from datetime import datetime, timedelta, date
import csv
from urllib.parse import urlsplit
from io import TextIOWrapper
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from sqlalchemy import func, or_, and_
from openpyxl import load_workbook
from app.extensions import db
from app.decorators import role_required
from app.services.majlis_enrollment_service import ensure_majlis_participant_acceptance, list_active_majlis_participants
from app.services.rumah_quran_service import (
    apply_rumah_quran_student_filter,
    assign_student_rumah_quran_class,
    ensure_rumah_quran_program_group,
    get_student_rumah_quran_classroom,
    is_rumah_quran_classroom,
    list_rumah_quran_classes,
    list_rumah_quran_students_for_class,
)
from app.services.bahasa_service import (
    apply_bahasa_student_filter,
    assign_student_bahasa_class,
    ensure_bahasa_program_group,
    get_student_bahasa_classroom,
    is_bahasa_classroom,
    list_bahasa_classes,
    list_bahasa_students_for_class,
)
from app.services.formal_service import (
    ensure_formal_program_group,
    list_formal_students_for_class,
    sync_student_formal_class_membership,
)
from app.services.staff_assignment_service import (
    cleanup_rumah_quran_subject_data,
    display_assignment_role,
    ensure_assignment_label_configs,
    sync_class_homeroom_assignment,
)
from app.services.ppdb_fee_service import (
    build_candidate_fee_drafts,
    get_ppdb_fee_template_admin_fields,
    save_ppdb_fee_templates,
)
from app.utils.timezone import local_day_bounds_utc_naive, local_now
from app.forms import StudentForm, FeeTypeForm  # Pastikan Anda punya form untuk Guru/Mapel nanti
from app.models import (
    # Base & Enums
    UserRole, Gender, PaymentStatus, RegistrationStatus, ProgramType, EducationLevel, AssignmentRole,
    # Users
    User, UserRoleAssignment, Student, Parent, Teacher, Staff, MajlisParticipant, BoardingGuardian,
    # Academic
    AcademicYear, ClassRoom, Subject, Schedule, Program, ProgramGroup, StaffAssignment,
    # Finance
    FeeType, Invoice, Transaction,
    # Student Related
    StudentClassHistory, Attendance, BoardingAttendance, Grade, ReportCard, StudentAttitude,
    Violation, BehaviorReport, TahfidzRecord, TahfidzSummary, RecitationRecord, TahfidzEvaluation,
    student_extracurriculars,
    # User/System Related
    Announcement, AnnouncementRead, NotificationQueue, AuditLog, BoardingDormitory,
    # Activities
    Extracurricular,
    # PPDB
    StudentCandidate,
    # Config
    AppConfig
)
from app.utils.nis import generate_nip, generate_nis
from app.utils.roles import validate_role_combination, role_label, ROLE_PRIORITY
from app.utils.money import to_rupiah_int
from app.utils.tenant import (
    classroom_in_tenant,
    resolve_tenant_id,
    scoped_classrooms_query,
)

admin_bp = Blueprint('admin', __name__)


def _current_tenant_id():
    return resolve_tenant_id(current_user)


def _tenant_teachers_query(tenant_id):
    return Teacher.query.join(User, Teacher.user_id == User.id).filter(
        Teacher.is_deleted.is_(False),
        User.tenant_id == tenant_id,
    )


def _safe_students_list_return_url(next_url, fallback_endpoint='admin.list_students'):
    fallback_url = url_for(fallback_endpoint)
    if not next_url:
        return fallback_url

    parsed = urlsplit(next_url)
    if parsed.scheme or parsed.netloc:
        return fallback_url

    allowed_paths = {url_for('admin.list_students'), url_for('staff.list_students')}
    if parsed.path not in allowed_paths:
        return fallback_url

    return next_url


def _infer_user_display_name(user):
    if user.teacher_profile and user.teacher_profile.full_name:
        return user.teacher_profile.full_name
    if user.staff_profile and user.staff_profile.full_name:
        return user.staff_profile.full_name
    if user.parent_profile and user.parent_profile.full_name:
        return user.parent_profile.full_name
    if user.student_profile and user.student_profile.full_name:
        return user.student_profile.full_name
    if user.majlis_profile and user.majlis_profile.full_name:
        return user.majlis_profile.full_name
    if user.boarding_guardian_profile and user.boarding_guardian_profile.full_name:
        return user.boarding_guardian_profile.full_name
    return user.username


