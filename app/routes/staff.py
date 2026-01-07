from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
from sqlalchemy import func
from app.extensions import db
from app.decorators import role_required
from app.forms import PaymentForm, StudentForm  # Pastikan import ini ada
from app.models import (
    UserRole, User, Student, Parent, Staff, ClassRoom, Gender,
    Invoice, Transaction, PaymentStatus, FeeType,
    StudentCandidate, RegistrationStatus
)

staff_bp = Blueprint('staff', __name__)


@staff_bp.route('/dashboard')
@login_required
@role_required(UserRole.TU)
def dashboard():
    # 1. Hitung Pemasukan Hari Ini
    today = datetime.now().date()
    pemasukan_hari_ini = db.session.query(func.sum(Transaction.amount)).filter(
        func.date(Transaction.date) == today
    ).scalar() or 0

    # 2. Kirim ke HTML
    return render_template('staff/dashboard.html',
                           pemasukan_hari_ini=pemasukan_hari_ini)


# =========================================================
# 1. MODUL KEUANGAN (KASIR & GENERATE TAGIHAN)
# =========================================================

@staff_bp.route('/kasir', methods=['GET'])
@login_required
@role_required(UserRole.TU)
def cashier_search():
    query = request.args.get('q')
    students = []
    if query:
        students = Student.query.filter(
            (Student.full_name.ilike(f'%{query}%')) |
            (Student.nis.ilike(f'%{query}%'))).all()
    return render_template('staff/cashier_search.html', students=students, query=query)


@staff_bp.route('/kasir/bayar/<int:student_id>', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.TU)
def cashier_pay(student_id):
    student = Student.query.get_or_404(student_id)
    unpaid_invoices = Invoice.query.filter(
        Invoice.student_id == student.id,
        Invoice.status != PaymentStatus.PAID
    ).all()

    form = PaymentForm()

    if request.method == 'POST':
        invoice_id = request.form.get('invoice_id')
        invoice = Invoice.query.get(invoice_id)

        if invoice and form.validate_on_submit():
            bayar = form.amount.data
            sisa_tagihan = invoice.total_amount - invoice.paid_amount

            if bayar > sisa_tagihan:
                flash(f'Gagal! Pembayaran melebihi sisa (Maks: {sisa_tagihan})', 'danger')
            else:
                # Catat Transaksi
                trx = Transaction(
                    invoice_id=invoice.id,
                    amount=bayar,
                    method=form.method.data,
                    pic_id=current_user.id,  # TU yang login
                    #status='SUCCESS'
                )
                db.session.add(trx)

                # Update Invoice
                invoice.paid_amount += bayar
                if invoice.paid_amount >= invoice.total_amount:
                    invoice.status = PaymentStatus.PAID
                else:
                    invoice.status = PaymentStatus.PARTIAL

                db.session.commit()
                flash(f'Pembayaran Rp {bayar:,.0f} diterima!', 'success')
                return redirect(url_for('staff.cashier_pay', student_id=student.id))

    return render_template('staff/cashier_payment.html', student=student, invoices=unpaid_invoices, form=form)


