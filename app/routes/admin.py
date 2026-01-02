from datetime import datetime, timedelta

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.decorators import role_required
from app.forms import StudentForm, FeeTypeForm
from app.models import (
    AcademicYear,
    ClassRoom,
    FeeType,
    Gender,
    Invoice,
    Parent,
    PaymentStatus,
    RegistrationStatus,
    Student,
    StudentCandidate,
    Transaction,
    User,
    UserRole,
)




admin_bp = Blueprint('admin', __name__)


# ==========================================
# 1. MANAJEMEN SISWA
# ==========================================

@admin_bp.route('/student/tambah', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.ADMIN)
def add_student():
    form = StudentForm()
    form.class_id.choices = [(c.id, c.name) for c in ClassRoom.query.all()]

    if form.validate_on_submit():
        try:
            # 1. BUAT AKUN USER UNTUK SISWA
            user_siswa = User(
                username=form.nis.data,
                email=form.email.data,
                password_hash=generate_password_hash(form.nis.data),
                role=UserRole.SISWA,
                must_change_password=True
            )
            db.session.add(user_siswa)
            db.session.flush()

            # 2. CEK ATAU BUAT DATA WALI
            existing_wali = Parent.query.filter_by(phone=form.parent_phone.data).first()
            wali = None

            if existing_wali:
                wali = existing_wali
                flash(f'Wali lama ditemukan: {wali.full_name}', 'info')
            else:
                user_wali = User(
                    username=form.parent_phone.data,
                    email=f"wali.{form.nis.data}@sekolah.id",
                    password_hash=generate_password_hash(form.parent_phone.data),
                    role=UserRole.WALI_MURID,
                    must_change_password=True
                )
                db.session.add(user_wali)
                db.session.flush()

                wali = Parent(
                    user_id=user_wali.id,
                    full_name=form.parent_name.data,
                    phone=form.parent_phone.data,
                    address=form.address.data,
                    job=form.parent_job.data
                )
                db.session.add(wali)
                db.session.flush()

            # 3. BUAT PROFIL SISWA
            siswa = Student(
                user_id=user_siswa.id,
                parent_id=wali.id,
                current_class_id=form.class_id.data,
                nis=form.nis.data,
                full_name=form.full_name.data,
                gender=Gender[form.gender.data],
                place_of_birth=form.place_of_birth.data,
                date_of_birth=form.date_of_birth.data,
                address=form.address.data
            )
            db.session.add(siswa)
            db.session.commit()

            flash(f'Siswa {form.full_name.data} berhasil ditambahkan!', 'success')
            return redirect(url_for('main.dashboard'))

        except Exception as e:
            db.session.rollback()
            flash(f'Gagal menyimpan: {str(e)}', 'danger')
            print(e)

    return render_template('admin/add_student.html', form=form)


@admin_bp.route('/student/edit/<int:student_id>', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.ADMIN)
def edit_student(student_id):
    # 1. Ambil data siswa target
    student = Student.query.get_or_404(student_id)

    # 2. Ambil daftar semua kelas (untuk dropdown pilihan kelas)
    classes = ClassRoom.query.all()

    # 3. Proses jika tombol Simpan ditekan (POST)
    if request.method == 'POST':
        try:
            # Update Data Dasar
            student.full_name = request.form.get('full_name')
            student.nis = request.form.get('nis')
            student.nisn = request.form.get('nisn')

            # Update Penempatan Kelas
            # Cek apakah admin memilih kelas atau "Belum Ada" (value kosong)
            class_id_input = request.form.get('class_id')
            if class_id_input and class_id_input.strip():
                student.current_class_id = int(class_id_input)
            else:
                student.current_class_id = None  # Set null jika admin memilih kosong

            # Update SPP Khusus (Fitur Baru)
            spp_input = request.form.get('custom_spp')
            if spp_input and spp_input.strip():
                # Hapus karakter non-angka jika ada (misal Rp, titik, koma)
                clean_spp = ''.join(filter(str.isdigit, spp_input))
                student.custom_spp_fee = int(clean_spp)
            else:
                student.custom_spp_fee = None  # Kosongkan/Reset ke tarif normal

            # Simpan ke Database
            db.session.commit()
            flash('Data siswa dan pengaturan SPP berhasil diperbarui!', 'success')
            return redirect(url_for('admin.list_students'))

        except Exception as e:
            db.session.rollback()
            flash(f'Gagal update: {str(e)}', 'danger')
            # Jika error, jangan redirect, tapi lanjut ke render template di bawah
            # agar Admin bisa melihat pesan errornya.

    # 4. Tampilkan Halaman Edit (GET Request atau jika POST gagal)
    return render_template('admin/edit_student.html', student=student, classes=classes)


