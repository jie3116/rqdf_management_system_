from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from app.decorators import role_required
from app.utils.timezone import local_today
from app.utils.tenant import resolve_tenant_id, scoped_dormitories_query
from app.extensions import db
from app.services.pesantren_service import list_students_for_dormitory, sync_student_dormitory_membership
from app.models import (
    User,
    UserRole,
    UserRoleAssignment,
    Gender,
    AttendanceStatus,
    Student,
    BoardingGuardian,
    BoardingDormitory,
    BoardingActivitySchedule,
    BoardingAttendance,
    BoardingHoliday,
    GroupType,
    Program,
    ProgramGroup,
)


boarding_bp = Blueprint('boarding', __name__, url_prefix='/boarding')
DAYS = ['Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu', 'Minggu']


def _current_tenant_id():
    return resolve_tenant_id(current_user)


def _tenant_guardians_query(tenant_id):
    return BoardingGuardian.query.join(User, BoardingGuardian.user_id == User.id).filter(
        BoardingGuardian.is_deleted.is_(False),
        User.is_deleted.is_(False),
        User.tenant_id == tenant_id,
        db.or_(
            User.role == UserRole.WALI_ASRAMA,
            User.role_assignments.any(role=UserRole.WALI_ASRAMA)
        ),
    )


def _tenant_students_query(tenant_id):
    return Student.query.join(User, Student.user_id == User.id).filter(
        Student.is_deleted.is_(False),
        User.is_deleted.is_(False),
        User.tenant_id == tenant_id,
    )


def _coerce_selected_ids(raw_values):
    ids = []
    for value in raw_values or []:
        try:
            ids.append(int(value))
        except (TypeError, ValueError):
            continue
    return ids


def _ensure_dormitory_program_group(dormitory, tenant_id):
    if dormitory is None or tenant_id is None:
        return None

    program = Program.query.filter_by(
        tenant_id=tenant_id,
        code='PESANTREN',
        is_deleted=False,
    ).first()
    if program is None:
        return None

    group = None
    if dormitory.program_group_id:
        group = ProgramGroup.query.filter_by(
            id=dormitory.program_group_id,
            tenant_id=tenant_id,
            is_deleted=False,
        ).first()

    if group is None:
        group = ProgramGroup.query.filter_by(
            tenant_id=tenant_id,
            program_id=program.id,
            academic_year_id=None,
            name=dormitory.name,
            is_deleted=False,
        ).first()

    if group is None:
        group = ProgramGroup(
            tenant_id=tenant_id,
            program_id=program.id,
            academic_year_id=None,
            name=dormitory.name,
        )
        db.session.add(group)

    group.name = dormitory.name
    group.group_type = GroupType.DORMITORY
    group.level_label = None
    group.gender_scope = dormitory.gender
    group.capacity = dormitory.capacity
    group.is_active = True
    db.session.flush()

    dormitory.program_group_id = group.id
    return group


def _schedule_in_tenant(schedule, tenant_dormitory_ids):
    if schedule is None:
        return False
    if schedule.dormitory_id and schedule.dormitory_id in tenant_dormitory_ids:
        return True
    selected_ids = {d.id for d in schedule.selected_dormitories}
    if selected_ids:
        return bool(selected_ids.intersection(tenant_dormitory_ids))
    return False


def _weekday_label(date_obj):
    return DAYS[date_obj.weekday()]


def _selected_days(schedule):
    if schedule.applies_all_days:
        return DAYS
    raw = (schedule.selected_days or '').strip()
    if raw:
        return [item.strip() for item in raw.split(',') if item.strip()]
    if schedule.day:
        return [schedule.day]
    return []


def _is_holiday(date_obj):
    return BoardingHoliday.query.filter_by(date=date_obj, is_deleted=False).first() is not None


