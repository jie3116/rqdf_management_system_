from datetime import datetime, timedelta
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from sqlalchemy import func
from app.extensions import db
from app.decorators import role_required
from app.forms import StudentForm, FeeTypeForm  # Pastikan Anda punya form untuk Guru/Mapel nanti
from app.models import (
    # Base & Enums
    UserRole, Gender, PaymentStatus, RegistrationStatus,
    # Users
    User, Student, Parent, Teacher, Staff,
    # Academic
    AcademicYear, ClassRoom, Subject, Schedule,
    # Finance
    FeeType, Invoice, Transaction,
    # Activities
    Extracurricular,
    # PPDB
    StudentCandidate,
    # Config
    AppConfig
)

admin_bp = Blueprint('admin', __name__)


# =========================================================
# 1. DASHBOARD & KONFIGURASI SISTEM
# =========================================================

@admin_bp.route('/dashboard')
@login_required
@role_required(UserRole.ADMIN)
def dashboard():
    # 1. Hitung Total Siswa & Guru
    total_students = Student.query.filter_by(is_deleted=False).count()
    total_teachers = Teacher.query.filter_by(is_deleted=False).count()

    # 2. Hitung Pemasukan Hari Ini (PENTING!)
    today = datetime.now().date()
    income_today = db.session.query(func.sum(Transaction.amount)).filter(
        func.date(Transaction.date) == today
    ).scalar() or 0  # <--- "or 0" penting agar tidak None

    # 3. Kirim variabel ke HTML (income_today wajib ada)
    return render_template('admin/dashboard.html',
                           total_students=total_students,
                           total_teachers=total_teachers,
                           income_today=income_today)  # <--- JANGAN LUPA INI


@admin_bp.route('/pengaturan/sistem', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.ADMIN)
def manage_app_config():
    """Mengelola Variable Global (Misal: Biaya Denda, Pesan Pengumuman, dll)"""
    if request.method == 'POST':
        key = request.form.get('key')
        value = request.form.get('value')
        description = request.form.get('description')

        config = AppConfig.query.filter_by(key=key).first()
        if config:
            config.value = value
            config.description = description
        else:
            new_config = AppConfig(key=key, value=value, description=description)
            db.session.add(new_config)

        db.session.commit()
        flash('Konfigurasi tersimpan.', 'success')
        return redirect(url_for('admin.manage_app_config'))

    configs = AppConfig.query.all()
    return render_template('admin/system/configs.html', configs=configs)


# =========================================================
# 2. MASTER AKADEMIK (TAHUN AJARAN & MATA PELAJARAN)
# =========================================================

@admin_bp.route('/akademik/tahun-ajaran', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.ADMIN)
def manage_academic_years():
    if request.method == 'POST':
        name = request.form.get('name')  # 2025/2026
        semester = request.form.get('semester')  # Ganjil/Genap
        is_active = request.form.get('is_active') == 'on'

        if is_active:
            # Nonaktifkan tahun lain jika ini di-set aktif
            AcademicYear.query.update({AcademicYear.is_active: False})

        new_year = AcademicYear(name=name, semester=semester, is_active=is_active)
        db.session.add(new_year)
        db.session.commit()
        flash('Tahun ajaran berhasil dibuat.', 'success')
        return redirect(url_for('admin.manage_academic_years'))

    years = AcademicYear.query.order_by(AcademicYear.id.desc()).all()
    return render_template('admin/academic/years.html', years=years)


@admin_bp.route('/akademik/aktifkan-tahun/<int:id>')
@login_required
@role_required(UserRole.ADMIN)
def activate_academic_year(id):
    # Nonaktifkan semua
    AcademicYear.query.update({AcademicYear.is_active: False})
    # Aktifkan yang dipilih
    year = AcademicYear.query.get_or_404(id)
    year.is_active = True
    db.session.commit()
    flash(f'Tahun Ajaran {year.name} - {year.semester} sekarang AKTIF.', 'success')
    return redirect(url_for('admin.manage_academic_years'))


@admin_bp.route('/akademik/mapel', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.ADMIN)
def manage_subjects():
    if request.method == 'POST':
        code = request.form.get('code')
        name = request.form.get('name')
        kkm = request.form.get('kkm')

        new_subject = Subject(code=code, name=name, kkm=float(kkm))
        db.session.add(new_subject)
        db.session.commit()
        flash('Mata Pelajaran ditambahkan.', 'success')
        return redirect(url_for('admin.manage_subjects'))

    subjects = Subject.query.filter_by(is_deleted=False).all()
    return render_template('admin/academic/subjects.html', subjects=subjects)