@admin_bp.route('/student/reset-password/<int:user_id>', methods=['POST'])
@login_required
@role_required(UserRole.ADMIN)
def reset_password(user_id):
    user = User.query.get_or_404(user_id)

    if user.role == UserRole.ADMIN:
        flash('Tidak bisa mereset akun Admin lain dari sini.', 'danger')
        return redirect(url_for('main.dashboard'))

    try:
        new_password = "123456"  # Default fallback

        if user.role == UserRole.SISWA and user.student_profile:
            new_password = user.student_profile.nis
        elif user.role == UserRole.WALI_MURID and user.parent_profile:
            new_password = user.parent_profile.phone

        user.password_hash = generate_password_hash(new_password)
        user.must_change_password = True
        db.session.commit()

        flash(f'Password user {user.username} berhasil direset menjadi: {new_password}', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Gagal mereset password: {str(e)}', 'danger')

    return redirect(request.referrer or url_for('main.dashboard'))


@admin_bp.route('/daftar-student')
@login_required
@role_required(UserRole.ADMIN)
def list_students():
    students = Student.query.order_by(Student.id.desc()).all()
    return render_template('admin/list_students.html', students=students)


# ==========================================
# 2. MANAJEMEN KEUANGAN (SPP & INVOICE)
# ==========================================

@admin_bp.route('/keuangan/biaya', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.ADMIN)
def manage_fee_types():
    form = FeeTypeForm()

    # Ambil Tahun Ajaran (atau buat dummy jika kosong)
    years = AcademicYear.query.order_by(AcademicYear.name.desc()).all()
    if not years:
        default_year = AcademicYear(name='2024/2025', semester='Ganjil', is_active=True)
        db.session.add(default_year)
        db.session.commit()
        years = [default_year]

    form.academic_year_id.choices = [(y.id, f"{y.name} - {y.semester}") for y in years]

    if form.validate_on_submit():
        new_fee = FeeType(
            name=form.name.data,
            amount=form.amount.data,
            academic_year_id=form.academic_year_id.data
        )
        db.session.add(new_fee)
        db.session.commit()
        flash('Jenis biaya berhasil ditambahkan!', 'success')
        return redirect(url_for('admin.manage_fee_types'))

    fees = FeeType.query.order_by(FeeType.id.desc()).all()
    return render_template('admin/finance/manage_fees.html', form=form, fees=fees)


@admin_bp.route('/keuangan/generate/<int:fee_id>', methods=['POST'])
@login_required
@role_required(UserRole.ADMIN)
def generate_invoices(fee_id):
    fee = FeeType.query.get_or_404(fee_id)
    students = Student.query.all()

    count_success = 0
    count_skip = 0
    bulan_tahun = datetime.now().strftime("%Y%m")
    due_date_default = datetime.now() + timedelta(days=10)

    # Cek apakah ini tagihan bulanan/rutin? (SPP atau Infaq Bulanan)
    is_monthly_fee = "SPP" in fee.name.upper() or "BULAN" in fee.name.upper()

    try:
        for student in students:
            # 1. FILTER JURUSAN (RQDF vs SEKOLAH) - Sama seperti sebelumnya
            if "RQDF" in fee.name.upper() and student.student_candidate.program_type.name != 'RQDF_SORE':
                continue
            if "RQDF" not in fee.name.upper() and student.student_candidate.program_type.name == 'RQDF_SORE':
                continue

            # 2. CEK DUPLIKAT
            existing_inv = Invoice.query.filter_by(student_id=student.id, fee_type_id=fee.id).first()
            if existing_inv:
                count_skip += 1
                continue

            # 3. PENENTUAN NOMINAL (LOGIKA PRIORITAS)
            nominal_final = fee.amount  # Default: Harga Master

            # Prioritas 1: SPP KHUSUS (Jika ini tagihan bulanan & siswa punya tarif khusus)
            if is_monthly_fee and student.custom_spp_fee is not None:
                nominal_final = student.custom_spp_fee

            # Prioritas 2: BEASISWA (Jika tidak ada SPP Khusus, baru cek beasiswa)
            elif student.student_candidate.scholarship_category.name != 'NON_BEASISWA':
                # Diskon 50%
                nominal_final = fee.amount * 0.5

            # 4. BUAT INVOICE
            new_inv = Invoice(
                invoice_number=f"INV/{bulan_tahun}/{fee.id}/{student.id}",
                student_id=student.id,
                fee_type_id=fee.id,
                total_amount=int(nominal_final),
                paid_amount=0,
                status=PaymentStatus.UNPAID,
                due_date=due_date_default
            )
            db.session.add(new_inv)
            count_success += 1

        db.session.commit()
        flash(f'Sukses! {count_success} tagihan diterbitkan. ({count_skip} skip)', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'danger')

    return redirect(url_for('admin.manage_fee_types'))

# ==========================================
# 3. MANAJEMEN PPDB (PENERIMAAN SISWA BARU)
# ==========================================

@admin_bp.route('/ppdb/pendaftar')
@login_required
@role_required(UserRole.ADMIN)
def ppdb_list():
    candidates = StudentCandidate.query.order_by(StudentCandidate.created_at.desc()).all()
    return render_template('admin/ppdb/list.html', candidates=candidates)

@admin_bp.route('/ppdb/detail/<int:candidate_id>')
@login_required
@role_required(UserRole.ADMIN)
def ppdb_detail(candidate_id):
    candidate = StudentCandidate.query.get_or_404(candidate_id)
    return render_template('admin/ppdb/detail.html', candidate=candidate)


@admin_bp.route('/ppdb/terima/<int:candidate_id>', methods=['POST'])
@login_required
@role_required(UserRole.ADMIN)
def accept_candidate(candidate_id):
    calon = StudentCandidate.query.get_or_404(candidate_id)

    if calon.status == RegistrationStatus.ACCEPTED:
        flash('Siswa ini sudah diproses sebelumnya.', 'warning')
        return redirect(url_for('admin.ppdb_detail', candidate_id=calon.id))

    try:
        # --- 1. PROSES AKUN (TIDAK BERUBAH) ---
        tahun_masuk = datetime.now().year
        urutan = Student.query.filter(Student.nis.like(f"{tahun_masuk}%")).count() + 1
        nis_baru = f"{tahun_masuk}{str(urutan).zfill(4)}"

        # User Wali
        user_wali = User.query.filter_by(username=calon.parent_phone).first()
        if not user_wali:
            user_wali = User(username=calon.parent_phone, email=f"wali.{nis_baru}@sekolah.id",
                             password_hash=generate_password_hash("123456"), role=UserRole.WALI_MURID,
                             must_change_password=True)
            db.session.add(user_wali)
            db.session.flush()
            parent_profile = Parent(user_id=user_wali.id, full_name=calon.father_name, phone=calon.parent_phone,
                                    job=calon.father_job, address=calon.address)
            db.session.add(parent_profile)
            db.session.flush()
        else:
            parent_profile = user_wali.parent_profile

        # User Siswa
        user_siswa = User(username=nis_baru, email=f"{nis_baru}@sekolah.id",
                          password_hash=generate_password_hash("123456"), role=UserRole.SISWA,
                          must_change_password=True)
        db.session.add(user_siswa)
        db.session.flush()
        siswa_baru = Student(user_id=user_siswa.id, parent_id=parent_profile.id, nis=nis_baru,
                             full_name=calon.full_name, gender=calon.gender, place_of_birth=calon.place_of_birth,
                             date_of_birth=calon.date_of_birth, address=calon.address)
        db.session.add(siswa_baru)
        db.session.flush()

        # --- 2. SMART INVOICING (VERSI DINAMIS) ---

        # Fungsi Helper: Cari harga di DB dulu, kalau gak ada baru pakai default
        def get_nominal(nama_biaya, harga_default):
            biaya_db = FeeType.query.filter_by(name=nama_biaya).first()
            if biaya_db:
                return biaya_db.amount  # Pakai harga dari Admin Dashboard
            return harga_default  # Pakai harga hardcode (hanya untuk pertama kali)

        tagihan_list = []

        # === KASUS A: SEKOLAH FORMAL ===
        if calon.program_type.name == 'SEKOLAH_FULLDAY':
            if calon.scholarship_category.name == 'NON_BEASISWA':
                # Format: get_nominal('Nama di DB', Harga Default)
                tagihan_list = [
                    {'nama': 'Biaya Pendaftaran', 'nominal': get_nominal('Biaya Pendaftaran', 200000)},
                    {'nama': 'Seragam Batik', 'nominal': get_nominal('Seragam Batik', 100000)},
                    {'nama': 'Infaq Bulanan (Juli)', 'nominal': get_nominal('Infaq Bulanan (Juli)', 650000)},
                    {'nama': 'Wakaf Bangunan', 'nominal': get_nominal('Wakaf Bangunan', 1000000)},
                    {'nama': 'Fasilitas Kasur', 'nominal': get_nominal('Fasilitas Kasur', 500000)},
                    {'nama': 'Orientasi Siswa', 'nominal': get_nominal('Orientasi Siswa', 150000)},
                    {'nama': 'Wakaf Perpustakaan', 'nominal': get_nominal('Wakaf Perpustakaan', 100000)},
                    {'nama': 'Infaq Qurban', 'nominal': get_nominal('Infaq Qurban', 100000)},
                    {'nama': 'Raport Pesantren', 'nominal': get_nominal('Raport Pesantren', 65000)},
                    {'nama': 'Adm Sekolah Formal', 'nominal': get_nominal('Adm Sekolah Formal', 500000)},
                    {'nama': 'Infaq Kegiatan', 'nominal': get_nominal('Infaq Kegiatan', 100000)}
                ]
            else:
                # BEASISWA
                tagihan_list = [
                    {'nama': 'Biaya Pendaftaran (Beasiswa)',
                     'nominal': get_nominal('Biaya Pendaftaran (Beasiswa)', 100000)},
                    {'nama': 'Infaq Bulanan (Beasiswa)', 'nominal': get_nominal('Infaq Bulanan (Beasiswa)', 325000)},
                    {'nama': 'Wakaf Bangunan (Beasiswa)', 'nominal': get_nominal('Wakaf Bangunan (Beasiswa)', 500000)},
                    {'nama': 'Fasilitas Lemari (Beasiswa)',
                     'nominal': get_nominal('Fasilitas Lemari (Beasiswa)', 250000)},
                    {'nama': 'Fasilitas Kasur (Beasiswa)',
                     'nominal': get_nominal('Fasilitas Kasur (Beasiswa)', 250000)},
                    {'nama': 'Orientasi Siswa (Beasiswa)', 'nominal': get_nominal('Orientasi Siswa (Beasiswa)', 75000)},
                    {'nama': 'Raport', 'nominal': get_nominal('Raport', 65000)},
                    {'nama': 'Wakaf Perpustakaan (Beasiswa)',
                     'nominal': get_nominal('Wakaf Perpustakaan (Beasiswa)', 50000)},
                    {'nama': 'Infaq Kegiatan (Beasiswa)', 'nominal': get_nominal('Infaq Kegiatan (Beasiswa)', 50000)},
                    {'nama': 'Infaq Qurban (Beasiswa)', 'nominal': get_nominal('Infaq Qurban (Beasiswa)', 50000)},
                    {'nama': 'Seragam Batik', 'nominal': get_nominal('Seragam Batik', 100000)},
                    {'nama': 'Adm Sekolah Formal', 'nominal': get_nominal('Adm Sekolah Formal', 500000)}
                ]

        # === KASUS B: RQDF REGULER SORE ===
        elif calon.program_type.name == 'RQDF_SORE':
            tagihan_list = [
                {'nama': 'Infaq Pendaftaran (RQDF)', 'nominal': get_nominal('Infaq Pendaftaran (RQDF)', 300000)},
                {'nama': 'Uang Dana Semesteran', 'nominal': get_nominal('Uang Dana Semesteran', 50000)},
                {'nama': 'Infaq Bulanan RQDF', 'nominal': get_nominal('Infaq Bulanan RQDF', 150000)},
                {'nama': 'Atribut (Syal) & Buku', 'nominal': get_nominal('Atribut (Syal) & Buku', 100000)},
                {'nama': 'Raport RQDF', 'nominal': get_nominal('Raport RQDF', 50000)}
            ]

            # Khusus Seragam & Pembangunan (Tetap pakai logika form karena variatif)
            if calon.initial_pledge_amount and calon.initial_pledge_amount > 0:
                tagihan_list.append({'nama': 'Infaq Pembangunan Pesantren', 'nominal': calon.initial_pledge_amount})

            harga_seragam = 0
            uk = calon.uniform_size.name
            # Cari harga seragam di DB juga (opsional), atau tetap hardcode logika ukuran
            if uk in ['S', 'M']:
                harga_seragam = get_nominal('Seragam RQDF (S/M)', 345000)
            elif uk in ['L', 'XL']:
                harga_seragam = get_nominal('Seragam RQDF (L/XL)', 355000)
            elif uk == 'XXL':
                harga_seragam = get_nominal('Seragam RQDF (XXL)', 380000)

            if harga_seragam > 0:
                tagihan_list.append({'nama': f'Seragam RQDF (Ukuran {uk})', 'nominal': harga_seragam})

        # --- 3. EKSEKUSI (SAMA) ---
        due_date = datetime.now() + timedelta(days=14)
        inv_prefix = f"INV/{datetime.now().strftime('%Y%m')}/{siswa_baru.id}"

        ctr = 1
        for item in tagihan_list:
            # PENTING: Cek lagi di DB untuk create record jika belum ada
            fee_type = FeeType.query.filter_by(name=item['nama']).first()
            if not fee_type:
                # Jika belum ada di Master Biaya, buat baru dengan nominal dari logic di atas
                fee_type = FeeType(name=item['nama'], amount=item['nominal'])
                db.session.add(fee_type)
                db.session.flush()

            # Buat Invoice pakai nominal yang sudah dipastikan (bisa dari DB atau default)
            new_inv = Invoice(
                invoice_number=f"{inv_prefix}/{ctr}",
                student_id=siswa_baru.id,
                fee_type_id=fee_type.id,
                total_amount=item['nominal'],  # Ini sudah hasil fungsi get_nominal
                paid_amount=0,
                status=PaymentStatus.UNPAID,
                due_date=due_date
            )
            db.session.add(new_inv)
            ctr += 1

        calon.status = RegistrationStatus.ACCEPTED
        db.session.commit()
        flash(f'Sukses! Siswa {siswa_baru.full_name} diterima. {len(tagihan_list)} rincian tagihan diterbitkan.',
              'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Error: {e}', 'danger')
        print(e)

    return redirect(url_for('admin.ppdb_detail', candidate_id=candidate_id))