def _schedule_applies_to_dormitory(schedule, dormitory_id):
    selected_ids = {d.id for d in schedule.selected_dormitories}
    if schedule.applies_all_dormitories:
        if selected_ids:
            return dormitory_id in selected_ids
        if schedule.dormitory_id:
            return schedule.dormitory_id == dormitory_id
        return False

    if selected_ids:
        return dormitory_id in selected_ids

    # backward-compatible untuk data lama per-asrama
    return schedule.dormitory_id == dormitory_id


def _effective_schedules_for(dormitory_id, date_obj):
    day_name = _weekday_label(date_obj)
    holiday = _is_holiday(date_obj)

    schedules = BoardingActivitySchedule.query.filter_by(is_active=True, is_deleted=False).order_by(
        BoardingActivitySchedule.start_time.asc()
    ).all()

    result = []
    for schedule in schedules:
        if not _schedule_applies_to_dormitory(schedule, dormitory_id):
            continue
        if day_name not in _selected_days(schedule):
            continue
        if holiday and schedule.exclude_national_holidays:
            continue
        result.append(schedule)
    return result


@boarding_bp.route('/admin/wali-asrama', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.ADMIN)
def manage_guardians():
    tenant_id = _current_tenant_id()
    if tenant_id is None:
        flash('Tenant default tidak ditemukan.', 'danger')
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        password = (request.form.get('password') or '').strip() or '123456'
        full_name = (request.form.get('full_name') or '').strip()
        phone = (request.form.get('phone') or '').strip()

        if not username or not full_name:
            flash('Username dan nama wali asrama wajib diisi.', 'warning')
            return redirect(url_for('boarding.manage_guardians'))

        existing_user = User.query.filter_by(username=username).first()

        try:
            if not existing_user:
                existing_user = User(
                    tenant_id=tenant_id,
                    username=username,
                    email=f'{username}@asrama.sekolah.id',
                    role=UserRole.WALI_ASRAMA,
                    must_change_password=True,
                )
                existing_user.set_password(password)
                db.session.add(existing_user)
                db.session.flush()
            elif existing_user.tenant_id != tenant_id:
                flash('Username sudah digunakan tenant lain.', 'danger')
                return redirect(url_for('boarding.manage_guardians'))
            elif not existing_user.has_role(UserRole.WALI_ASRAMA):
                db.session.add(UserRoleAssignment(
                    user_id=existing_user.id,
                    role=UserRole.WALI_ASRAMA
                ))

            if existing_user.tenant_id is None:
                existing_user.tenant_id = tenant_id

            profile = existing_user.boarding_guardian_profile
            if not profile:
                profile = BoardingGuardian(
                    user_id=existing_user.id,
                    full_name=full_name,
                    phone=phone or None,
                )
                db.session.add(profile)
            else:
                profile.full_name = full_name
                profile.phone = phone or None

            db.session.commit()
            flash('Akun wali asrama berhasil disimpan.', 'success')
        except Exception as exc:
            db.session.rollback()
            flash(f'Gagal menyimpan wali asrama: {exc}', 'danger')

        return redirect(url_for('boarding.manage_guardians'))

    query = (request.args.get('q') or '').strip()
    guardians_query = _tenant_guardians_query(tenant_id)
    if query:
        guardians_query = guardians_query.filter(
            db.or_(
                BoardingGuardian.full_name.ilike(f'%{query}%'),
                BoardingGuardian.phone.ilike(f'%{query}%'),
                User.username.ilike(f'%{query}%')
            )
        )

    guardians = guardians_query.order_by(BoardingGuardian.full_name.asc()).all()
    return render_template('boarding/admin_guardians.html', guardians=guardians, query=query)