@admin_bp.route('/akademik/mapel/edit/<int:subject_id>', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.ADMIN)
def edit_subject(subject_id):
    subject = Subject.query.get_or_404(subject_id)

    if request.method == 'POST':
        subject.code = request.form.get('code')
        subject.name = request.form.get('name')
        subject.kkm = float(request.form.get('kkm')) # nilai kkm dengan type float

        try:
            db.session.commit()
            flash(f'Mapel {subject.name} berhasil diperbarui.', 'success')
            return redirect(url_for('admin.manage_subjects'))
        except Exception as e:
            db.session.rollback()
            flash(f'Gagal update: {e}', 'danger')

    return render_template('admin/academic/edit_subject.html', subject=subject)


# =========================================================
# 3. MASTER SDM (GURU & STAFF)
# =========================================================

@admin_bp.route('/sdm/guru', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.ADMIN)
def manage_teachers():
    if request.method == 'POST':
        # 1. Buat User Login
        username = request.form.get('nip')
        password = request.form.get('password') or "guru123"
        full_name = request.form.get('full_name')
        phone = request.form.get('phone')
        specialty = request.form.get('specialty')

        try:
            user = User(
                username=username,
                email=f"{username}@sekolah.id",
                password_hash=generate_password_hash(password),
                role=UserRole.GURU,
                must_change_password=True
            )
            db.session.add(user)
            db.session.flush()  # Dapat ID

            # 2. Buat Profile Guru
            teacher = Teacher(
                user_id=user.id,
                nip=username,
                full_name=full_name,
                phone=phone,
                specialty=specialty
            )
            db.session.add(teacher)
            db.session.commit()
            flash('Data Guru berhasil ditambahkan.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {e}', 'danger')

        return redirect(url_for('admin.manage_teachers'))

    teachers = Teacher.query.filter_by(is_deleted=False).all()
    return render_template('admin/hr/teachers.html', teachers=teachers)