def _infer_user_phone(user):
    if user.teacher_profile and user.teacher_profile.phone:
        return user.teacher_profile.phone
    if user.parent_profile and user.parent_profile.phone:
        return user.parent_profile.phone
    if user.boarding_guardian_profile and user.boarding_guardian_profile.phone:
        return user.boarding_guardian_profile.phone
    if user.majlis_profile and user.majlis_profile.phone:
        return user.majlis_profile.phone
    return None


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
    tenant_id = _current_tenant_id()
    if tenant_id is None:
        flash('Tenant default tidak ditemukan.', 'danger')
        return redirect(url_for('main.dashboard'))

    # 1. Hitung Total Siswa & Guru
    total_students = (
        Student.query.join(User, Student.user_id == User.id)
        .filter(
            Student.is_deleted.is_(False),
            User.tenant_id == tenant_id,
        )
        .count()
    )
    total_teachers = (
        Teacher.query.join(User, Teacher.user_id == User.id)
        .filter(
            Teacher.is_deleted.is_(False),
            User.tenant_id == tenant_id,
        )
        .count()
    )

    # 2. Hitung Pemasukan Hari Ini (PENTING!)
    start_utc, end_utc = local_day_bounds_utc_naive()
    income_today = (
        db.session.query(func.sum(Transaction.amount))
        .join(Invoice, Invoice.id == Transaction.invoice_id)
        .join(Student, Student.id == Invoice.student_id)
        .join(User, User.id == Student.user_id)
        .filter(
            Transaction.date >= start_utc,
            Transaction.date < end_utc,
            Invoice.is_deleted.is_(False),
            Student.is_deleted.is_(False),
            User.tenant_id == tenant_id,
        )
        .scalar()
        or 0
    )  # <--- "or 0" penting agar tidak None

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

    ensure_assignment_label_configs()
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
        tenant_id = _current_tenant_id()
        if tenant_id is None:
            flash('Tenant default tidak ditemukan.', 'danger')
            return redirect(url_for('admin.manage_teachers'))

        # 1. Buat User Login
        username = generate_nip()
        password = request.form.get('password') or "guru123"
        full_name = request.form.get('full_name')
        phone = request.form.get('phone')
        specialty = request.form.get('specialty')

        try:
            user = User(
                tenant_id=tenant_id,
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
            flash(f'Data Guru berhasil ditambahkan. NIP/Login: {username}', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {e}', 'danger')

        return redirect(url_for('admin.manage_teachers'))

    query = (request.args.get('q') or '').strip()
    tenant_id = _current_tenant_id()
    if tenant_id is None:
        flash('Tenant default tidak ditemukan.', 'danger')
        return render_template('admin/hr/teachers.html', teachers=[], query=query)

    teachers_query = Teacher.query.join(User, Teacher.user_id == User.id).filter(
        Teacher.is_deleted == False,
        User.tenant_id == tenant_id,
    )
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


def _display_assignment_note(note):
    if not note:
        return None
    normalized = note.strip()
    internal_prefixes = (
        'Legacy ',
        'Class homeroom sync',
        'Admin assignment',
    )
    if normalized.startswith(internal_prefixes):
        return None
    return normalized


@admin_bp.route('/sdm/guru/<int:id>/assignments')
@login_required
@role_required(UserRole.ADMIN)
def teacher_assignments(id):
    tenant_id = _current_tenant_id()

    if tenant_id is None:
        flash('Tenant default tidak ditemukan.', 'danger')
        return redirect(url_for('admin.manage_teachers'))

    teacher = (
        Teacher.query.join(User, Teacher.user_id == User.id)
        .filter(
            Teacher.id == id,
            Teacher.is_deleted.is_(False),
            User.tenant_id == tenant_id,
        )
        .first_or_404()
    )

    assignment_rows = (
        StaffAssignment.query
        .outerjoin(Program, StaffAssignment.program_id == Program.id)
        .outerjoin(ProgramGroup, StaffAssignment.group_id == ProgramGroup.id)
        .filter(
            StaffAssignment.tenant_id == tenant_id,
            StaffAssignment.person_id == teacher.person_id,
            StaffAssignment.is_deleted == False,
        )
        .order_by(
            StaffAssignment.end_date.isnot(None),
            Program.code.asc(),
            StaffAssignment.assignment_role.asc(),
            ProgramGroup.name.asc(),
            StaffAssignment.id.asc(),
        )
        .all()
    )

    grouped_assignments = []
    grouped_map = {}
    for assignment in assignment_rows:
        program = assignment.program
        if program is None:
            continue
        program_key = program.code
        if program_key not in grouped_map:
            grouped_map[program_key] = {
                'program_code': program.code,
                'program_name': program.name,
                'assignments': [],
                'active_count': 0,
            }
            grouped_assignments.append(grouped_map[program_key])

        row = {
            'id': assignment.id,
            'role': display_assignment_role(
                assignment.assignment_role,
                program.code,
            ),
            'group_name': assignment.group.name if assignment.group else '-',
            'academic_year': assignment.academic_year.name if assignment.academic_year else '-',
            'start_date': assignment.start_date,
            'end_date': assignment.end_date,
            'notes': _display_assignment_note(assignment.notes),
            'is_active': assignment.end_date is None,
        }
        grouped_map[program_key]['assignments'].append(row)
        if row['is_active']:
            grouped_map[program_key]['active_count'] += 1

    role_summary = {}
    for assignment in assignment_rows:
        if assignment.assignment_role:
            label = display_assignment_role(
                assignment.assignment_role,
                assignment.program.code if assignment.program else None,
            )
            role_summary[label] = role_summary.get(label, 0) + 1

    return render_template(
        'admin/hr/teacher_assignments.html',
        teacher=teacher,
        grouped_assignments=grouped_assignments,
        total_assignments=len(assignment_rows),
        role_summary=role_summary,
    )


@admin_bp.route('/sdm/guru/hapus/<int:id>', methods=['POST'])
@login_required
@role_required(UserRole.ADMIN)
def delete_teacher(id):
    tenant_id = _current_tenant_id()
    if tenant_id is None:
        flash('Tenant default tidak ditemukan.', 'danger')
        return redirect(url_for('admin.manage_teachers'))

    teacher = (
        Teacher.query.join(User, Teacher.user_id == User.id)
        .filter(
            Teacher.id == id,
            Teacher.is_deleted.is_(False),
            User.tenant_id == tenant_id,
        )
        .first_or_404()
    )
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
    tenant_id = _current_tenant_id()

    if tenant_id is None:
        flash('Tenant default tidak ditemukan.', 'danger')
        return redirect(url_for('admin.manage_teachers'))

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

        existing_user = User.query.filter_by(username=nip).first()
        if existing_user:
            skipped += 1
            if existing_user.tenant_id != tenant_id:
                errors.append(f'Baris {idx}: NIP {nip} sudah dipakai tenant lain.')
            else:
                errors.append(f'Baris {idx}: NIP {nip} sudah terdaftar.')
            continue

        try:
            with db.session.begin_nested():
                user = User(
                    tenant_id=tenant_id,
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
    tenant_id = _current_tenant_id()
    if tenant_id is None:
        flash('Tenant default tidak ditemukan.', 'danger')
        return redirect(url_for('admin.manage_teachers'))

    # Ambil data guru, return 404 jika tidak ada
    teacher = (
        Teacher.query.join(User, Teacher.user_id == User.id)
        .filter(
            Teacher.id == id,
            Teacher.is_deleted.is_(False),
            User.tenant_id == tenant_id,
        )
        .first_or_404()
    )

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
        tenant_id = _current_tenant_id()
        if tenant_id is None:
            flash('Tenant default tidak ditemukan.', 'danger')
            return redirect(url_for('admin.manage_staff'))

        username = (request.form.get('username') or '').strip()
        password = request.form.get('password') or "staff123"
        full_name = request.form.get('full_name')
        position = request.form.get('position') # Misal: Kepala TU, Staff Keuangan

        # Cek Username Kembar
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            if existing_user.tenant_id != tenant_id:
                flash('Username sudah digunakan tenant lain.', 'danger')
            else:
                flash('Username sudah digunakan.', 'danger')
        else:
            try:
                # 1. Buat User Login
                user = User(
                    tenant_id=tenant_id,
                    username=username,
                    email=f"{username}@sekolah.id",
                    role=UserRole.TU,
                )
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
    tenant_id = _current_tenant_id()
    if tenant_id is None:
        flash('Tenant default tidak ditemukan.', 'danger')
        return render_template('admin/hr/staff.html', staff_list=[], query=query)

    staff_query = Staff.query.filter_by(is_deleted=False).join(User, Staff.user_id == User.id).filter(
        User.tenant_id == tenant_id
    )
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
    tenant_id = _current_tenant_id()
    if tenant_id is None:
        flash('Tenant default tidak ditemukan.', 'danger')
        return redirect(url_for('admin.manage_staff'))

    staff = (
        Staff.query.join(User, Staff.user_id == User.id)
        .filter(
            Staff.id == id,
            Staff.is_deleted.is_(False),
            User.tenant_id == tenant_id,
        )
        .first_or_404()
    )
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
    tenant_id = _current_tenant_id()
    if tenant_id is None:
        flash('Tenant default tidak ditemukan.', 'danger')
        return redirect(url_for('admin.manage_staff'))

    # Ambil data staff, jika tidak ada return 404
    staff = (
        Staff.query.join(User, Staff.user_id == User.id)
        .filter(
            Staff.id == id,
            Staff.is_deleted.is_(False),
            User.tenant_id == tenant_id,
        )
        .first_or_404()
    )

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
    tenant_id = _current_tenant_id()
    if tenant_id is None:
        flash('Tenant default tidak ditemukan.', 'danger')
        return render_template(
            'admin/academic/classes.html',
            classes=[],
            class_student_counts={},
            teachers=[],
            query=(request.args.get('q') or '').strip(),
            ProgramType=ProgramType,
            EducationLevel=EducationLevel,
        )

    if request.method == 'POST':
        name = request.form.get('name')
        grade_level = request.form.get('grade_level')
        homeroom_id = request.form.get('homeroom_teacher_id', type=int)  # ID Guru
        program_type_raw = request.form.get('program_type')
        education_level_raw = request.form.get('education_level')

        if homeroom_id:
            homeroom_teacher = _tenant_teachers_query(tenant_id).filter(Teacher.id == homeroom_id).first()
            if homeroom_teacher is None:
                flash('Wali kelas tidak valid untuk tenant aktif.', 'warning')
                return redirect(url_for('admin.manage_classes'))

        program_type = ProgramType[program_type_raw] if program_type_raw else None
        education_level = EducationLevel[education_level_raw] if education_level_raw else None

        new_class = ClassRoom(
            name=name,
            grade_level=grade_level,
            homeroom_teacher_id=homeroom_id,
            program_type=program_type,
            education_level=education_level
        )
        db.session.add(new_class)
        db.session.flush()
        ensure_formal_program_group(new_class, tenant_id=tenant_id)
        ensure_rumah_quran_program_group(new_class, tenant_id=tenant_id)
        ensure_bahasa_program_group(new_class, tenant_id=tenant_id)
        sync_class_homeroom_assignment(new_class)
        db.session.commit()
        flash('Kelas berhasil dibuat.', 'success')
        return redirect(url_for('admin.manage_classes'))

    query = (request.args.get('q') or '').strip()
    classes_query = scoped_classrooms_query(tenant_id).outerjoin(Teacher, ClassRoom.homeroom_teacher_id == Teacher.id)
    if query:
        classes_query = classes_query.filter(
            or_(
                ClassRoom.name.ilike(f'%{query}%'),
                Teacher.full_name.ilike(f'%{query}%')
            )
        )

    classes = classes_query.order_by(ClassRoom.name.asc()).all()
    class_student_counts = {}
    for class_room in classes:
        if is_rumah_quran_classroom(class_room):
            class_student_counts[class_room.id] = len(list_rumah_quran_students_for_class(class_room.id))
        elif is_bahasa_classroom(class_room):
            class_student_counts[class_room.id] = len(list_bahasa_students_for_class(class_room.id))
        elif class_room.program_group_id:
            class_student_counts[class_room.id] = len(list_formal_students_for_class(class_room.id))
        else:
            class_student_counts[class_room.id] = len(class_room.students)
    teachers = _tenant_teachers_query(tenant_id).order_by(Teacher.full_name.asc()).all()  # Untuk dropdown
    return render_template(
        'admin/academic/classes.html',
        classes=classes,
        class_student_counts=class_student_counts,
        teachers=teachers,
        query=query,
        ProgramType=ProgramType,
        EducationLevel=EducationLevel
    )


@admin_bp.route('/sekolah/kelas/edit/<int:class_id>', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.ADMIN)
def edit_class(class_id):
    tenant_id = _current_tenant_id()
    if tenant_id is None:
        flash('Tenant default tidak ditemukan.', 'danger')
        return redirect(url_for('admin.manage_classes'))

    # Ambil data kelas atau 404 jika tidak ada
    class_room = scoped_classrooms_query(tenant_id).filter(ClassRoom.id == class_id).first_or_404()
    teachers = _tenant_teachers_query(tenant_id).order_by(Teacher.full_name.asc()).all()

    if request.method == 'POST':
        class_room.name = request.form.get('name')
        class_room.grade_level = request.form.get('grade_level')
        program_type_raw = request.form.get('program_type')
        education_level_raw = request.form.get('education_level')
        class_room.program_type = ProgramType[program_type_raw] if program_type_raw else None
        class_room.education_level = EducationLevel[education_level_raw] if education_level_raw else None

        # Handle Wali Kelas (Bisa Kosong/None)
        homeroom_id = request.form.get('homeroom_teacher_id', type=int)
        if homeroom_id:
            homeroom_teacher = _tenant_teachers_query(tenant_id).filter(Teacher.id == homeroom_id).first()
            if homeroom_teacher is None:
                flash('Wali kelas tidak valid untuk tenant aktif.', 'warning')
                return redirect(url_for('admin.edit_class', class_id=class_id))
        class_room.homeroom_teacher_id = homeroom_id if homeroom_id else None

        try:
            ensure_formal_program_group(class_room, tenant_id=tenant_id)
            ensure_rumah_quran_program_group(class_room, tenant_id=tenant_id)
            ensure_bahasa_program_group(class_room, tenant_id=tenant_id)
            sync_class_homeroom_assignment(class_room)
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


@admin_bp.route('/sekolah/kelas/hapus/<int:class_id>', methods=['POST'])
@login_required
@role_required(UserRole.ADMIN)
def delete_class(class_id):
    tenant_id = _current_tenant_id()
    if tenant_id is None:
        flash('Tenant default tidak ditemukan.', 'danger')
        return redirect(url_for('admin.manage_classes'))

    class_room = scoped_classrooms_query(tenant_id).filter(ClassRoom.id == class_id).first_or_404()

    if is_rumah_quran_classroom(class_room):
        student_count = len(list_rumah_quran_students_for_class(class_room.id))
    elif is_bahasa_classroom(class_room):
        student_count = len(list_bahasa_students_for_class(class_room.id))
    elif class_room.program_group_id:
        student_count = len(list_formal_students_for_class(class_room.id))
    else:
        student_count = Student.query.filter_by(
            current_class_id=class_room.id,
            is_deleted=False,
        ).count()

    majlis_parent_count = Parent.query.filter_by(
        majlis_class_id=class_room.id,
        is_deleted=False,
    ).count()
    majlis_participant_count = MajlisParticipant.query.filter_by(
        majlis_class_id=class_room.id,
        is_deleted=False,
    ).count()

    if student_count > 0 or majlis_parent_count > 0 or majlis_participant_count > 0:
        flash(
            (
                f'Kelas "{class_room.name}" tidak bisa dihapus karena masih memiliki peserta aktif '
                f'(siswa: {student_count}, peserta majlis: {majlis_participant_count}, wali majlis: {majlis_parent_count}).'
            ),
            'danger'
        )
        return redirect(url_for('admin.manage_classes'))

    try:
        schedules = Schedule.query.filter_by(class_id=class_room.id, is_deleted=False).all()
        for schedule in schedules:
            schedule.is_deleted = True

        class_room.homeroom_teacher_id = None
        sync_class_homeroom_assignment(class_room)
        class_room.is_deleted = True

        if class_room.program_group_id:
            program_group = ProgramGroup.query.filter_by(
                id=class_room.program_group_id,
                tenant_id=tenant_id,
                is_deleted=False,
            ).first()
            if program_group:
                program_group.is_active = False

        db.session.commit()
        flash(f'Kelas "{class_room.name}" berhasil dihapus.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Gagal menghapus kelas: {e}', 'danger')

    return redirect(url_for('admin.manage_classes'))

# =========================================================
# 5. MASTER KESISWAAN (EKSKUL)
# =========================================================

@admin_bp.route('/kesiswaan/ekskul', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.ADMIN)
def manage_extracurriculars():
    tenant_id = _current_tenant_id()
    if tenant_id is None:
        flash('Tenant default tidak ditemukan.', 'danger')
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        name = request.form.get('name')
        supervisor_id = request.form.get('supervisor_id', type=int)
        if supervisor_id and _tenant_teachers_query(tenant_id).filter(Teacher.id == supervisor_id).first() is None:
            flash('Pembina ekstrakurikuler tidak valid untuk tenant aktif.', 'warning')
            return redirect(url_for('admin.manage_extracurriculars'))

        ekskul = Extracurricular(name=name, supervisor_teacher_id=supervisor_id)
        db.session.add(ekskul)
        db.session.commit()
        flash('Ekstrakurikuler ditambahkan.', 'success')
        return redirect(url_for('admin.manage_extracurriculars'))

    ekskuls = Extracurricular.query.filter_by(is_deleted=False).all()
    teachers = _tenant_teachers_query(tenant_id).order_by(Teacher.full_name.asc()).all()
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
    tenant_id = _current_tenant_id()
    if tenant_id is None:
        flash('Tenant default tidak ditemukan.', 'danger')
        return redirect(url_for('admin.list_students'))

    form = StudentForm()

    # 1. Isi Pilihan Kelas (Wajib diisi dinamis setiap loading halaman)
    # Kita ambil ID dan Nama Kelas dari database
    form.class_id.choices = [(c.id, c.name) for c in scoped_classrooms_query(tenant_id).all()]

    # Jika belum ada kelas sama sekali, kasih opsi dummy biar gak error
    if not form.class_id.choices:
        form.class_id.choices = [(0, 'Belum ada kelas')]

    if form.validate_on_submit():
        try:
            if form.class_id.data and form.class_id.data != 0:
                selected_class = scoped_classrooms_query(tenant_id).filter(ClassRoom.id == form.class_id.data).first()
                if selected_class is None:
                    raise ValueError('Kelas tidak valid untuk tenant aktif.')

            nis = (form.nis.data or '').strip() or generate_nis()

            # A. CEK DUPLIKASI (Penting!)
            existing_student_user = User.query.filter_by(username=nis).first()
            if existing_student_user:
                if existing_student_user.tenant_id != tenant_id:
                    flash('NIS sudah dipakai tenant lain.', 'warning')
                else:
                    flash('NIS sudah terdaftar sebagai User.', 'warning')
                return render_template('admin/add_student.html', form=form)

            # B. BUAT USER SISWA
            student_user = User(
                tenant_id=tenant_id,
                username=nis,  # Login pakai NIS
                email=form.email.data,  # Pakai email dari inputan form
                role=UserRole.SISWA
            )
            student_user.set_password("123456")  # Default Pass
            db.session.add(student_user)
            db.session.flush()

            # C. BUAT PROFIL SISWA
            new_student = Student(
                user_id=student_user.id,
                nis=nis,
                full_name=form.full_name.data,
                gender=Gender[form.gender.data],  # Konversi string 'L'/'P' ke Enum
                place_of_birth=form.place_of_birth.data,
                date_of_birth=form.date_of_birth.data,
                current_class_id=form.class_id.data if form.class_id.data != 0 else None,
                address=form.address.data
            )
            db.session.add(new_student)

            # D. BUAT USER & PROFIL WALI
            # Cek dulu takutnya ortu sudah punya akun (kakak kelas)
            parent_user = User.query.filter_by(username=form.parent_phone.data).first()

            if not parent_user:
                # Buat Akun Wali Baru
                parent_user = User(
                    tenant_id=tenant_id,
                    username=form.parent_phone.data,  # Login pakai No WA
                    email=f"{form.parent_phone.data}@wali.sekolah.id",  # Email dummy
                    role=UserRole.WALI_MURID
                )
                parent_user.set_password(form.parent_phone.data)  # Default Pass = No WA
                db.session.add(parent_user)
                db.session.flush()
            elif parent_user.tenant_id != tenant_id:
                raise ValueError('Nomor HP wali sudah dipakai tenant lain.')

            if parent_user.tenant_id is None:
                parent_user.tenant_id = tenant_id

            if parent_user.role == UserRole.ADMIN:
                raise ValueError('Akun admin tidak boleh dipakai sebagai wali murid.')

            if not parent_user.has_role(UserRole.WALI_MURID):
                db.session.add(UserRoleAssignment(user_id=parent_user.id, role=UserRole.WALI_MURID))

            if parent_user.role != UserRole.WALI_MURID:
                parent_user.role = UserRole.WALI_MURID
            db.session.flush()

            # Buat/ambil profil wali
            parent_profile = parent_user.parent_profile
            if not parent_profile:
                parent_profile = Parent(
                    user_id=parent_user.id,
                    full_name=form.parent_name.data,
                    phone=form.parent_phone.data,
                    job=form.parent_job.data,
                    address=form.address.data
                )
                db.session.add(parent_profile)
                db.session.flush()

            # Sambungkan Siswa ke Wali
            new_student.parent_id = parent_profile.id

            sync_student_formal_class_membership(new_student, new_student.current_class_id)
            db.session.commit()
            flash(f'Siswa {form.full_name.data} berhasil ditambahkan. NIS/Login: {nis}', 'success')
            return redirect(url_for('admin.list_students'))

        except Exception as e:
            db.session.rollback()
            flash(f"Gagal menyimpan: {str(e)}", 'danger')

    return render_template('admin/add_student.html', form=form)


@admin_bp.route('/student/edit/<int:student_id>', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.ADMIN)
def edit_student(student_id):
    tenant_id = _current_tenant_id()
    if tenant_id is None:
        flash('Tenant default tidak ditemukan.', 'danger')
        return redirect(url_for('admin.list_students'))

    student = (
        Student.query.join(User, Student.user_id == User.id)
        .filter(
            Student.id == student_id,
            Student.is_deleted.is_(False),
            User.tenant_id == tenant_id,
        )
        .first_or_404()
    )
    return_url = _safe_students_list_return_url(
        request.args.get('next') or request.form.get('next'),
        fallback_endpoint='admin.list_students'
    )
    classes = scoped_classrooms_query(tenant_id).all()
    rumah_quran_classes = [class_room for class_room in list_rumah_quran_classes() if classroom_in_tenant(class_room, tenant_id)]
    rumah_quran_class = get_student_rumah_quran_classroom(student)
    bahasa_classes = [class_room for class_room in list_bahasa_classes() if classroom_in_tenant(class_room, tenant_id)]
    bahasa_class = get_student_bahasa_classroom(student)

    if request.method == 'POST':
        # Update Data Dasar
        student.full_name = request.form.get('full_name')
        student.nis = request.form.get('nis')
        student.nisn = (request.form.get('nisn') or '').strip() or None

        # Update Kelas
        cid = request.form.get('class_id')
        selected_class_id = int(cid) if cid else None
        student.current_class_id = selected_class_id
        rumah_quran_class_id = request.form.get('rumah_quran_class_id')
        rumah_quran_class_id = int(rumah_quran_class_id) if rumah_quran_class_id else None
        bahasa_class_id = request.form.get('bahasa_class_id')
        bahasa_class_id = int(bahasa_class_id) if bahasa_class_id else None

        selected_class = (
            scoped_classrooms_query(tenant_id).filter(ClassRoom.id == selected_class_id).first()
            if selected_class_id else None
        )
        if selected_class_id and selected_class is None:
            flash('Kelas tidak valid untuk tenant aktif.', 'warning')
            return redirect(url_for('admin.edit_student', student_id=student_id, next=return_url))
        if selected_class and selected_class.program_type in (ProgramType.RQDF_SORE, ProgramType.TAKHOSUS_TAHFIDZ):
            rumah_quran_class_id = selected_class.id
        if selected_class and selected_class.program_type == ProgramType.BAHASA:
            bahasa_class_id = selected_class.id

        # Update SPP Khusus
        spp = request.form.get('custom_spp')
        if spp:
            student.custom_spp_fee = int(''.join(filter(str.isdigit, spp)))
        else:
            student.custom_spp_fee = None

        try:
            sync_student_formal_class_membership(student, selected_class_id)
            assign_student_rumah_quran_class(student, rumah_quran_class_id)
            assign_student_bahasa_class(student, bahasa_class_id)
            student.save()  # Menggunakan method save() dari BaseModel
            flash('Data siswa diupdate.', 'success')
            return redirect(return_url)
        except Exception as e:
            db.session.rollback()
            flash(f'Gagal update data siswa: {e}', 'danger')

    return render_template('staff/edit_student.html',
                           student=student,
                           classes=classes,
                           rumah_quran_classes=rumah_quran_classes,
                           rumah_quran_class=rumah_quran_class,
                           bahasa_classes=bahasa_classes,
                           bahasa_class=bahasa_class,
                           return_url=return_url)


@admin_bp.route('/daftar-student')
@login_required
@role_required(UserRole.ADMIN)
def list_students():
    tenant_id = _current_tenant_id()
    if tenant_id is None:
        flash('Tenant default tidak ditemukan.', 'danger')
        return redirect(url_for('main.dashboard'))

    query = (request.args.get('q') or '').strip()
    query_majlis = (request.args.get('q_majlis') or '').strip()
    active_category = (request.args.get('category') or 'all').strip().lower()

    students_query = (
        Student.query.join(User, Student.user_id == User.id)
        .filter(
            Student.is_deleted.is_(False),
            User.tenant_id == tenant_id,
        )
        .outerjoin(ClassRoom, Student.current_class_id == ClassRoom.id)
    )

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
        students_query = apply_rumah_quran_student_filter(students_query, track='reguler')
    elif active_category == 'takhosus':
        students_query = apply_rumah_quran_student_filter(students_query, track='takhosus')
    elif active_category == 'bahasa':
        students_query = apply_bahasa_student_filter(students_query)

    students = students_query.order_by(Student.id.desc()).all()
    bahasa_class_map = {}
    if active_category == 'bahasa':
        bahasa_class_map = {
            student.id: get_student_bahasa_classroom(student)
            for student in students
        }
    majlis_participants = list_active_majlis_participants(search=query_majlis, tenant_id=tenant_id)

    return render_template(
        'student/list_students.html',
        students=students,
        bahasa_class_map=bahasa_class_map,
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
    tenant_id = _current_tenant_id()

    if tenant_id is None:
        flash('Tenant default tidak ditemukan.', 'danger')
        return redirect(url_for('admin.list_students'))

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

        existing_student_user = User.query.filter_by(username=nis).first()
        if existing_student_user:
            skipped += 1
            if existing_student_user.tenant_id != tenant_id:
                errors.append(f'Baris {idx}: NIS {nis} sudah dipakai tenant lain.')
            else:
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
            class_room = scoped_classrooms_query(tenant_id).filter(ClassRoom.name == class_name).first()
            if class_room:
                class_id = class_room.id

        try:
            with db.session.begin_nested():
                student_user = User(
                    tenant_id=tenant_id,
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
                        tenant_id=tenant_id,
                        username=parent_phone,
                        email=f"{parent_phone}@wali.sekolah.id",
                        role=UserRole.WALI_MURID
                    )
                    parent_user.set_password(parent_phone)
                    db.session.add(parent_user)
                    db.session.flush()
                elif parent_user.tenant_id != tenant_id:
                    raise ValueError('Nomor HP wali sudah terdaftar pada tenant lain.')

                if parent_user.tenant_id is None:
                    parent_user.tenant_id = tenant_id

                if not parent_user.has_role(UserRole.WALI_MURID):
                    db.session.add(UserRoleAssignment(user_id=parent_user.id, role=UserRole.WALI_MURID))

                if parent_user.role == UserRole.ADMIN:
                    raise ValueError('Akun admin tidak boleh dipakai sebagai wali murid.')

                if parent_user.role != UserRole.WALI_MURID:
                    parent_user.role = UserRole.WALI_MURID

                db.session.flush()

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
    tenant_id = _current_tenant_id()
    if tenant_id is None:
        flash('Tenant default tidak ditemukan.', 'danger')
        return redirect(url_for('admin.list_students'))

    student = (
        Student.query.join(User, Student.user_id == User.id)
        .filter(
            Student.id == id,
            Student.is_deleted.is_(False),
            User.tenant_id == tenant_id,
        )
        .first_or_404()
    )
    student.delete()  # Menggunakan method Soft Delete dari BaseModel
    flash('Data siswa berhasil dihapus (Soft Delete).', 'warning')
    return redirect(url_for('admin.list_students'))


# =========================================================
# 7. MANAJEMEN KEUANGAN
# =========================================================

@admin_bp.route('/keuangan/master-biaya', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.ADMIN)
def manage_fee_types():
    if request.method == 'POST':
        form_type = (request.form.get('form_type') or 'master_fee').strip()

        if form_type == 'ppdb_template':
            try:
                changed = save_ppdb_fee_templates(request.form)
                db.session.commit()
                if changed > 0:
                    flash(f'Template komponen biaya PPDB berhasil disimpan ({changed} perubahan).', 'success')
                else:
                    flash('Tidak ada perubahan pada template komponen biaya PPDB.', 'info')
            except Exception as e:
                db.session.rollback()
                flash(f'Gagal menyimpan template biaya PPDB: {e}', 'danger')
            return redirect(url_for('admin.manage_fee_types'))

        name = request.form.get('name')
        amount = request.form.get('amount')
        academic_year_id = request.form.get('academic_year_id', type=int)
        amount_rupiah = to_rupiah_int(amount, default=-1)

        if amount_rupiah <= 0:
            flash('Nominal biaya harus lebih dari 0.', 'warning')
            return redirect(url_for('admin.manage_fee_types'))

        try:
            new_fee = FeeType(
                name=name,
                amount=amount_rupiah,
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
    ppdb_fee_template_fields = get_ppdb_fee_template_admin_fields()
    return render_template(
        'admin/finance/fee_types.html',
        fees=fees,
        years=years,
        query=query,
        ppdb_fee_template_fields=ppdb_fee_template_fields,
    )


@admin_bp.route('/keuangan/biaya/edit/<int:fee_id>', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.ADMIN)
def edit_fee_type(fee_id):
    fee = FeeType.query.get_or_404(fee_id)
    years = AcademicYear.query.filter_by(is_active=True).all()

    if request.method == 'POST':
        fee.name = request.form.get('name')
        amount_rupiah = to_rupiah_int(request.form.get('amount'), default=-1)
        if amount_rupiah <= 0:
            flash('Nominal biaya harus lebih dari 0.', 'warning')
            return redirect(url_for('admin.edit_fee_type', fee_id=fee_id))
        fee.amount = amount_rupiah

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
    tenant_id = _current_tenant_id()
    if tenant_id is None:
        flash('Tenant default tidak ditemukan.', 'danger')
        return redirect(url_for('admin.manage_fee_types'))

    fee = FeeType.query.get_or_404(fee_id)
    students = (
        Student.query.join(User, Student.user_id == User.id)
        .filter(
            Student.is_deleted.is_(False),
            User.tenant_id == tenant_id,
        )
        .all()
    )

    count_success = 0
    bulan_tahun = local_now().strftime("%Y%m")
    due_date_default = local_now() + timedelta(days=10)
    is_monthly_fee = "SPP" in fee.name.upper() or "BULAN" in fee.name.upper()

    try:
        for student in students:
            candidate = getattr(student, "student_candidate", None)

            if candidate:
                if "RQDF" in fee.name.upper() and candidate.program_type.name != 'RQDF_SORE':
                    continue
                if "RQDF" not in fee.name.upper() and candidate.program_type.name == 'RQDF_SORE':
                    continue

            if Invoice.query.filter_by(student_id=student.id, fee_type_id=fee.id, is_deleted=False).first():
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
                total_amount=to_rupiah_int(nominal_final),
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
# 8. MANAJEMEN PPDB
# =========================================================

@admin_bp.route('/ppdb/pendaftar')
@login_required
@role_required(UserRole.ADMIN)
def ppdb_list():
    tenant_id = _current_tenant_id()
    if tenant_id is None:
        flash('Tenant default tidak ditemukan.', 'danger')
        return redirect(url_for('main.dashboard'))

    query = (request.args.get('q') or '').strip()
    candidates_query = StudentCandidate.query.filter_by(tenant_id=tenant_id, is_deleted=False)
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
    tenant_id = _current_tenant_id()
    if tenant_id is None:
        flash('Tenant default tidak ditemukan.', 'danger')
        return redirect(url_for('main.dashboard'))

    calon = StudentCandidate.query.filter_by(id=candidate_id, tenant_id=tenant_id, is_deleted=False).first_or_404()

    if calon.status == RegistrationStatus.ACCEPTED:
        flash('Siswa ini sudah diproses sebelumnya.', 'warning')
        return redirect(url_for('admin.ppdb_list'))

    try:
        # Jalur khusus peserta Majelis Ta'lim (tidak membuat akun siswa & tagihan)
        if calon.program_type == ProgramType.MAJLIS_TALIM:
            nomor_majelis = calon.personal_phone or calon.parent_phone
            if not nomor_majelis:
                raise ValueError('Nomor WhatsApp peserta Majelis tidak ditemukan.')

            majlis_user = User.query.filter_by(username=nomor_majelis).first()
            if not majlis_user:
                majlis_user = User(
                    tenant_id=tenant_id,
                    username=nomor_majelis,
                    email=f"majlis.{calon.id}@sekolah.id",
                    password_hash=generate_password_hash(nomor_majelis or "123456"),
                    role=UserRole.MAJLIS_PARTICIPANT,
                    must_change_password=True,
                )
                db.session.add(majlis_user)
                db.session.flush()
            elif majlis_user.tenant_id != tenant_id:
                raise ValueError('Akun Majelis lintas tenant tidak diizinkan.')

            ensure_majlis_participant_acceptance(
                user=majlis_user,
                full_name=calon.full_name,
                phone=nomor_majelis,
                address=calon.address,
                job=calon.personal_job,
            )

            calon.status = RegistrationStatus.ACCEPTED
            db.session.commit()
            flash(f"Peserta Majelis {calon.full_name} berhasil diterima.", 'success')
            return redirect(url_for('admin.ppdb_list'))

        # --- 1. PROSES AKUN ---
        nis_baru = generate_nis()

        # User Wali
        parent_phone = (calon.parent_phone or '').strip()
        if not parent_phone:
            raise ValueError('Nomor Telepon Orang Tua wajib diisi.')

        user_wali = User.query.filter_by(username=parent_phone).first()
        if not user_wali:
            user_wali = User(tenant_id=tenant_id, username=parent_phone, email=f"wali.{nis_baru}@sekolah.id",
                             password_hash=generate_password_hash(parent_phone or "123456"),
                             role=UserRole.WALI_MURID,
                             must_change_password=True)
            db.session.add(user_wali)
            db.session.flush()
        parent_profile = user_wali.parent_profile
        if not parent_profile:
            parent_profile = Parent(
                user_id=user_wali.id,
                full_name=calon.father_name or calon.mother_name or "Wali Murid",
                phone=parent_phone,
                job=calon.father_job,
                address=calon.address
            )
            db.session.add(parent_profile)
            db.session.flush()
        else:
            if not parent_profile.full_name:
                parent_profile.full_name = calon.father_name or calon.mother_name or "Wali Murid"
            if not parent_profile.phone:
                parent_profile.phone = parent_phone
            if not parent_profile.job and calon.father_job:
                parent_profile.job = calon.father_job
            if not parent_profile.address and calon.address:
                parent_profile.address = calon.address

        # User Siswa
        user_siswa = User(tenant_id=tenant_id, username=nis_baru, email=f"{nis_baru}@sekolah.id",
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
        tagihan_list = build_candidate_fee_drafts(calon)

        due_date = local_now() + timedelta(days=14)
        inv_prefix = f"INV/{local_now().strftime('%Y%m')}/{siswa_baru.id}"

        ctr = 1
        for item in tagihan_list:
            fee_type = FeeType.query.filter_by(name=item['nama']).first()
            if not fee_type:
                fee_type = FeeType(name=item['nama'], amount=to_rupiah_int(item['nominal']))
                db.session.add(fee_type)
                db.session.flush()

            new_inv = Invoice(
                invoice_number=f"{inv_prefix}/{ctr}",
                student_id=siswa_baru.id,
                fee_type_id=fee_type.id,
                total_amount=to_rupiah_int(item['nominal']),
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
    tenant_id = _current_tenant_id()
    if tenant_id is None:
        flash('Tenant default tidak ditemukan.', 'danger')
        return redirect(url_for('main.dashboard'))

    user = User.query.filter_by(id=user_id, tenant_id=tenant_id).first_or_404()

    if user.has_role(UserRole.ADMIN):
        flash('Tidak bisa mereset akun Admin lain dari sini.', 'danger')
        return redirect(url_for('main.dashboard'))

    try:
        new_password = "123456"  # Default fallback

        if user.has_role(UserRole.SISWA) and user.student_profile:
            new_password = user.student_profile.nis
        elif user.has_role(UserRole.WALI_MURID) and user.parent_profile:
            new_password = user.parent_profile.phone
        elif user.has_role(UserRole.WALI_ASRAMA) and user.boarding_guardian_profile:
            new_password = user.boarding_guardian_profile.phone or "123456"

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
    tenant_id = _current_tenant_id()
    if tenant_id is None:
        flash('Tenant default tidak ditemukan.', 'danger')
        return render_template(
            'admin/academic/schedules.html',
            classes=[],
            subjects=[],
            teachers=[],
            schedules=[],
            selected_class=None,
        )

    # Ambil parameter filter kelas dari URL (misal: ?class_id=1)
    selected_class_id = request.args.get('class_id', type=int)

    # Pastikan data lama "guru mapel Rumah Qur'an" ditutup.
    cleanup_stats = cleanup_rumah_quran_subject_data(tenant_id=tenant_id)
    if cleanup_stats["closed_assignments"] or cleanup_stats["deleted_schedules"]:
        db.session.commit()

    # Dropdown Data
    classes = (
        scoped_classrooms_query(tenant_id)
        .filter(
            or_(
                ClassRoom.program_type.is_(None),
                ~ClassRoom.program_type.in_([ProgramType.RQDF_SORE, ProgramType.TAKHOSUS_TAHFIDZ]),
            )
        )
        .all()
    )
    subjects = Subject.query.filter_by(is_deleted=False).all()
    teachers = _tenant_teachers_query(tenant_id).all()

    # Jika user mengirim Form Tambah Jadwal
    if request.method == 'POST':
        class_id = request.form.get('class_id', type=int)
        subject_id = request.form.get('subject_id', type=int)
        teacher_id = request.form.get('teacher_id', type=int)
        day = request.form.get('day')
        start_time_str = request.form.get('start_time')
        end_time_str = request.form.get('end_time')

        try:
            target_class = scoped_classrooms_query(tenant_id).filter(ClassRoom.id == class_id).first()
            if target_class is None:
                flash('Kelas tidak valid.', 'warning')
                return redirect(url_for('admin.manage_schedules'))
            if is_rumah_quran_classroom(target_class):
                flash("Kelas Rumah Qur'an tidak menggunakan jadwal mapel.", 'warning')
                return redirect(url_for('admin.manage_schedules', class_id=class_id))
            if _tenant_teachers_query(tenant_id).filter(Teacher.id == teacher_id).first() is None:
                flash('Guru tidak valid untuk tenant aktif.', 'warning')
                return redirect(url_for('admin.manage_schedules', class_id=class_id))

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
                Schedule.is_deleted.is_(False),
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
            clash_teacher = (
                Schedule.query.join(ClassRoom, Schedule.class_id == ClassRoom.id)
                .join(ProgramGroup, ClassRoom.program_group_id == ProgramGroup.id)
                .filter(
                    ProgramGroup.tenant_id == tenant_id,
                    Schedule.teacher_id == teacher_id,
                    Schedule.is_deleted.is_(False),
                    Schedule.day == day,
                    Schedule.start_time < end_time,
                    Schedule.end_time > start_time,
                )
                .first()
            )

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
        selected_class = scoped_classrooms_query(tenant_id).filter(ClassRoom.id == selected_class_id).first()
        if selected_class is None:
            flash('Kelas tidak valid.', 'warning')
            return redirect(url_for('admin.manage_schedules'))
        if selected_class and is_rumah_quran_classroom(selected_class):
            flash("Kelas Rumah Qur'an tidak menggunakan jadwal mapel.", 'warning')
            return redirect(url_for('admin.manage_schedules'))
        # Urutkan berdasarkan Hari (Senin-Jumat) dan Jam Mulai
        schedules = Schedule.query.filter_by(class_id=selected_class_id, is_deleted=False) \
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
    tenant_id = _current_tenant_id()
    if tenant_id is None:
        flash('Tenant default tidak ditemukan.', 'danger')
        return redirect(url_for('admin.manage_schedules'))

    schedule = (
        Schedule.query.join(ClassRoom, Schedule.class_id == ClassRoom.id)
        .join(ProgramGroup, ClassRoom.program_group_id == ProgramGroup.id)
        .filter(
            Schedule.id == id,
            Schedule.is_deleted.is_(False),
            ProgramGroup.tenant_id == tenant_id,
        )
        .first_or_404()
    )
    class_id = request.form.get('class_id', type=int) or schedule.class_id  # Fallback

    if schedule.class_room and is_rumah_quran_classroom(schedule.class_room):
        schedule.is_deleted = True
        db.session.commit()
        flash("Jadwal mapel kelas Rumah Qur'an telah dinonaktifkan.", 'warning')
        return redirect(url_for('admin.manage_schedules', class_id=schedule.class_id))

    # Ambil data dari form
    subject_id = request.form.get('subject_id', type=int)
    teacher_id = request.form.get('teacher_id', type=int)
    day = request.form.get('day')
    start_time_str = request.form.get('start_time')
    end_time_str = request.form.get('end_time')

    try:
        target_class = scoped_classrooms_query(tenant_id).filter(ClassRoom.id == class_id).first()
        if target_class is None:
            flash('Kelas tidak valid.', 'warning')
            return redirect(url_for('admin.manage_schedules', class_id=class_id))
        if is_rumah_quran_classroom(target_class):
            flash("Kelas Rumah Qur'an tidak menggunakan jadwal mapel.", 'warning')
            return redirect(url_for('admin.manage_schedules', class_id=class_id))
        if _tenant_teachers_query(tenant_id).filter(Teacher.id == teacher_id).first() is None:
            flash('Guru tidak valid untuk tenant aktif.', 'warning')
            return redirect(url_for('admin.manage_schedules', class_id=class_id))

        start_time = datetime.strptime(start_time_str, '%H:%M').time()
        end_time = datetime.strptime(end_time_str, '%H:%M').time()

        if start_time >= end_time:
            flash('Jam mulai harus lebih awal dari jam selesai!', 'warning')
            return redirect(url_for('admin.manage_schedules', class_id=class_id))

        # Cek Bentrok KELAS
        clash_class = Schedule.query.filter(
            Schedule.id != id,  # PENTING: Jangan cek jadwal diri sendiri
            Schedule.class_id == class_id,
            Schedule.is_deleted.is_(False),
            Schedule.day == day,
            Schedule.start_time < end_time,
            Schedule.end_time > start_time
        ).first()

        if clash_class:
            flash(f'Gagal Update! Bentrok dengan mapel lain di kelas ini.', 'danger')
            return redirect(url_for('admin.manage_schedules', class_id=class_id))

        # Cek Bentrok GURU
        clash_teacher = (
            Schedule.query.join(ClassRoom, Schedule.class_id == ClassRoom.id)
            .join(ProgramGroup, ClassRoom.program_group_id == ProgramGroup.id)
            .filter(
                Schedule.id != id,  # PENTING: Jangan cek jadwal diri sendiri
                ProgramGroup.tenant_id == tenant_id,
                Schedule.teacher_id == teacher_id,
                Schedule.is_deleted.is_(False),
                Schedule.day == day,
                Schedule.start_time < end_time,
                Schedule.end_time > start_time,
            )
            .first()
        )

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
    tenant_id = _current_tenant_id()
    if tenant_id is None:
        flash('Tenant default tidak ditemukan.', 'danger')
        return redirect(url_for('admin.manage_schedules'))

    schedule = (
        Schedule.query.join(ClassRoom, Schedule.class_id == ClassRoom.id)
        .join(ProgramGroup, ClassRoom.program_group_id == ProgramGroup.id)
        .filter(
            Schedule.id == id,
            Schedule.is_deleted.is_(False),
            ProgramGroup.tenant_id == tenant_id,
        )
        .first_or_404()
    )
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

    tenant_id = _current_tenant_id()
    if tenant_id is None:
        flash('Tenant default tidak ditemukan.', 'danger')
        return render_template(
            'admin/users/manage.html',
            users=[],
            query=query,
            role_filter=role_filter
        )

    # Ambil semua user tenant aktif KECUALI Admin (untuk keamanan)
    users_query = User.query.filter(
        User.tenant_id == tenant_id,
        User.role != UserRole.ADMIN,
        ~User.role_assignments.any(role=UserRole.ADMIN)
    )

    role_mapping = {
        'santri': UserRole.SISWA,
        'wali': UserRole.WALI_MURID,
        'wali_asrama': UserRole.WALI_ASRAMA,
        'guru': UserRole.GURU,
        'peserta_majlis': UserRole.MAJLIS_PARTICIPANT,
        'staff': UserRole.TU,
    }
    selected_role = role_mapping.get(role_filter)
    if selected_role:
        users_query = users_query.filter(
            or_(
                User.role == selected_role,
                User.role_assignments.any(role=selected_role)
            )
        )

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
            elif u.boarding_guardian_profile:
                owner_name = u.boarding_guardian_profile.full_name or ''

            if (
                keyword in (u.username or '').lower() or
                keyword in (u.role.value or '').lower() or
                any(keyword in rv.lower() for rv in u.all_role_values()) or
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


@admin_bp.route('/users/roles', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.ADMIN)
def manage_user_roles():
    tenant_id = _current_tenant_id()
    if tenant_id is None:
        flash('Tenant default tidak ditemukan.', 'danger')
        return redirect(url_for('admin.manage_users'))

    if request.method == 'POST':
        user_id = request.form.get('user_id', type=int)
        selected_roles_raw = request.form.getlist('roles')
        query = (request.form.get('q') or '').strip()

        user = User.query.filter_by(id=user_id, tenant_id=tenant_id).first_or_404()
        selected_roles = set()
        for item in selected_roles_raw:
            try:
                selected_roles.add(UserRole[item])
            except KeyError:
                pass

        is_valid, message = validate_role_combination(selected_roles)
        if not is_valid:
            flash(message, 'danger')
            return redirect(url_for('admin.manage_user_roles', q=query))

        # Pilih role utama berdasarkan prioritas global agar deterministik
        new_primary = None
        for role in ROLE_PRIORITY:
            if role in selected_roles:
                new_primary = role
                break

        if not new_primary:
            flash('Role utama tidak valid.', 'danger')
            return redirect(url_for('admin.manage_user_roles', q=query))

        # Validasi role yang wajib punya profil spesifik
        if UserRole.SISWA in selected_roles and not user.student_profile:
            flash('Role Santri hanya bisa diberikan ke user yang sudah memiliki profil siswa.', 'danger')
            return redirect(url_for('admin.manage_user_roles', q=query))

        if UserRole.WALI_MURID in selected_roles and not user.parent_profile:
            flash('Role Wali Murid hanya bisa diberikan ke user yang sudah memiliki profil wali murid.', 'danger')
            return redirect(url_for('admin.manage_user_roles', q=query))

        if UserRole.MAJLIS_PARTICIPANT in selected_roles and not user.majlis_profile:
            flash("Role Peserta Majlis hanya bisa diberikan ke user yang sudah memiliki profil peserta majlis.", 'danger')
            return redirect(url_for('admin.manage_user_roles', q=query))

        # Auto-provision profil untuk role operasional agar langsung muncul di modul terkait
        display_name = _infer_user_display_name(user)
        phone = _infer_user_phone(user)
        if UserRole.GURU in selected_roles and not user.teacher_profile:
            db.session.add(Teacher(
                user_id=user.id,
                full_name=display_name,
                phone=phone
            ))

        if UserRole.TU in selected_roles and not user.staff_profile:
            db.session.add(Staff(
                user_id=user.id,
                full_name=display_name,
                position='Staff'
            ))

        if UserRole.WALI_ASRAMA in selected_roles and not user.boarding_guardian_profile:
            db.session.add(BoardingGuardian(
                user_id=user.id,
                full_name=display_name,
                phone=phone
            ))

        user.role = new_primary

        # Sinkronkan role assignment tambahan (di luar role utama)
        target_extra_roles = selected_roles - {new_primary}
        existing_assignments = {assignment.role: assignment for assignment in user.role_assignments}

        for role, assignment in list(existing_assignments.items()):
            if role not in target_extra_roles:
                db.session.delete(assignment)

        for role in target_extra_roles:
            if role not in existing_assignments:
                db.session.add(UserRoleAssignment(user_id=user.id, role=role))

        db.session.commit()
        flash(f'Role user {user.username} berhasil diperbarui.', 'success')
        return redirect(url_for('admin.manage_user_roles', q=query))

    query = (request.args.get('q') or '').strip()
    users_query = User.query.filter(
        User.tenant_id == tenant_id,
        User.role != UserRole.ADMIN,
        ~User.role_assignments.any(role=UserRole.ADMIN)
    )
    if query:
        users_query = users_query.filter(
            or_(
                User.username.ilike(f'%{query}%'),
                User.email.ilike(f'%{query}%')
            )
        )

    users = users_query.order_by(User.username.asc()).all()
    return render_template(
        'admin/users/roles.html',
        users=users,
        query=query,
        all_roles=list(UserRole),
        role_label=role_label
    )


@admin_bp.route('/users/reset-password-generic', methods=['POST'])
@login_required
@role_required(UserRole.ADMIN)
def generic_reset_password():
    """Route serbaguna untuk reset password via Modal"""
    user_id = request.form.get('user_id')
    new_password = request.form.get('new_password')

    tenant_id = _current_tenant_id()
    if tenant_id is None:
        flash('Tenant default tidak ditemukan.', 'danger')
        return redirect(url_for('admin.manage_users'))

    user = User.query.filter_by(id=user_id, tenant_id=tenant_id).first_or_404()

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