@boarding_bp.route('/admin/asrama', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.ADMIN)
def manage_dormitories():
    tenant_id = _current_tenant_id()
    if tenant_id is None:
        flash('Tenant default tidak ditemukan.', 'danger')
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        action = (request.form.get('action') or '').strip()
        tenant_dormitory_ids = {
            dormitory.id
            for dormitory in scoped_dormitories_query(tenant_id).all()
        }
        tenant_guardian_user_ids = {
            guardian.user_id
            for guardian in _tenant_guardians_query(tenant_id).all()
            if guardian.user_id
        }

        if action == 'create_dormitory':
            name = (request.form.get('name') or '').strip()
            guardian_user_id = request.form.get('guardian_user_id', type=int)
            gender_raw = (request.form.get('gender') or '').strip()
            capacity = request.form.get('capacity', type=int)
            description = (request.form.get('description') or '').strip()

            if not name:
                flash('Nama asrama wajib diisi.', 'warning')
                return redirect(url_for('boarding.manage_dormitories'))
            if not guardian_user_id:
                flash('Wali asrama wajib dipilih.', 'warning')
                return redirect(url_for('boarding.manage_dormitories'))
            if guardian_user_id not in tenant_guardian_user_ids:
                flash('Wali asrama tidak valid untuk tenant aktif.', 'warning')
                return redirect(url_for('boarding.manage_dormitories'))

            if scoped_dormitories_query(tenant_id).filter(BoardingDormitory.name == name).first():
                flash('Nama asrama sudah digunakan.', 'warning')
                return redirect(url_for('boarding.manage_dormitories'))

            dormitory = BoardingDormitory(
                name=name,
                guardian_user_id=guardian_user_id,
                gender=Gender[gender_raw] if gender_raw else None,
                capacity=capacity,
                description=description or None,
            )
            db.session.add(dormitory)
            db.session.flush()
            _ensure_dormitory_program_group(dormitory, tenant_id)
            db.session.commit()
            flash('Data asrama berhasil ditambahkan.', 'success')
            return redirect(url_for('boarding.manage_dormitories'))

        if action == 'update_dormitory':
            dormitory_id = request.form.get('dormitory_id', type=int)
            dormitory = scoped_dormitories_query(tenant_id).filter(BoardingDormitory.id == dormitory_id).first_or_404()

            guardian_user_id = request.form.get('guardian_user_id', type=int)
            if guardian_user_id and guardian_user_id not in tenant_guardian_user_ids:
                flash('Wali asrama tidak valid untuk tenant aktif.', 'warning')
                return redirect(url_for('boarding.manage_dormitories'))

            dormitory.guardian_user_id = guardian_user_id
            dormitory.capacity = request.form.get('capacity', type=int)
            dormitory.description = (request.form.get('description') or '').strip() or None
            gender_raw = (request.form.get('gender') or '').strip()
            dormitory.gender = Gender[gender_raw] if gender_raw else None
            _ensure_dormitory_program_group(dormitory, tenant_id)

            db.session.commit()
            flash(f'Asrama {dormitory.name} berhasil diperbarui.', 'success')
            return redirect(url_for('boarding.manage_dormitories'))

        if action == 'assign_students':
            query_value = (request.form.get('q') or '').strip()
            submitted_assignments = {}
            for key, value in request.form.items():
                if not key.startswith('dormitory_'):
                    continue
                student_id_raw = key.replace('dormitory_', '', 1).strip()
                try:
                    student_id = int(student_id_raw)
                except ValueError:
                    continue
                value = (value or '').strip()
                submitted_assignments[student_id] = int(value) if value else None

            if not submitted_assignments:
                flash('Tidak ada data penempatan yang dikirim.', 'warning')
                return redirect(url_for('boarding.manage_dormitories', q=query_value or None))

            submitted_dormitory_ids = {
                dormitory_id
                for dormitory_id in submitted_assignments.values()
                if dormitory_id is not None
            }
            invalid_dormitory_ids = submitted_dormitory_ids - tenant_dormitory_ids
            if invalid_dormitory_ids:
                flash('Terdapat asrama yang bukan milik tenant aktif.', 'danger')
                return redirect(url_for('boarding.manage_dormitories', q=query_value or None))

            students = _tenant_students_query(tenant_id).filter(Student.id.in_(submitted_assignments.keys())).all()
            updated = 0
            for student in students:
                new_dormitory_id = submitted_assignments.get(student.id)
                if student.boarding_dormitory_id != new_dormitory_id:
                    student.boarding_dormitory_id = new_dormitory_id
                    sync_student_dormitory_membership(student, new_dormitory_id, tenant_id=tenant_id)
                    updated += 1

            db.session.commit()
            flash(f'Penempatan asrama siswa diperbarui ({updated} perubahan).', 'success')
            return redirect(url_for('boarding.manage_dormitories', q=query_value or None))

    student_query = (request.args.get('q') or '').strip()
    students_query = _tenant_students_query(tenant_id)
    if student_query:
        students_query = students_query.filter(
            db.or_(
                Student.full_name.ilike(f'%{student_query}%'),
                Student.nis.ilike(f'%{student_query}%')
            )
        )

    guardians = _tenant_guardians_query(tenant_id).order_by(BoardingGuardian.full_name.asc()).all()
    dormitories = scoped_dormitories_query(tenant_id).order_by(BoardingDormitory.name.asc()).all()
    dormitory_student_counts = {
        dormitory.id: len(list_students_for_dormitory(dormitory.id, tenant_id=tenant_id))
        for dormitory in dormitories
    }
    students = students_query.order_by(Student.full_name.asc()).all()

    return render_template(
        'boarding/admin_dormitories.html',
        dormitories=dormitories,
        dormitory_student_counts=dormitory_student_counts,
        guardians=guardians,
        students=students,
        query=student_query,
        Gender=Gender,
    )