@admin_bp.route('/sdm/guru/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.ADMIN)
def edit_teacher(id):
    # Ambil data guru, return 404 jika tidak ada
    teacher = Teacher.query.get_or_404(id)

    if request.method == 'POST':
        # Ambil data dari form
        new_nip = request.form.get('nip')
        full_name = request.form.get('full_name')
        specialty = request.form.get('specialty')
        phone = request.form.get('phone')
        new_password = request.form.get('password')

        try:
            # 1. Update Data Profil Guru
            teacher.full_name = full_name
            teacher.specialty = specialty
            teacher.phone = phone

            # 2. Cek apakah NIP berubah? (NIP berpengaruh ke Username Login)
            if new_nip and new_nip != teacher.nip:
                # Cek apakah NIP baru sudah dipakai orang lain?
                existing_user = User.query.filter_by(username=new_nip).first()
                if existing_user:
                    flash(f'NIP {new_nip} sudah digunakan oleh user lain.', 'danger')
                    return redirect(url_for('admin.edit_teacher', id=id))

                # Jika aman, update NIP di tabel Teacher dan Username di tabel User
                teacher.nip = new_nip
                teacher.user.username = new_nip
                teacher.user.email = f"{new_nip}@sekolah.id"

            # 3. Update Password (hanya jika diisi)
            if new_password:
                teacher.user.password_hash = generate_password_hash(new_password)
                teacher.user.must_change_password = True  # Opsional: paksa ganti pas login

            db.session.commit()
            flash('Data Guru berhasil diperbarui.', 'success')
            return redirect(url_for('admin.manage_teachers'))

        except Exception as e:
            db.session.rollback()
            flash(f'Gagal update data: {e}', 'danger')

    # Render template edit
    return render_template('admin/hr/edit_teacher.html', teacher=teacher)

@admin_bp.route('/sdm/staff', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.ADMIN)
def manage_staff():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password') or "staff123"
        full_name = request.form.get('full_name')
        position = request.form.get('position') # Misal: Kepala TU, Staff Keuangan

        # Cek Username Kembar
        if User.query.filter_by(username=username).first():
            flash('Username sudah digunakan.', 'danger')
        else:
            try:
                # 1. Buat User Login
                user = User(username=username, email=f"{username}@sekolah.id", role=UserRole.TU)
                user.set_password(password)
                db.session.add(user)
                db.session.flush()

                # 2. Buat Profil Staff
                staff = Staff(user_id=user.id, full_name=full_name, position=position)
                db.session.add(staff)
                db.session.commit()
                flash('Staff Tata Usaha berhasil ditambahkan.', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error: {e}', 'danger')
        return redirect(url_for('admin.manage_staff'))

    staff_list = Staff.query.filter_by(is_deleted=False).all()
    return render_template('admin/hr/staff.html', staff_list=staff_list)


@admin_bp.route('/sdm/staff/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.ADMIN)
def edit_staff(id):
    # Ambil data staff, jika tidak ada return 404
    staff = Staff.query.get_or_404(id)

    if request.method == 'POST':
        # Ambil data input
        staff.full_name = request.form.get('full_name')
        staff.position = request.form.get('position')

        # Opsional: Jika ingin admin bisa reset password staff dari sini
        new_password = request.form.get('password')
        if new_password:  # Hanya update jika kolom password diisi
            staff.user.set_password(new_password)

        try:
            db.session.commit()
            flash('Data Staff berhasil diperbarui.', 'success')
            # Redirect kembali ke fungsi manage_staff (nama blueprint 'admin')
            return redirect(url_for('admin.manage_staff'))
        except Exception as e:
            db.session.rollback()
            flash(f'Gagal memperbarui data: {e}', 'danger')

    # Render template edit
    return render_template('admin/hr/edit_staff.html', staff=staff)
# =========================================================
# 4. MASTER KELAS & WALI KELAS
# =========================================================

@admin_bp.route('/sekolah/kelas', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.ADMIN)
def manage_classes():
    if request.method == 'POST':
        name = request.form.get('name')
        grade_level = request.form.get('grade_level')
        homeroom_id = request.form.get('homeroom_teacher_id')  # ID Guru

        new_class = ClassRoom(
            name=name,
            grade_level=grade_level,
            homeroom_teacher_id=homeroom_id if homeroom_id else None
        )
        db.session.add(new_class)
        db.session.commit()
        flash('Kelas berhasil dibuat.', 'success')
        return redirect(url_for('admin.manage_classes'))

    classes = ClassRoom.query.filter_by(is_deleted=False).all()
    teachers = Teacher.query.filter_by(is_deleted=False).all()  # Untuk dropdown
    return render_template('admin/academic/classes.html', classes=classes, teachers=teachers)


@admin_bp.route('/sekolah/kelas/edit/<int:class_id>', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.ADMIN)
def edit_class(class_id):
    # Ambil data kelas atau 404 jika tidak ada
    class_room = ClassRoom.query.get_or_404(class_id)
    teachers = Teacher.query.filter_by(is_deleted=False).all()

    if request.method == 'POST':
        class_room.name = request.form.get('name')
        class_room.grade_level = request.form.get('grade_level')

        # Handle Wali Kelas (Bisa Kosong/None)
        homeroom_id = request.form.get('homeroom_teacher_id')
        class_room.homeroom_teacher_id = homeroom_id if homeroom_id else None

        try:
            db.session.commit()
            flash(f'Kelas {class_room.name} berhasil diperbarui.', 'success')
            return redirect(url_for('admin.manage_classes'))
        except Exception as e:
            db.session.rollback()
            flash(f'Gagal update: {e}', 'danger')

    return render_template('admin/academic/edit_class.html', class_room=class_room, teachers=teachers)

# =========================================================
# 5. MASTER KESISWAAN (EKSKUL)
# =========================================================

@admin_bp.route('/kesiswaan/ekskul', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.ADMIN)
def manage_extracurriculars():
    if request.method == 'POST':
        name = request.form.get('name')
        supervisor_id = request.form.get('supervisor_id')

        ekskul = Extracurricular(name=name, supervisor_teacher_id=supervisor_id)
        db.session.add(ekskul)
        db.session.commit()
        flash('Ekstrakurikuler ditambahkan.', 'success')
        return redirect(url_for('admin.manage_extracurriculars'))

    ekskuls = Extracurricular.query.filter_by(is_deleted=False).all()
    teachers = Teacher.query.filter_by(is_deleted=False).all()
    return render_template('admin/student_affairs/extracurriculars.html', ekskuls=ekskuls, teachers=teachers)


# =========================================================
# 6. MANAJEMEN SISWA (SAMA SEPERTI SEBELUMNYA)
# =========================================================

# app/routes/admin.py

from app.forms import StudentForm
from app.models import User, Student, Parent, ClassRoom, UserRole, Gender


@admin_bp.route('/student/tambah', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.ADMIN)
def add_student():
    form = StudentForm()

    # 1. Isi Pilihan Kelas (Wajib diisi dinamis setiap loading halaman)
    # Kita ambil ID dan Nama Kelas dari database
    form.class_id.choices = [(c.id, c.name) for c in ClassRoom.query.filter_by(is_deleted=False).all()]

    # Jika belum ada kelas sama sekali, kasih opsi dummy biar gak error
    if not form.class_id.choices:
        form.class_id.choices = [(0, 'Belum ada kelas')]

    if form.validate_on_submit():
        try:
            # A. CEK DUPLIKASI (Penting!)
            if User.query.filter_by(username=form.nis.data).first():
                flash('NIS sudah terdaftar sebagai User.', 'warning')
                return render_template('admin/add_student.html', form=form)

            # B. BUAT USER SISWA
            student_user = User(
                username=form.nis.data,  # Login pakai NIS
                email=form.email.data,  # Pakai email dari inputan form
                role=UserRole.SISWA
            )
            student_user.set_password(form.nis.data)  # Default Pass = NIS
            db.session.add(student_user)
            db.session.flush()

            # C. BUAT PROFIL SISWA
            new_student = Student(
                user_id=student_user.id,
                nis=form.nis.data,
                full_name=form.full_name.data,
                gender=Gender[form.gender.data],  # Konversi string 'L'/'P' ke Enum
                place_of_birth=form.place_of_birth.data,
                date_of_birth=form.date_of_birth.data,
                current_class_id=form.class_id.data,
                address=form.address.data
            )
            db.session.add(new_student)

            # D. BUAT USER & PROFIL WALI
            # Cek dulu takutnya ortu sudah punya akun (kakak kelas)
            parent_user = User.query.filter_by(username=form.parent_phone.data).first()

            if not parent_user:
                # Buat Akun Wali Baru
                parent_user = User(
                    username=form.parent_phone.data,  # Login pakai No WA
                    email=f"{form.parent_phone.data}@wali.sekolah.id",  # Email dummy
                    role=UserRole.WALI_MURID
                )
                parent_user.set_password(form.parent_phone.data)  # Default Pass = No WA
                db.session.add(parent_user)
                db.session.flush()

                # Buat Profil Wali Baru
                parent_profile = Parent(
                    user_id=parent_user.id,
                    full_name=form.parent_name.data,
                    phone=form.parent_phone.data,
                    job=form.parent_job.data,  # Sesuai form Anda
                    address=form.address.data  # Alamat sama dengan anak
                )
                db.session.add(parent_profile)
                db.session.flush()
            else:
                # Jika sudah ada user, ambil profilnya
                parent_profile = parent_user.parent_profile

            # Sambungkan Siswa ke Wali
            new_student.parent_id = parent_profile.id

            db.session.commit()
            flash(f'Siswa {form.full_name.data} berhasil ditambahkan!', 'success')
            return redirect(url_for('admin.list_students'))

        except Exception as e:
            db.session.rollback()
            flash(f"Gagal menyimpan: {str(e)}", 'danger')

    return render_template('admin/add_student.html', form=form)


@admin_bp.route('/student/edit/<int:student_id>', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.ADMIN)
def edit_student(student_id):
    student = Student.query.get_or_404(student_id)
    classes = ClassRoom.query.filter_by(is_deleted=False).all()

    if request.method == 'POST':
        # Update Data Dasar
        student.full_name = request.form.get('full_name')
        student.nis = request.form.get('nis')
        student.nisn = request.form.get('nisn')

        # Update Kelas
        cid = request.form.get('class_id')
        student.current_class_id = int(cid) if cid else None

        # Update SPP Khusus
        spp = request.form.get('custom_spp')
        if spp:
            student.custom_spp_fee = int(''.join(filter(str.isdigit, spp)))
        else:
            student.custom_spp_fee = None

        student.save()  # Menggunakan method save() dari BaseModel
        flash('Data siswa diupdate.', 'success')
        return redirect(url_for('admin.list_students'))

    return render_template('admin/edit_student.html', student=student, classes=classes)


@admin_bp.route('/daftar-student')
@login_required
@role_required(UserRole.ADMIN)
def list_students():
    # Menampilkan siswa yang TIDAK dihapus (Soft Delete Check)
    students = Student.query.filter_by(is_deleted=False).order_by(Student.id.desc()).all()
    return render_template('student/list_students.html', students=students)


@admin_bp.route('/student/hapus/<int:id>')
@login_required
@role_required(UserRole.ADMIN)
def delete_student(id):
    student = Student.query.get_or_404(id)
    student.delete()  # Menggunakan method Soft Delete dari BaseModel
    flash('Data siswa berhasil dihapus (Soft Delete).', 'warning')
    return redirect(url_for('admin.list_students'))


# =========================================================
# 7. MANAJEMEN KEUANGAN (SAMA SEPERTI SEBELUMNYA)
# =========================================================

@admin_bp.route('/keuangan/master-biaya', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.ADMIN)
def manage_fee_types():
    if request.method == 'POST':
        name = request.form.get('name')
        amount = request.form.get('amount')
        academic_year_id = request.form.get('academic_year_id')

        try:
            new_fee = FeeType(
                name=name,
                amount=float(amount),
                academic_year_id=academic_year_id
            )
            db.session.add(new_fee)
            db.session.commit()
            flash('Jenis Biaya Master berhasil dibuat.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {e}', 'danger')

        return redirect(url_for('admin.manage_fee_types'))

    fees = FeeType.query.order_by(FeeType.id.desc()).all()
    years = AcademicYear.query.filter_by(is_active=True).all()
    return render_template('admin/finance/fee_types.html', fees=fees, years=years)


@admin_bp.route('/keuangan/biaya/edit/<int:fee_id>', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.ADMIN)
def edit_fee_type(fee_id):
    fee = FeeType.query.get_or_404(fee_id)
    years = AcademicYear.query.filter_by(is_active=True).all()

    if request.method == 'POST':
        fee.name = request.form.get('name')
        fee.amount = float(request.form.get('amount'))

        # Handle Tahun Ajaran (Bisa None/Null jika berlaku umum)
        year_id = request.form.get('academic_year_id')
        fee.academic_year_id = year_id if year_id else None

        try:
            db.session.commit()
            flash(f'Master Biaya "{fee.name}" berhasil diperbarui.', 'success')
            return redirect(url_for('admin.manage_fee_types'))
        except Exception as e:
            db.session.rollback()
            flash(f'Gagal update: {e}', 'danger')

    return render_template('admin/finance/edit_fee_type.html', fee=fee, years=years)


@admin_bp.route('/keuangan/generate/<int:fee_id>', methods=['POST'])
@login_required
@role_required(UserRole.ADMIN)
def generate_invoices(fee_id):
    # ... (Gunakan kode generate_invoices yang lama) ...
    pass


# =========================================================
# 8. MANAJEMEN PPDB (SAMA SEPERTI SEBELUMNYA)
# =========================================================

@admin_bp.route('/ppdb/pendaftar')
@login_required
@role_required(UserRole.ADMIN)
def ppdb_list():
    candidates = StudentCandidate.query.filter_by(is_deleted=False).order_by(StudentCandidate.created_at.desc()).all()
    return render_template('admin/ppdb/list.html', candidates=candidates)


@admin_bp.route('/ppdb/terima/<int:candidate_id>', methods=['POST'])
@login_required
@role_required(UserRole.ADMIN)
def accept_candidate(candidate_id):
    # ... (Gunakan kode accept_candidate yang lama) ...
    # Note: Pastikan import Gender, UserRole, dll sesuai
    pass

# =========================================================
# 8. MANAJEMEN USER
# =========================================================

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


# =========================================================
# 9. MANAJEMEN JADWAL PELAJARAN
# =========================================================

@admin_bp.route('/akademik/jadwal', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.ADMIN)
def manage_schedules():
    # Ambil parameter filter kelas dari URL (misal: ?class_id=1)
    selected_class_id = request.args.get('class_id', type=int)

    # Dropdown Data
    classes = ClassRoom.query.filter_by(is_deleted=False).all()
    subjects = Subject.query.filter_by(is_deleted=False).all()
    teachers = Teacher.query.filter_by(is_deleted=False).all()

    # Jika user mengirim Form Tambah Jadwal
    if request.method == 'POST':
        class_id = request.form.get('class_id')
        subject_id = request.form.get('subject_id')
        teacher_id = request.form.get('teacher_id')
        day = request.form.get('day')
        start_time_str = request.form.get('start_time')
        end_time_str = request.form.get('end_time')

        try:
            # Konversi String jam "07:00" menjadi object Time python
            start_time = datetime.strptime(start_time_str, '%H:%M').time()
            end_time = datetime.strptime(end_time_str, '%H:%M').time()

            new_schedule = Schedule(
                class_id=class_id,
                subject_id=subject_id,
                teacher_id=teacher_id,
                day=day,
                start_time=start_time,
                end_time=end_time
            )
            db.session.add(new_schedule)
            db.session.commit()
            flash('Jadwal berhasil ditambahkan.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Gagal menambah jadwal: {e}', 'danger')

        # Redirect kembali ke kelas yang sedang dipilih
        return redirect(url_for('admin.manage_schedules', class_id=class_id))

    # Query Jadwal untuk ditampilkan di tabel
    schedules = []
    selected_class = None

    if selected_class_id:
        selected_class = ClassRoom.query.get(selected_class_id)
        # Urutkan berdasarkan Hari (Senin-Jumat) dan Jam Mulai
        # Note: Sorting hari string (Senin, Selasa) di SQL mungkin tidak urut,
        # idealnya pakai Case/Enum, tapi untuk sekarang kita ambil raw dulu.
        schedules = Schedule.query.filter_by(class_id=selected_class_id) \
            .order_by(Schedule.day, Schedule.start_time).all()

        # Custom sort di python agar harinya urut Senin->Minggu
        days_order = {'Senin': 1, 'Selasa': 2, 'Rabu': 3, 'Kamis': 4, 'Jumat': 5, 'Sabtu': 6, 'Minggu': 7}
        schedules.sort(key=lambda x: (days_order.get(x.day, 8), x.start_time))

    return render_template('admin/academic/schedules.html',
                           classes=classes,
                           subjects=subjects,
                           teachers=teachers,
                           schedules=schedules,
                           selected_class=selected_class)


@admin_bp.route('/akademik/jadwal/hapus/<int:id>')
@login_required
@role_required(UserRole.ADMIN)
def delete_schedule(id):
    schedule = Schedule.query.get_or_404(id)
    class_id = schedule.class_id  # Simpan ID kelas untuk redirect

    db.session.delete(schedule)  # Hard delete karena jadwal sering berubah total
    db.session.commit()

    flash('Jadwal dihapus.', 'warning')
    return redirect(url_for('admin.manage_schedules', class_id=class_id))


# =========================================================
# 10. MANAJEMEN USER PUSAT (RESET PASSWORD ALL ROLES)
# =========================================================

@admin_bp.route('/users/manage', methods=['GET'])
@login_required
@role_required(UserRole.ADMIN)
def manage_users():
    """Halaman untuk melihat semua user dan reset password"""
    # Ambil semua user KECUALI Admin (untuk keamanan)
    users = User.query.filter(User.role != UserRole.ADMIN).order_by(User.role, User.username).all()
    return render_template('admin/users/manage.html', users=users)


@admin_bp.route('/users/reset-password-generic', methods=['POST'])
@login_required
@role_required(UserRole.ADMIN)
def generic_reset_password():
    """Route serbaguna untuk reset password via Modal"""
    user_id = request.form.get('user_id')
    new_password = request.form.get('new_password')

    user = User.query.get_or_404(user_id)

    # Validasi sederhana
    if not new_password or len(new_password) < 4:
        flash('Password minimal 4 karakter.', 'danger')
        return redirect(url_for('admin.manage_users'))

    try:
        user.set_password(new_password)
        # Opsional: Paksa user ganti password lagi saat login nanti
        user.must_change_password = False
        db.session.commit()

        flash(f'Password untuk {user.username} ({user.role.value}) berhasil diubah.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Gagal mereset password: {str(e)}', 'danger')

    return redirect(url_for('admin.manage_users'))
