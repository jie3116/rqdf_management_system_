from datetime import datetime, timedelta, date
import csv
from io import TextIOWrapper
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from sqlalchemy import func, or_, and_
from openpyxl import load_workbook
from app.extensions import db
from app.decorators import role_required
from app.forms import StudentForm, FeeTypeForm  # Pastikan Anda punya form untuk Guru/Mapel nanti
from app.models import (
    # Base & Enums
    UserRole, Gender, PaymentStatus, RegistrationStatus, ProgramType, EducationLevel,
    # Users
    User, Student, Parent, Teacher, Staff, MajlisParticipant,
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
from app.utils.nis import generate_nis

admin_bp = Blueprint('admin', __name__)


def _iter_upload_rows(file):
    def _normalize_cell(value):
        if value is None:
            return ''
        if isinstance(value, datetime):
            return value.date().isoformat()
        if isinstance(value, date):
            return value.isoformat()
        if isinstance(value, float):
            if value.is_integer():
                return str(int(value))
            return str(value).strip()
        if isinstance(value, int):
            return str(value)
        return str(value).strip()

    filename = (file.filename or "").lower()
    if filename.endswith('.xlsx'):
        workbook = load_workbook(file, data_only=True)
        sheet = workbook.active
        rows = list(sheet.iter_rows(values_only=True))
        if not rows:
            return []
        headers = [str(cell).strip() if cell is not None else '' for cell in rows[0]]
        parsed = []
        for idx, row in enumerate(rows[1:], start=2):
            row_data = {}
            for col_idx, header in enumerate(headers):
                value = row[col_idx] if col_idx < len(row) else None
                row_data[header] = _normalize_cell(value)
            parsed.append((idx, row_data))
        return parsed

    wrapper = TextIOWrapper(file.stream, encoding='utf-8-sig')
    reader = csv.DictReader(wrapper)
    return [(idx, {k: (v.strip() if isinstance(v, str) else '' if v is None else str(v).strip())
                   for k, v in row.items()})
            for idx, row in enumerate(reader, start=2)]


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

    query = (request.args.get('q') or '').strip()
    configs_query = AppConfig.query
    if query:
        configs_query = configs_query.filter(
            or_(
                AppConfig.key.ilike(f'%{query}%'),
                AppConfig.value.ilike(f'%{query}%'),
                AppConfig.description.ilike(f'%{query}%')
            )
        )

    configs = configs_query.order_by(AppConfig.key.asc()).all()
    return render_template('admin/system/configs.html', configs=configs, query=query)


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

    query = (request.args.get('q') or '').strip()
    years_query = AcademicYear.query
    if query:
        years_query = years_query.filter(
            or_(
                AcademicYear.name.ilike(f'%{query}%'),
                AcademicYear.semester.ilike(f'%{query}%')
            )
        )

    years = years_query.order_by(AcademicYear.id.desc()).all()
    return render_template('admin/academic/years.html', years=years, query=query)


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

    query = (request.args.get('q') or '').strip()
    subjects_query = Subject.query.filter_by(is_deleted=False)
    if query:
        subjects_query = subjects_query.filter(
            or_(
                Subject.code.ilike(f'%{query}%'),
                Subject.name.ilike(f'%{query}%')
            )
        )

    subjects = subjects_query.order_by(Subject.name.asc()).all()
    return render_template('admin/academic/subjects.html', subjects=subjects, query=query)


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

    query = (request.args.get('q') or '').strip()
    teachers_query = Teacher.query.filter_by(is_deleted=False)
    if query:
        teachers_query = teachers_query.filter(
            or_(
                Teacher.full_name.ilike(f'%{query}%'),
                Teacher.nip.ilike(f'%{query}%'),
                Teacher.phone.ilike(f'%{query}%'),
                Teacher.specialty.ilike(f'%{query}%')
            )
        )

    teachers = teachers_query.order_by(Teacher.full_name.asc()).all()
    return render_template('admin/hr/teachers.html', teachers=teachers, query=query)


@admin_bp.route('/sdm/guru/hapus/<int:id>', methods=['POST'])
@login_required
@role_required(UserRole.ADMIN)
def delete_teacher(id):
    teacher = Teacher.query.get_or_404(id)
    teacher.delete()
    if teacher.user:
        teacher.user.delete()
    db.session.commit()
    flash('Data guru berhasil dihapus.', 'success')
    return redirect(url_for('admin.manage_teachers'))


@admin_bp.route('/sdm/guru/upload', methods=['POST'])
@login_required
@role_required(UserRole.ADMIN)
def upload_teachers():
    file = request.files.get('file')
    if not file or file.filename == '':
        flash('File belum dipilih.', 'warning')
        return redirect(url_for('admin.manage_teachers'))

    if not file.filename.lower().endswith(('.csv', '.xlsx')):
        flash('Format file harus CSV atau XLSX.', 'warning')
        return redirect(url_for('admin.manage_teachers'))

    created = 0
    skipped = 0
    errors = []

    for idx, row in _iter_upload_rows(file):
        nip = (row.get('nip') or row.get('NIP') or '').strip()
        full_name = (row.get('full_name') or row.get('nama') or row.get('nama_lengkap') or '').strip()
        specialty = (row.get('specialty') or row.get('mapel') or '').strip()
        phone = (row.get('phone') or row.get('no_hp') or row.get('whatsapp') or '').strip()
        password = (row.get('password') or '').strip() or "guru123"

        if not nip or not full_name:
            skipped += 1
            errors.append(f'Baris {idx}: NIP dan Nama wajib diisi.')
            continue

        if User.query.filter_by(username=nip).first():
            skipped += 1
            errors.append(f'Baris {idx}: NIP {nip} sudah terdaftar.')
            continue

        try:
            with db.session.begin_nested():
                user = User(
                    username=nip,
                    email=f"{nip}@sekolah.id",
                    password_hash=generate_password_hash(password),
                    role=UserRole.GURU,
                    must_change_password=True
                )
                db.session.add(user)
                db.session.flush()

                teacher = Teacher(
                    user_id=user.id,
                    nip=nip,
                    full_name=full_name,
                    phone=phone,
                    specialty=specialty
                )
                db.session.add(teacher)
                created += 1
        except Exception as exc:
            skipped += 1
            errors.append(f'Baris {idx}: {exc}')

    db.session.commit()
    flash(f'Upload guru selesai. Berhasil: {created}, Dilewati: {skipped}.', 'success')
    if errors:
        flash('Contoh error: ' + '; '.join(errors[:3]), 'warning')
    return redirect(url_for('admin.manage_teachers'))


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

    query = (request.args.get('q') or '').strip()
    staff_query = Staff.query.filter_by(is_deleted=False).outerjoin(User, Staff.user_id == User.id)
    if query:
        staff_query = staff_query.filter(
            or_(
                Staff.full_name.ilike(f'%{query}%'),
                Staff.position.ilike(f'%{query}%'),
                User.username.ilike(f'%{query}%')
            )
        )

    staff_list = staff_query.order_by(Staff.full_name.asc()).all()
    return render_template('admin/hr/staff.html', staff_list=staff_list, query=query)


@admin_bp.route('/sdm/staff/hapus/<int:id>', methods=['POST'])
@login_required
@role_required(UserRole.ADMIN)
def delete_staff(id):
    staff = Staff.query.get_or_404(id)
    staff.delete()
    if staff.user:
        staff.user.delete()
    db.session.commit()
    flash('Data staff berhasil dihapus.', 'success')
    return redirect(url_for('admin.manage_staff'))


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
        program_type_raw = request.form.get('program_type')
        education_level_raw = request.form.get('education_level')

        program_type = ProgramType[program_type_raw] if program_type_raw else None
        education_level = EducationLevel[education_level_raw] if education_level_raw else None

        new_class = ClassRoom(
            name=name,
            grade_level=grade_level,
            homeroom_teacher_id=homeroom_id if homeroom_id else None,
            program_type=program_type,
            education_level=education_level
        )
        db.session.add(new_class)
        db.session.commit()
        flash('Kelas berhasil dibuat.', 'success')
        return redirect(url_for('admin.manage_classes'))

    query = (request.args.get('q') or '').strip()
    classes_query = ClassRoom.query.filter_by(is_deleted=False).outerjoin(Teacher, ClassRoom.homeroom_teacher_id == Teacher.id)
    if query:
        classes_query = classes_query.filter(
            or_(
                ClassRoom.name.ilike(f'%{query}%'),
                Teacher.full_name.ilike(f'%{query}%')
            )
        )

    classes = classes_query.order_by(ClassRoom.name.asc()).all()
    teachers = Teacher.query.filter_by(is_deleted=False).all()  # Untuk dropdown
    return render_template(
        'admin/academic/classes.html',
        classes=classes,
        teachers=teachers,
        query=query,
        ProgramType=ProgramType,
        EducationLevel=EducationLevel
    )


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
        program_type_raw = request.form.get('program_type')
        education_level_raw = request.form.get('education_level')
        class_room.program_type = ProgramType[program_type_raw] if program_type_raw else None
        class_room.education_level = EducationLevel[education_level_raw] if education_level_raw else None

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

    return render_template(
        'admin/academic/edit_class.html',
        class_room=class_room,
        teachers=teachers,
        ProgramType=ProgramType,
        EducationLevel=EducationLevel
    )

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
# 6. MANAJEMEN SISWA
# =========================================================

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
            student_user.set_password("123456")  # Default Pass
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

    return render_template('staff/edit_student.html',
                           student=student,
                           classes=classes,)


@admin_bp.route('/daftar-student')
@login_required
@role_required(UserRole.ADMIN)
def list_students():
    query = (request.args.get('q') or '').strip()
    query_majlis = (request.args.get('q_majlis') or '').strip()
    active_category = (request.args.get('category') or 'all').strip().lower()

    students_query = Student.query.filter_by(is_deleted=False).outerjoin(ClassRoom, Student.current_class_id == ClassRoom.id)
    majlis_query = MajlisParticipant.query.filter_by(is_deleted=False)

    if query:
        students_query = students_query.outerjoin(Parent, Student.parent_id == Parent.id).filter(
            db.or_(
                Student.full_name.ilike(f'%{query}%'),
                Student.nis.ilike(f'%{query}%'),
                Parent.full_name.ilike(f'%{query}%'),
                Parent.phone.ilike(f'%{query}%'),
                ClassRoom.name.ilike(f'%{query}%')
            )
        )

    if query_majlis:
        majlis_query = majlis_query.outerjoin(ClassRoom, MajlisParticipant.majlis_class_id == ClassRoom.id).filter(
            db.or_(
                MajlisParticipant.full_name.ilike(f'%{query_majlis}%'),
                MajlisParticipant.phone.ilike(f'%{query_majlis}%'),
                ClassRoom.name.ilike(f'%{query_majlis}%')
            )
        )

    if active_category == 'sbq_sd':
        students_query = students_query.filter(
            or_(
                and_(
                    ClassRoom.program_type == ProgramType.SEKOLAH_FULLDAY,
                    ClassRoom.education_level == EducationLevel.SD
                ),
                and_(
                    ClassRoom.program_type.is_(None),
                    or_(
                        ClassRoom.name.ilike('%sd%'),
                        ClassRoom.grade_level.in_([1, 2, 3, 4, 5, 6])
                    )
                )
            )
        )
    elif active_category == 'sbq_smp':
        students_query = students_query.filter(
            or_(
                and_(
                    ClassRoom.program_type == ProgramType.SEKOLAH_FULLDAY,
                    ClassRoom.education_level == EducationLevel.SMP
                ),
                and_(
                    ClassRoom.program_type.is_(None),
                    or_(
                        ClassRoom.name.ilike('%smp%'),
                        ClassRoom.grade_level.in_([7, 8, 9])
                    )
                )
            )
        )
    elif active_category == 'sbq_sma':
        students_query = students_query.filter(
            or_(
                and_(
                    ClassRoom.program_type == ProgramType.SEKOLAH_FULLDAY,
                    ClassRoom.education_level == EducationLevel.SMA
                ),
                and_(
                    ClassRoom.program_type.is_(None),
                    or_(
                        ClassRoom.name.ilike('%sma%'),
                        ClassRoom.grade_level.in_([10, 11, 12])
                    )
                )
            )
        )
    elif active_category == 'reguler':
        students_query = students_query.filter(
            or_(
                ClassRoom.program_type == ProgramType.RQDF_SORE,
                and_(
                    ClassRoom.program_type.is_(None),
                    or_(
                        ClassRoom.name.ilike('%reguler%'),
                        ClassRoom.name.ilike('%rqdf%')
                    )
                )
            )
        )
    elif active_category == 'takhosus':
        students_query = students_query.filter(
            or_(
                ClassRoom.program_type == ProgramType.TAKHOSUS_TAHFIDZ,
                and_(
                    ClassRoom.program_type.is_(None),
                    ClassRoom.name.ilike('%takhosus%')
                )
            )
        )

    students = students_query.order_by(Student.id.desc()).all()
    majlis_participants = majlis_query.order_by(MajlisParticipant.id.desc()).all()

    return render_template(
        'student/list_students.html',
        students=students,
        majlis_participants=majlis_participants,
        query=query,
        query_majlis=query_majlis,
        active_category=active_category
    )


@admin_bp.route('/student/upload', methods=['POST'])
@login_required
@role_required(UserRole.ADMIN)
def upload_students():
    file = request.files.get('file')
    if not file or file.filename == '':
        flash('File belum dipilih.', 'warning')
        return redirect(url_for('admin.list_students'))

    if not file.filename.lower().endswith(('.csv', '.xlsx')):
        flash('Format file harus CSV atau XLSX.', 'warning')
        return redirect(url_for('admin.list_students'))

    created = 0
    skipped = 0
    errors = []

    for idx, row in _iter_upload_rows(file):
        nis = (row.get('nis') or row.get('NIS') or '').strip()
        full_name = (row.get('full_name') or row.get('nama') or row.get('nama_lengkap') or '').strip()
        gender_raw = (row.get('gender') or row.get('jk') or row.get('jenis_kelamin') or '').strip().upper()
        class_name = (row.get('class') or row.get('kelas') or row.get('class_name') or '').strip()
        place_of_birth = (row.get('place_of_birth') or row.get('tempat_lahir') or '').strip()
        date_of_birth = (row.get('date_of_birth') or row.get('tanggal_lahir') or '').strip()
        address = (row.get('address') or row.get('alamat') or '').strip()
        email = (row.get('email') or '').strip()
        parent_name = (row.get('parent_name') or row.get('nama_wali') or '').strip()
        parent_phone = (row.get('parent_phone') or row.get('no_wa') or row.get('no_hp_wali') or '').strip()
        parent_job = (row.get('parent_job') or row.get('pekerjaan_wali') or '').strip()

        if not full_name:
            skipped += 1
            errors.append(f'Baris {idx}: Nama wajib diisi.')
            continue

        if not parent_phone:
            skipped += 1
            errors.append(f'Baris {idx}: Nomor HP wali wajib diisi.')
            continue

        if not nis:
            nis = generate_nis()

        if User.query.filter_by(username=nis).first():
            skipped += 1
            errors.append(f'Baris {idx}: NIS {nis} sudah terdaftar.')
            continue

        if gender_raw not in {'L', 'P'}:
            skipped += 1
            errors.append(f'Baris {idx}: Gender harus L atau P.')
            continue

        try:
            dob = datetime.strptime(date_of_birth, '%Y-%m-%d').date()
        except ValueError:
            skipped += 1
            errors.append(f'Baris {idx}: Tanggal lahir harus YYYY-MM-DD.')
            continue

        class_id = None
        if class_name:
            class_room = ClassRoom.query.filter_by(name=class_name).first()
            if class_room:
                class_id = class_room.id

        try:
            with db.session.begin_nested():
                student_user = User(
                    username=nis,
                    email=email or f"{nis}@sekolah.id",
                    role=UserRole.SISWA
                )
                student_user.set_password("123456")
                db.session.add(student_user)
                db.session.flush()

                new_student = Student(
                    user_id=student_user.id,
                    nis=nis,
                    full_name=full_name,
                    gender=Gender[gender_raw],
                    place_of_birth=place_of_birth,
                    date_of_birth=dob,
                    current_class_id=class_id,
                    address=address
                )
                db.session.add(new_student)

                parent_user = User.query.filter_by(username=parent_phone).first()
                if not parent_user:
                    parent_user = User(
                        username=parent_phone,
                        email=f"{parent_phone}@wali.sekolah.id",
                        role=UserRole.WALI_MURID
                    )
                    parent_user.set_password(parent_phone)
                    db.session.add(parent_user)
                    db.session.flush()

                    parent_profile = Parent(
                        user_id=parent_user.id,
                        full_name=parent_name or "Wali Murid",
                        phone=parent_phone,
                        job=parent_job,
                        address=address
                    )
                    db.session.add(parent_profile)
                    db.session.flush()
                else:
                    parent_profile = parent_user.parent_profile
                    if not parent_profile:
                        parent_profile = Parent(
                            user_id=parent_user.id,
                            full_name=parent_name or "Wali Murid",
                            phone=parent_phone,
                            job=parent_job,
                            address=address
                        )
                        db.session.add(parent_profile)
                        db.session.flush()

                new_student.parent_id = parent_profile.id

                created += 1
        except Exception as exc:
            skipped += 1
            errors.append(f'Baris {idx}: {exc}')

    db.session.commit()
    flash(f'Upload siswa selesai. Berhasil: {created}, Dilewati: {skipped}.', 'success')
    if errors:
        flash('Contoh error: ' + '; '.join(errors[:3]), 'warning')
    return redirect(url_for('admin.list_students'))


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
        academic_year_id = request.form.get('academic_year_id', type=int)

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

    query = (request.args.get('q') or '').strip()
    fees_query = FeeType.query.outerjoin(AcademicYear, FeeType.academic_year_id == AcademicYear.id)
    if query:
        fees_query = fees_query.filter(
            or_(
                FeeType.name.ilike(f'%{query}%'),
                AcademicYear.name.ilike(f'%{query}%'),
                AcademicYear.semester.ilike(f'%{query}%')
            )
        )

    fees = fees_query.order_by(FeeType.id.desc()).all()
    years = AcademicYear.query.filter_by(is_active=True).all()
    return render_template('admin/finance/fee_types.html', fees=fees, years=years, query=query)


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
    """
    Admin berhak menerbitkan tagihan untuk seluruh siswa berdasarkan FeeType.
    Menggunakan logika yang sama seperti modul TU dengan guard agar tidak error
    jika relasi student_candidate belum tersedia.
    """
    fee = FeeType.query.get_or_404(fee_id)
    students = Student.query.all()

    count_success = 0
    bulan_tahun = datetime.now().strftime("%Y%m")
    due_date_default = datetime.now() + timedelta(days=10)
    is_monthly_fee = "SPP" in fee.name.upper() or "BULAN" in fee.name.upper()

    try:
        for student in students:
            candidate = getattr(student, "student_candidate", None)

            if candidate:
                if "RQDF" in fee.name.upper() and candidate.program_type.name != 'RQDF_SORE':
                    continue
                if "RQDF" not in fee.name.upper() and candidate.program_type.name == 'RQDF_SORE':
                    continue

            if Invoice.query.filter_by(student_id=student.id, fee_type_id=fee.id).first():
                continue

            nominal_final = fee.amount
            if is_monthly_fee and student.custom_spp_fee is not None:
                nominal_final = student.custom_spp_fee
            elif candidate and candidate.scholarship_category.name != 'NON_BEASISWA':
                nominal_final = fee.amount * 0.5

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

    return redirect(url_for('admin.manage_fee_types'))




# =========================================================
# 8. MANAJEMEN PPDB (SAMA SEPERTI SEBELUMNYA)
# =========================================================

@admin_bp.route('/ppdb/pendaftar')
@login_required
@role_required(UserRole.ADMIN)
def ppdb_list():
    query = (request.args.get('q') or '').strip()
    candidates_query = StudentCandidate.query.filter_by(is_deleted=False)
    if query:
        candidates_query = candidates_query.filter(
            or_(
                StudentCandidate.registration_no.ilike(f'%{query}%'),
                StudentCandidate.full_name.ilike(f'%{query}%'),
                StudentCandidate.parent_phone.ilike(f'%{query}%'),
                StudentCandidate.personal_phone.ilike(f'%{query}%')
            )
        )

    candidates = candidates_query.order_by(StudentCandidate.created_at.desc()).all()
    return render_template('admin/ppdb/list.html', candidates=candidates, query=query)


@admin_bp.route('/ppdb/terima/<int:candidate_id>', methods=['POST'])
@login_required
@role_required(UserRole.ADMIN)
def accept_candidate(candidate_id):
    calon = StudentCandidate.query.get_or_404(candidate_id)

    if calon.status == RegistrationStatus.ACCEPTED:
        flash('Siswa ini sudah diproses sebelumnya.', 'warning')
        return redirect(url_for('admin.ppdb_list'))

    try:
        # Jalur khusus peserta Majelis Ta'lim (tidak membuat akun siswa & tagihan)
        if calon.program_type == ProgramType.MAJLIS_TALIM:
            majlis_user = User.query.filter_by(username=calon.parent_phone).first()
            if not majlis_user:
                majlis_user = User(
                    username=calon.parent_phone,
                    email=f"majlis.{calon.id}@sekolah.id",
                    password_hash=generate_password_hash(calon.parent_phone or "123456"),
                    role=UserRole.MAJLIS_PARTICIPANT,
                    must_change_password=True,
                )
                db.session.add(majlis_user)
                db.session.flush()

            if not majlis_user.majlis_profile:
                db.session.add(
                    MajlisParticipant(
                        user_id=majlis_user.id,
                        full_name=calon.full_name,
                        phone=calon.parent_phone,
                        address=calon.address,
                        job=calon.personal_job,
                    )
                )

            calon.status = RegistrationStatus.ACCEPTED
            db.session.commit()
            flash(f"Peserta Majelis {calon.full_name} berhasil diterima.", 'success')
            return redirect(url_for('admin.ppdb_list'))

        # --- 1. PROSES AKUN ---
        nis_baru = generate_nis()

        # User Wali
        user_wali = User.query.filter_by(username=calon.parent_phone).first()
        if not user_wali:
            user_wali = User(username=calon.parent_phone, email=f"wali.{nis_baru}@sekolah.id",
                             password_hash=generate_password_hash(calon.parent_phone or "123456"),
                             role=UserRole.WALI_MURID,
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
                          password_hash=generate_password_hash(nis_baru), role=UserRole.SISWA,
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

    return redirect(url_for('admin.ppdb_list'))

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
            # 1. Konversi String jam "07:00" menjadi object Time python
            start_time = datetime.strptime(start_time_str, '%H:%M').time()
            end_time = datetime.strptime(end_time_str, '%H:%M').time()

            # 2. Validasi Logika Waktu (Mulai harus sebelum Selesai)
            if start_time >= end_time:
                flash('Jam mulai harus lebih awal dari jam selesai!', 'warning')
                return redirect(url_for('admin.manage_schedules', class_id=class_id))

            # ==========================================
            # 3. CEK BENTROK JADWAL (CLASH DETECTION)
            # ==========================================

            # A. Cek Bentrok KELAS (Kelas ini sudah dipakai belum di jam segitu?)
            clash_class = Schedule.query.filter(
                Schedule.class_id == class_id,
                Schedule.day == day,
                Schedule.start_time < end_time,  # Logic overlap: StartA < EndB
                Schedule.end_time > start_time  # Logic overlap: EndA > StartB
            ).first()

            if clash_class:
                # Ambil nama mapel agar pesan error jelas (menggunakan relationship 'subject')
                mapel_name = clash_class.subject.name if clash_class.subject else "Mapel Lain"
                flash(
                    f'Gagal! Bentrok dengan mapel "{mapel_name}" di kelas ini ({clash_class.start_time.strftime("%H:%M")} - {clash_class.end_time.strftime("%H:%M")}).',
                    'danger')
                return redirect(url_for('admin.manage_schedules', class_id=class_id))

            # B. Cek Bentrok GURU (Guru ini sedang mengajar di kelas lain tidak?)
            clash_teacher = Schedule.query.filter(
                Schedule.teacher_id == teacher_id,
                Schedule.day == day,
                Schedule.start_time < end_time,
                Schedule.end_time > start_time
            ).first()

            if clash_teacher:
                # Ambil nama kelas tempat guru tsb sedang mengajar
                other_class = clash_teacher.class_room.name if clash_teacher.class_room else "Kelas Lain"
                flash(f'Gagal! Guru tersebut sedang mengajar di "{other_class}" pada jam yang sama.', 'danger')
                return redirect(url_for('admin.manage_schedules', class_id=class_id))

            # ==========================================
            # 4. SIMPAN JIKA LOLOS VALIDASI
            # ==========================================
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
            flash(f'Gagal menambah jadwal (System Error): {e}', 'danger')

        # Redirect kembali ke kelas yang sedang dipilih
        return redirect(url_for('admin.manage_schedules', class_id=class_id))

    # Query Jadwal untuk ditampilkan di tabel
    schedules = []
    selected_class = None

    if selected_class_id:
        selected_class = ClassRoom.query.get(selected_class_id)
        # Urutkan berdasarkan Hari (Senin-Jumat) dan Jam Mulai
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


@admin_bp.route('/akademik/jadwal/edit/<int:id>', methods=['POST'])
@login_required
@role_required(UserRole.ADMIN)
def edit_schedule(id):
    schedule = Schedule.query.get_or_404(id)
    class_id = request.form.get('class_id') or schedule.class_id  # Fallback

    # Ambil data dari form
    subject_id = request.form.get('subject_id')
    teacher_id = request.form.get('teacher_id')
    day = request.form.get('day')
    start_time_str = request.form.get('start_time')
    end_time_str = request.form.get('end_time')

    try:
        start_time = datetime.strptime(start_time_str, '%H:%M').time()
        end_time = datetime.strptime(end_time_str, '%H:%M').time()

        if start_time >= end_time:
            flash('Jam mulai harus lebih awal dari jam selesai!', 'warning')
            return redirect(url_for('admin.manage_schedules', class_id=class_id))

        # Cek Bentrok KELAS
        clash_class = Schedule.query.filter(
            Schedule.id != id,  # PENTING: Jangan cek jadwal diri sendiri
            Schedule.class_id == class_id,
            Schedule.day == day,
            Schedule.start_time < end_time,
            Schedule.end_time > start_time
        ).first()

        if clash_class:
            flash(f'Gagal Update! Bentrok dengan mapel lain di kelas ini.', 'danger')
            return redirect(url_for('admin.manage_schedules', class_id=class_id))

        # Cek Bentrok GURU
        clash_teacher = Schedule.query.filter(
            Schedule.id != id,  # PENTING: Jangan cek jadwal diri sendiri
            Schedule.teacher_id == teacher_id,
            Schedule.day == day,
            Schedule.start_time < end_time,
            Schedule.end_time > start_time
        ).first()

        if clash_teacher:
            flash(f'Gagal Update! Guru sedang mengajar di kelas lain.', 'danger')
            return redirect(url_for('admin.manage_schedules', class_id=class_id))

        # UPDATE DATA
        schedule.subject_id = subject_id
        schedule.teacher_id = teacher_id
        schedule.day = day
        schedule.start_time = start_time
        schedule.end_time = end_time

        db.session.commit()
        flash('Jadwal berhasil diperbarui.', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Gagal update: {e}', 'danger')

    return redirect(url_for('admin.manage_schedules', class_id=class_id))


@admin_bp.route('/akademik/jadwal/hapus/<int:id>', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.ADMIN)
def delete_schedule(id):
    schedule = Schedule.query.get_or_404(id)
    class_id = schedule.class_id

    # Optional: Jika ingin strict hanya boleh POST
    if request.method == 'GET':
        # Bisa redirect balik atau tampilkan error
        pass

    db.session.delete(schedule)
    db.session.commit()

    flash('Jadwal dihapus.', 'success')  # Ubah jadi success warna hijau
    return redirect(url_for('admin.manage_schedules', class_id=class_id))


# =========================================================
# 10. MANAJEMEN USER PUSAT (RESET PASSWORD ALL ROLES)
# =========================================================

@admin_bp.route('/users/manage', methods=['GET'])
@login_required
@role_required(UserRole.ADMIN)
def manage_users():
    """Halaman untuk melihat semua user dan reset password"""
    query = (request.args.get('q') or '').strip()
    role_filter = (request.args.get('role') or 'all').strip().lower()

    # Ambil semua user KECUALI Admin (untuk keamanan)
    users_query = User.query.filter(User.role != UserRole.ADMIN)

    role_mapping = {
        'santri': UserRole.SISWA,
        'wali': UserRole.WALI_MURID,
        'guru': UserRole.GURU,
        'peserta_majlis': UserRole.MAJLIS_PARTICIPANT,
        'staff': UserRole.TU,
    }
    selected_role = role_mapping.get(role_filter)
    if selected_role:
        users_query = users_query.filter(User.role == selected_role)

    users = users_query.order_by(User.role, User.username).all()

    if query:
        keyword = query.lower()
        filtered_users = []
        for u in users:
            owner_name = ''
            if u.student_profile:
                owner_name = u.student_profile.full_name or ''
            elif u.parent_profile:
                owner_name = u.parent_profile.full_name or ''
            elif u.teacher_profile:
                owner_name = u.teacher_profile.full_name or ''
            elif u.majlis_profile:
                owner_name = u.majlis_profile.full_name or ''
            elif u.staff_profile:
                owner_name = u.staff_profile.full_name or ''

            if (
                keyword in (u.username or '').lower() or
                keyword in (u.role.value or '').lower() or
                keyword in owner_name.lower()
            ):
                filtered_users.append(u)
        users = filtered_users

    return render_template(
        'admin/users/manage.html',
        users=users,
        query=query,
        role_filter=role_filter
    )


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