@boarding_bp.route('/admin/jadwal', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.ADMIN)
def manage_schedules():
    tenant_id = _current_tenant_id()
    if tenant_id is None:
        flash('Tenant default tidak ditemukan.', 'danger')
        return redirect(url_for('main.dashboard'))

    selected_dormitory_id = request.args.get('dormitory_id', type=int)
    dormitories = scoped_dormitories_query(tenant_id).order_by(BoardingDormitory.name.asc()).all()
    tenant_dormitory_ids = {dormitory.id for dormitory in dormitories}
    if selected_dormitory_id and selected_dormitory_id not in tenant_dormitory_ids:
        flash('Asrama tidak valid untuk tenant aktif.', 'warning')
        return redirect(url_for('boarding.manage_schedules'))

    if request.method == 'POST':
        action = (request.form.get('action') or '').strip()

        if action == 'add_schedule':
            activity_name = (request.form.get('activity_name') or '').strip()
            start_time_str = (request.form.get('start_time') or '').strip()
            end_time_str = (request.form.get('end_time') or '').strip()
            applies_all_dormitories = request.form.get('applies_all_dormitories') == 'on'
            applies_all_days = request.form.get('applies_all_days') == 'on'
            selected_dormitory_ids = _coerce_selected_ids(request.form.getlist('selected_dormitories'))
            selected_dormitory_ids = [dormitory_id for dormitory_id in selected_dormitory_ids if dormitory_id in tenant_dormitory_ids]
            selected_days = request.form.getlist('selected_days')
            exclude_national_holidays = request.form.get('exclude_national_holidays') == 'on'

            if not activity_name or not start_time_str or not end_time_str:
                flash('Nama kegiatan dan jam wajib diisi.', 'warning')
                return redirect(url_for('boarding.manage_schedules', dormitory_id=selected_dormitory_id))

            if not applies_all_dormitories and not selected_dormitory_ids:
                flash('Pilih minimal satu asrama jika tidak berlaku untuk semua asrama.', 'warning')
                return redirect(url_for('boarding.manage_schedules', dormitory_id=selected_dormitory_id))
            if applies_all_dormitories and not dormitories:
                flash('Belum ada asrama pada tenant aktif.', 'warning')
                return redirect(url_for('boarding.manage_schedules', dormitory_id=selected_dormitory_id))

            if not applies_all_days and not selected_days:
                flash('Pilih minimal satu hari jika tidak berlaku untuk semua hari.', 'warning')
                return redirect(url_for('boarding.manage_schedules', dormitory_id=selected_dormitory_id))

            try:
                start_time = datetime.strptime(start_time_str, '%H:%M').time()
                end_time = datetime.strptime(end_time_str, '%H:%M').time()
            except ValueError:
                flash('Format waktu tidak valid.', 'warning')
                return redirect(url_for('boarding.manage_schedules', dormitory_id=selected_dormitory_id))

            if start_time >= end_time:
                flash('Jam mulai harus lebih awal dari jam selesai.', 'warning')
                return redirect(url_for('boarding.manage_schedules', dormitory_id=selected_dormitory_id))

            schedule = BoardingActivitySchedule(
                activity_name=activity_name,
                start_time=start_time,
                end_time=end_time,
                is_active=True,
                applies_all_dormitories=applies_all_dormitories,
                applies_all_days=applies_all_days,
                selected_days=None if applies_all_days else ','.join(selected_days),
                exclude_national_holidays=exclude_national_holidays
            )
            db.session.add(schedule)
            db.session.flush()

            if not applies_all_dormitories:
                selected_dormitories = [dormitory for dormitory in dormitories if dormitory.id in selected_dormitory_ids]
                schedule.selected_dormitories = selected_dormitories
                schedule.dormitory_id = selected_dormitories[0].id if selected_dormitories else None  # fallback legacy
            else:
                schedule.selected_dormitories = dormitories
                schedule.dormitory_id = dormitories[0].id if dormitories else None

            if not applies_all_days and selected_days:
                schedule.day = selected_days[0]  # fallback legacy

            db.session.commit()
            flash('Template jadwal kegiatan boarding berhasil ditambahkan.', 'success')
            return redirect(url_for('boarding.manage_schedules', dormitory_id=selected_dormitory_id))

        if action == 'update_schedule':
            schedule_id = request.form.get('schedule_id', type=int)
            schedule = BoardingActivitySchedule.query.get_or_404(schedule_id)
            if not _schedule_in_tenant(schedule, tenant_dormitory_ids):
                flash('Jadwal tidak valid untuk tenant aktif.', 'danger')
                return redirect(url_for('boarding.manage_schedules', dormitory_id=selected_dormitory_id))

            activity_name = (request.form.get('activity_name') or '').strip()
            start_time_str = (request.form.get('start_time') or '').strip()
            end_time_str = (request.form.get('end_time') or '').strip()
            applies_all_dormitories = request.form.get('applies_all_dormitories') == 'on'
            applies_all_days = request.form.get('applies_all_days') == 'on'
            selected_dormitory_ids = _coerce_selected_ids(request.form.getlist('selected_dormitories'))
            selected_dormitory_ids = [dormitory_id for dormitory_id in selected_dormitory_ids if dormitory_id in tenant_dormitory_ids]
            selected_days = request.form.getlist('selected_days')
            exclude_national_holidays = request.form.get('exclude_national_holidays') == 'on'

            if not activity_name or not start_time_str or not end_time_str:
                flash('Nama kegiatan dan jam wajib diisi saat update.', 'warning')
                return redirect(url_for('boarding.manage_schedules', dormitory_id=selected_dormitory_id))

            if not applies_all_dormitories and not selected_dormitory_ids:
                flash('Pilih minimal satu asrama jika tidak berlaku untuk semua asrama.', 'warning')
                return redirect(url_for('boarding.manage_schedules', dormitory_id=selected_dormitory_id))
            if applies_all_dormitories and not dormitories:
                flash('Belum ada asrama pada tenant aktif.', 'warning')
                return redirect(url_for('boarding.manage_schedules', dormitory_id=selected_dormitory_id))

            if not applies_all_days and not selected_days:
                flash('Pilih minimal satu hari jika tidak berlaku untuk semua hari.', 'warning')
                return redirect(url_for('boarding.manage_schedules', dormitory_id=selected_dormitory_id))

            try:
                start_time = datetime.strptime(start_time_str, '%H:%M').time()
                end_time = datetime.strptime(end_time_str, '%H:%M').time()
            except ValueError:
                flash('Format waktu tidak valid.', 'warning')
                return redirect(url_for('boarding.manage_schedules', dormitory_id=selected_dormitory_id))

            if start_time >= end_time:
                flash('Jam mulai harus lebih awal dari jam selesai.', 'warning')
                return redirect(url_for('boarding.manage_schedules', dormitory_id=selected_dormitory_id))

            schedule.activity_name = activity_name
            schedule.start_time = start_time
            schedule.end_time = end_time
            schedule.applies_all_dormitories = applies_all_dormitories
            schedule.applies_all_days = applies_all_days
            schedule.selected_days = None if applies_all_days else ','.join(selected_days)
            schedule.exclude_national_holidays = exclude_national_holidays

            if not applies_all_dormitories:
                selected_dormitories = [dormitory for dormitory in dormitories if dormitory.id in selected_dormitory_ids]
                schedule.selected_dormitories = selected_dormitories
                schedule.dormitory_id = selected_dormitories[0].id if selected_dormitories else None
            else:
                schedule.selected_dormitories = dormitories
                schedule.dormitory_id = dormitories[0].id if dormitories else None

            if not applies_all_days and selected_days:
                schedule.day = selected_days[0]
            else:
                schedule.day = None

            db.session.commit()
            flash('Template jadwal berhasil diperbarui.', 'success')
            return redirect(url_for('boarding.manage_schedules', dormitory_id=selected_dormitory_id))

        if action == 'toggle_schedule':
            schedule_id = request.form.get('schedule_id', type=int)
            schedule = BoardingActivitySchedule.query.get_or_404(schedule_id)
            if not _schedule_in_tenant(schedule, tenant_dormitory_ids):
                flash('Jadwal tidak valid untuk tenant aktif.', 'danger')
                return redirect(url_for('boarding.manage_schedules', dormitory_id=selected_dormitory_id))
            schedule.is_active = not schedule.is_active
            db.session.commit()
            flash(
                f"Template '{schedule.activity_name}' {'diaktifkan' if schedule.is_active else 'dinonaktifkan'}.",
                'success'
            )
            return redirect(url_for('boarding.manage_schedules', dormitory_id=selected_dormitory_id))

        if action == 'delete_schedule':
            schedule_id = request.form.get('schedule_id', type=int)
            schedule = BoardingActivitySchedule.query.get_or_404(schedule_id)
            if not _schedule_in_tenant(schedule, tenant_dormitory_ids):
                flash('Jadwal tidak valid untuk tenant aktif.', 'danger')
                return redirect(url_for('boarding.manage_schedules', dormitory_id=selected_dormitory_id))
            schedule.is_deleted = True
            db.session.commit()
            flash(f"Template '{schedule.activity_name}' dihapus.", 'success')
            return redirect(url_for('boarding.manage_schedules', dormitory_id=selected_dormitory_id))

        if action == 'add_holiday':
            holiday_date_raw = (request.form.get('holiday_date') or '').strip()
            holiday_name = (request.form.get('holiday_name') or '').strip()
            is_national = request.form.get('is_national') == 'on'

            if not holiday_date_raw or not holiday_name:
                flash('Tanggal dan nama hari libur wajib diisi.', 'warning')
                return redirect(url_for('boarding.manage_schedules', dormitory_id=selected_dormitory_id))

            try:
                holiday_date = datetime.strptime(holiday_date_raw, '%Y-%m-%d').date()
            except ValueError:
                flash('Format tanggal hari libur tidak valid.', 'warning')
                return redirect(url_for('boarding.manage_schedules', dormitory_id=selected_dormitory_id))

            existing = BoardingHoliday.query.filter_by(date=holiday_date).first()
            if existing:
                existing.name = holiday_name
                existing.is_national = is_national
                existing.is_deleted = False
            else:
                db.session.add(BoardingHoliday(
                    date=holiday_date,
                    name=holiday_name,
                    is_national=is_national
                ))
            db.session.commit()
            flash('Hari libur boarding berhasil disimpan.', 'success')
            return redirect(url_for('boarding.manage_schedules', dormitory_id=selected_dormitory_id))

    schedules = BoardingActivitySchedule.query.filter_by(is_deleted=False).order_by(
        BoardingActivitySchedule.start_time.asc(),
        BoardingActivitySchedule.activity_name.asc()
    ).all()
    schedules = [schedule for schedule in schedules if _schedule_in_tenant(schedule, tenant_dormitory_ids)]
    holidays = BoardingHoliday.query.filter_by(is_deleted=False).order_by(BoardingHoliday.date.asc()).all()
    selected_dormitory = None
    if selected_dormitory_id:
        selected_dormitory = next((dormitory for dormitory in dormitories if dormitory.id == selected_dormitory_id), None)
        if selected_dormitory:
            schedules = [s for s in schedules if _schedule_applies_to_dormitory(s, selected_dormitory.id)]

    return render_template(
        'boarding/admin_schedules.html',
        dormitories=dormitories,
        selected_dormitory=selected_dormitory,
        schedules=schedules,
        holidays=holidays,
        DAYS=DAYS,
        selected_days=_selected_days,
    )