@staff_bp.route('/tagihan/terbitkan/<int:fee_id>', methods=['POST'])
@login_required
@role_required(UserRole.TU)
def generate_invoices(fee_id):
    """
    TU yang berhak menekan tombol 'Terbitkan' tagihan bulanan.
    Admin hanya membuat Master Biayanya saja.
    """
    fee = FeeType.query.get_or_404(fee_id)
    students = Student.query.all()

    count_success = 0
    bulan_tahun = datetime.now().strftime("%Y%m")
    due_date_default = datetime.now() + timedelta(days=10)
    is_monthly_fee = "SPP" in fee.name.upper() or "BULAN" in fee.name.upper()

    try:
        for student in students:
            # Filter Jurusan (RQDF vs Formal)
            if "RQDF" in fee.name.upper() and student.student_candidate.program_type.name != 'RQDF_SORE': continue
            if "RQDF" not in fee.name.upper() and student.student_candidate.program_type.name == 'RQDF_SORE': continue

            # Cek Duplikat
            if Invoice.query.filter_by(student_id=student.id, fee_type_id=fee.id).first():
                continue

            # Hitung Nominal (Smart Logic)
            nominal_final = fee.amount
            if is_monthly_fee and student.custom_spp_fee is not None:
                nominal_final = student.custom_spp_fee
            elif student.student_candidate.scholarship_category.name != 'NON_BEASISWA':
                nominal_final = fee.amount * 0.5

            # Buat Invoice
            new_inv = Invoice(
                invoice_number=f"INV/{bulan_tahun}/{fee.id}/{student.id}",
                student_id=student.id,
                fee_type_id=fee.id,
                total_amount=int(nominal_final),
                status=PaymentStatus.UNPAID,
                due_date=due_date_default
            )
            db.session.add(new_inv)
            count_success += 1

        db.session.commit()
        flash(f'Berhasil menerbitkan {count_success} tagihan baru.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'danger')

    # Kembali ke halaman list biaya (yang bisa diakses TU juga nanti)
    return redirect(url_for('staff.manage_fee_types'))


# =========================================================
# 2. MODUL KESISWAAN (DATA SISWA & PENEMPATAN KELAS)
# =========================================================

@staff_bp.route('/siswa/data')
@login_required
@role_required(UserRole.TU)
def list_students():
    students = Student.query.order_by(Student.id.desc()).all()
    # Kita reuse template admin agar hemat, atau buat folder staff/students
    return render_template('student/list_students.html', students=students)


@staff_bp.route('/siswa/edit/<int:student_id>', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.TU)
def edit_student(student_id):
    """TU bertugas menempatkan siswa ke kelas dan input NISN"""
    student = Student.query.get_or_404(student_id)
    classes = ClassRoom.query.all()

    if request.method == 'POST':
        student.full_name = request.form.get('full_name')
        student.nisn = request.form.get('nisn')

        class_id = request.form.get('class_id')
        student.current_class_id = int(class_id) if class_id else None

        # TU juga bisa update SPP Khusus jika ada negosiasi
        spp_input = request.form.get('custom_spp')
        if spp_input:
            student.custom_spp_fee = int(''.join(filter(str.isdigit, spp_input)))
        else:
            student.custom_spp_fee = None

        db.session.commit()
        flash('Data siswa berhasil diupdate.', 'success')
        return redirect(url_for('staff.list_students'))

    return render_template('staff/edit_student.html',
                           student=student,
                           classes=classes,)



# =========================================================
# 3. MODUL PPDB (VERIFIKASI & PENERIMAAN)
# =========================================================

@staff_bp.route('/ppdb/list')
@login_required
@role_required(UserRole.TU)
def ppdb_list():
    candidates = StudentCandidate.query.order_by(StudentCandidate.created_at.desc()).all()
    return render_template('staff/ppdb/list.html', candidates=candidates)


@staff_bp.route('/ppdb/detail/<int:candidate_id>')
@login_required
@role_required(UserRole.TU)
def ppdb_detail(candidate_id):
    candidate = StudentCandidate.query.get_or_404(candidate_id)
    return render_template('staff/ppdb/detail.html', candidate=candidate)


@staff_bp.route('/ppdb/terima/<int:candidate_id>', methods=['POST'])  # <--- GANTI JADI staff_bp
@login_required
@role_required(UserRole.TU)
def accept_candidate(candidate_id):
    calon = StudentCandidate.query.get_or_404(candidate_id)

    if calon.status == RegistrationStatus.ACCEPTED:
        flash('Siswa ini sudah diproses sebelumnya.', 'warning')
        return redirect(url_for('staff.ppdb_detail', candidate_id=calon.id))

    try:
        # --- 1. PROSES AKUN ---
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
        def get_nominal(nama_biaya, harga_default):
            biaya_db = FeeType.query.filter_by(name=nama_biaya).first()
            if biaya_db:
                return biaya_db.amount
            return harga_default

        tagihan_list = []

        if calon.program_type.name == 'SEKOLAH_FULLDAY':
            if calon.scholarship_category.name == 'NON_BEASISWA':
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

        elif calon.program_type.name == 'RQDF_SORE':
            tagihan_list = [
                {'nama': 'Infaq Pendaftaran (RQDF)', 'nominal': get_nominal('Infaq Pendaftaran (RQDF)', 300000)},
                {'nama': 'Uang Dana Semesteran', 'nominal': get_nominal('Uang Dana Semesteran', 50000)},
                {'nama': 'Infaq Bulanan RQDF', 'nominal': get_nominal('Infaq Bulanan RQDF', 150000)},
                {'nama': 'Atribut (Syal) & Buku', 'nominal': get_nominal('Atribut (Syal) & Buku', 100000)},
                {'nama': 'Raport RQDF', 'nominal': get_nominal('Raport RQDF', 50000)}
            ]

            if calon.initial_pledge_amount and calon.initial_pledge_amount > 0:
                tagihan_list.append({'nama': 'Infaq Pembangunan Pesantren', 'nominal': calon.initial_pledge_amount})

            harga_seragam = 0
            uk = calon.uniform_size.name
            if uk in ['S', 'M']:
                harga_seragam = get_nominal('Seragam RQDF (S/M)', 345000)
            elif uk in ['L', 'XL']:
                harga_seragam = get_nominal('Seragam RQDF (L/XL)', 355000)
            elif uk == 'XXL':
                harga_seragam = get_nominal('Seragam RQDF (XXL)', 380000)

            if harga_seragam > 0:
                tagihan_list.append({'nama': f'Seragam RQDF (Ukuran {uk})', 'nominal': harga_seragam})

        due_date = datetime.now() + timedelta(days=14)
        inv_prefix = f"INV/{datetime.now().strftime('%Y%m')}/{siswa_baru.id}"

        ctr = 1
        for item in tagihan_list:
            fee_type = FeeType.query.filter_by(name=item['nama']).first()
            if not fee_type:
                fee_type = FeeType(name=item['nama'], amount=item['nominal'])
                db.session.add(fee_type)
                db.session.flush()

            new_inv = Invoice(
                invoice_number=f"{inv_prefix}/{ctr}",
                student_id=siswa_baru.id,
                fee_type_id=fee_type.id,
                total_amount=item['nominal'],
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

    return redirect(url_for('staff.ppdb_detail', candidate_id=candidate_id))