@boarding_bp.route('/dashboard')
@login_required
@role_required(UserRole.WALI_ASRAMA)
def dashboard():
    tenant_id = _current_tenant_id()
    if tenant_id is None:
        flash('Tenant default tidak ditemukan.', 'danger')
        return redirect(url_for('main.dashboard'))

    today = local_today()
    today_name = _weekday_label(today)

    dormitories = (
        scoped_dormitories_query(tenant_id)
        .filter(BoardingDormitory.guardian_user_id == current_user.id)
        .order_by(BoardingDormitory.name)
        .all()
    )
    dormitory_ids = [item.id for item in dormitories]

    total_students = sum(len(list_students_for_dormitory(dormitory.id, tenant_id=tenant_id)) for dormitory in dormitories)

    attendance_today = BoardingAttendance.query.filter(
        BoardingAttendance.dormitory_id.in_(dormitory_ids),
        BoardingAttendance.date == today
    ).count() if dormitory_ids else 0

    todays_schedules = []
    for dorm in dormitories:
        dorm_schedules = _effective_schedules_for(dorm.id, today)
        for schedule in dorm_schedules:
            todays_schedules.append({'dormitory': dorm, 'schedule': schedule})
    todays_schedules.sort(key=lambda item: (item['schedule'].start_time, item['schedule'].activity_name))

    return render_template(
        'boarding/dashboard.html',
        dormitories=dormitories,
        total_students=total_students,
        attendance_today=attendance_today,
        todays_schedules=todays_schedules,
        today=today,
        today_name=today_name,
    )


@boarding_bp.route('/absensi', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.WALI_ASRAMA)
def input_attendance():
    tenant_id = _current_tenant_id()
    if tenant_id is None:
        flash('Tenant default tidak ditemukan.', 'danger')
        return redirect(url_for('main.dashboard'))

    my_dormitories = (
        scoped_dormitories_query(tenant_id)
        .filter(BoardingDormitory.guardian_user_id == current_user.id)
        .order_by(BoardingDormitory.name.asc())
        .all()
    )
    my_dormitory_ids = [d.id for d in my_dormitories]

    selected_dormitory_id = request.args.get('dormitory_id', type=int)
    selected_date = (request.args.get('date') or local_today().strftime('%Y-%m-%d')).strip()

    if request.method == 'POST':
        selected_dormitory_id = request.form.get('dormitory_id', type=int)
        selected_date = (request.form.get('attendance_date') or selected_date).strip()

    selected_dormitory = None
    if selected_dormitory_id and selected_dormitory_id in my_dormitory_ids:
        selected_dormitory = next((d for d in my_dormitories if d.id == selected_dormitory_id), None)
    elif selected_dormitory_id:
        flash('Anda tidak memiliki akses ke asrama tersebut.', 'danger')
        return redirect(url_for('boarding.input_attendance'))

    try:
        schedule_date = datetime.strptime(selected_date, '%Y-%m-%d').date()
    except ValueError:
        flash('Format tanggal tidak valid.', 'warning')
        return redirect(url_for('boarding.input_attendance'))
    selected_day = _weekday_label(schedule_date)

    schedules = _effective_schedules_for(selected_dormitory_id, schedule_date) if selected_dormitory else []

    selected_schedule_id = request.args.get('schedule_id', type=int)
    if request.method == 'POST':
        selected_schedule_id = request.form.get('schedule_id', type=int)

    if schedules and selected_schedule_id is None:
        selected_schedule_id = schedules[0].id

    selected_schedule = next((item for item in schedules if item.id == selected_schedule_id), None)
    students = list_students_for_dormitory(selected_dormitory_id, tenant_id=tenant_id) if selected_dormitory else []

    existing_attendance = {}
    if selected_schedule and students:
        records = BoardingAttendance.query.filter_by(
            dormitory_id=selected_dormitory_id,
            schedule_id=selected_schedule.id,
            date=schedule_date,
        ).all()
        for record in records:
            existing_attendance[record.student_id] = {
                'status': record.status.name,
                'notes': record.notes or '',
            }

    if request.method == 'POST':
        if not selected_dormitory:
            flash('Pilih asrama terlebih dahulu.', 'warning')
            return redirect(url_for('boarding.input_attendance'))
        if not selected_schedule:
            flash('Jadwal kegiatan pada tanggal tersebut belum dipilih.', 'warning')
            return redirect(url_for('boarding.input_attendance', dormitory_id=selected_dormitory_id, date=selected_date))

        saved = 0
        for student in students:
            status_raw = (request.form.get(f'status_{student.id}') or '').strip()
            if not status_raw:
                continue

            notes = (request.form.get(f'notes_{student.id}') or '').strip() or None
            existing = BoardingAttendance.query.filter_by(
                date=schedule_date,
                schedule_id=selected_schedule.id,
                student_id=student.id,
            ).first()

            if existing:
                existing.status = AttendanceStatus[status_raw]
                existing.notes = notes
                existing.attendance_by_user_id = current_user.id
            else:
                db.session.add(BoardingAttendance(
                    dormitory_id=selected_dormitory.id,
                    schedule_id=selected_schedule.id,
                    student_id=student.id,
                    attendance_by_user_id=current_user.id,
                    date=schedule_date,
                    status=AttendanceStatus[status_raw],
                    notes=notes,
                ))
            saved += 1

        db.session.commit()
        flash(f'Absensi boarding tersimpan ({saved} siswa).', 'success')
        return redirect(url_for(
            'boarding.input_attendance',
            dormitory_id=selected_dormitory_id,
            date=selected_date,
            schedule_id=selected_schedule.id,
        ))

    return render_template(
        'boarding/input_attendance.html',
        my_dormitories=my_dormitories,
        selected_dormitory=selected_dormitory,
        selected_dormitory_id=selected_dormitory_id,
        selected_date=selected_date,
        selected_day=selected_day,
        schedules=schedules,
        selected_schedule=selected_schedule,
        students=students,
        existing_attendance=existing_attendance,
        AttendanceStatus=AttendanceStatus,
    )

