from datetime import datetime, timedelta, timezone
from app.utils.timezone import utc_now_naive

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_required, current_user
from sqlalchemy import func, case
from sqlalchemy.orm import joinedload

from app.decorators import role_required
from app.utils.timezone import APP_TIMEZONE, local_today, local_day_bounds_utc_naive
from app.utils.tenant import resolve_tenant_id, scoped_dormitories_query
from app.extensions import db
from app.services.pesantren_service import list_students_for_dormitory, sync_student_dormitory_membership
from app.services.finance_posting_service import post_savings_transaction
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
    ProgramEnrollment,
    ProgramGroup,
    StudentSavingsAccount,
    StudentSavingsTransaction,
    SavingsTransactionType,
    SavingsTransactionStatus,
    EnrollmentStatus,
)


boarding_bp = Blueprint('boarding', __name__, url_prefix='/boarding')
DAYS = ['Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu', 'Minggu']
MAX_PIN_ATTEMPTS = 5
PIN_LOCK_MINUTES = 5
OFFICER_AUTH_WINDOW_SECONDS = 300
OFFICER_AUTH_IDLE_SECONDS = 90
OFFICER_REAUTH_AMOUNT_THRESHOLD = 200000
OFFICER_REAUTH_AFTER_TRANSACTIONS = 5


def _officer_auth_key(name):
    return f'savings_officer_{name}'


def _clear_officer_auth_session():
    for key in ('user_id', 'expires_at', 'last_seen', 'tx_count'):
        session.pop(_officer_auth_key(key), None)


def _set_officer_auth_session(user_id):
    now_ts = int(utc_now_naive().timestamp())
    session[_officer_auth_key('user_id')] = user_id
    session[_officer_auth_key('expires_at')] = now_ts + OFFICER_AUTH_WINDOW_SECONDS
    session[_officer_auth_key('last_seen')] = now_ts
    session[_officer_auth_key('tx_count')] = 0


def _officer_auth_state():
    now_ts = int(utc_now_naive().timestamp())
    user_id = session.get(_officer_auth_key('user_id'))
    expires_at = int(session.get(_officer_auth_key('expires_at')) or 0)
    last_seen = int(session.get(_officer_auth_key('last_seen')) or 0)
    tx_count = int(session.get(_officer_auth_key('tx_count')) or 0)

    unlocked = (
        user_id == current_user.id
        and expires_at > now_ts
        and (now_ts - last_seen) <= OFFICER_AUTH_IDLE_SECONDS
    )
    if not unlocked:
        _clear_officer_auth_session()
        return {'unlocked': False, 'tx_count': 0}

    session[_officer_auth_key('last_seen')] = now_ts
    return {'unlocked': True, 'tx_count': tx_count}


def _register_officer_tx_auth_use():
    tx_count = int(session.get(_officer_auth_key('tx_count')) or 0)
    session[_officer_auth_key('tx_count')] = tx_count + 1


def _pin_lock_remaining(locked_until):
    if not locked_until:
        return 0
    now = utc_now_naive()
    if locked_until <= now:
        return 0
    delta = locked_until - now
    return max(1, int(delta.total_seconds() // 60) + (1 if delta.total_seconds() % 60 else 0))


def _local_naive_to_utc_naive(local_dt):
    if local_dt is None:
        return None
    aware_local = local_dt.replace(tzinfo=APP_TIMEZONE)
    return aware_local.astimezone(timezone.utc).replace(tzinfo=None)


def _utc_naive_to_local_naive(utc_dt):
    if utc_dt is None:
        return None
    aware_utc = utc_dt.replace(tzinfo=timezone.utc)
    return aware_utc.astimezone(APP_TIMEZONE).replace(tzinfo=None)


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


def _tenant_pesantren_students_query(tenant_id):
    return (
        Student.query
        .join(User, Student.user_id == User.id)
        .join(
            ProgramEnrollment,
            (ProgramEnrollment.person_id == Student.person_id)
            & (ProgramEnrollment.status == EnrollmentStatus.ACTIVE)
            & (ProgramEnrollment.is_deleted.is_(False)),
        )
        .join(
            Program,
            (Program.id == ProgramEnrollment.program_id)
            & (Program.code == 'PESANTREN')
            & (Program.is_deleted.is_(False)),
        )
        .filter(
            Student.is_deleted.is_(False),
            User.is_deleted.is_(False),
            User.tenant_id == tenant_id,
            ProgramEnrollment.tenant_id == tenant_id,
        )
        .distinct()
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



@boarding_bp.route('/tabungan', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.WALI_ASRAMA, UserRole.ADMIN, UserRole.TU)
def manage_savings():
    tenant_id = _current_tenant_id()
    auth_state = _officer_auth_state()
    if request.method == 'POST':
        action = (request.form.get('action') or '').strip()
        trx_id = request.form.get('transaction_id', type=int)

        if action == 'set_officer_pin':
            old_officer_pin = (request.form.get('old_officer_pin') or '').strip()
            officer_pin = (request.form.get('officer_pin') or '').strip()
            officer_pin_confirm = (request.form.get('officer_pin_confirm') or '').strip()
            if current_user.withdrawal_pin_hash and not old_officer_pin:
                flash('PIN lama wajib diisi untuk mengganti PIN petugas.', 'warning')
                return redirect(url_for('boarding.manage_savings'))
            if current_user.withdrawal_pin_hash and not current_user.check_withdrawal_pin(old_officer_pin):
                flash('PIN lama tidak valid.', 'danger')
                return redirect(url_for('boarding.manage_savings'))
            if len(officer_pin) < 4 or not officer_pin.isdigit():
                flash('PIN petugas harus angka minimal 4 digit.', 'warning')
                return redirect(url_for('boarding.manage_savings'))
            if officer_pin != officer_pin_confirm:
                flash('Konfirmasi PIN petugas tidak sama.', 'warning')
                return redirect(url_for('boarding.manage_savings'))
            current_user.set_withdrawal_pin(officer_pin)
            current_user.withdrawal_pin_failed_attempts = 0
            current_user.withdrawal_pin_locked_until = None
            db.session.commit()
            flash('PIN petugas untuk verifikasi penarikan berhasil disimpan.', 'success')
            return redirect(url_for('boarding.manage_savings'))

        if action == 'unlock_officer_pin':
            if not current_user.withdrawal_pin_hash:
                flash('PIN petugas belum diset. Silakan atur PIN petugas terlebih dahulu.', 'warning')
                return redirect(url_for('boarding.manage_savings'))
            officer_pin = (request.form.get('officer_pin') or '').strip()
            lock_remaining = _pin_lock_remaining(current_user.withdrawal_pin_locked_until)
            if lock_remaining > 0:
                flash(f'PIN petugas terkunci sementara. Coba lagi {lock_remaining} menit lagi.', 'danger')
                return redirect(url_for('boarding.manage_savings'))

            if not current_user.check_withdrawal_pin(officer_pin):
                current_user.withdrawal_pin_failed_attempts = (current_user.withdrawal_pin_failed_attempts or 0) + 1
                if current_user.withdrawal_pin_failed_attempts >= MAX_PIN_ATTEMPTS:
                    current_user.withdrawal_pin_locked_until = utc_now_naive() + timedelta(minutes=PIN_LOCK_MINUTES)
                    current_user.withdrawal_pin_failed_attempts = 0
                db.session.commit()
                flash('PIN petugas tidak valid.', 'danger')
                return redirect(url_for('boarding.manage_savings'))

            current_user.withdrawal_pin_failed_attempts = 0
            current_user.withdrawal_pin_locked_until = None
            _set_officer_auth_session(current_user.id)
            db.session.commit()
            flash('Sesi otorisasi PIN petugas aktif.', 'success')
            return redirect(url_for('boarding.manage_savings'))

        if action == 'lock_officer_pin':
            _clear_officer_auth_session()
            flash('Sesi otorisasi PIN petugas dikunci.', 'info')
            return redirect(url_for('boarding.manage_savings'))

        if action in {'approve', 'reject'} and trx_id:
            try:
                with db.session.begin_nested():
                    locked_trx = (
                        StudentSavingsTransaction.query
                        .filter_by(id=trx_id, tenant_id=tenant_id)
                        .with_for_update()
                        .first()
                    )
                    if not locked_trx or locked_trx.status != SavingsTransactionStatus.PENDING:
                        flash('Transaksi tidak ditemukan atau sudah diproses.', 'warning')
                        return redirect(url_for('boarding.manage_savings'))

                    is_pesantren_student = (
                        _tenant_pesantren_students_query(tenant_id)
                        .filter(Student.id == locked_trx.student_id)
                        .first()
                        is not None
                    )
                    if not is_pesantren_student:
                        flash('Transaksi tabungan hanya berlaku untuk santri program pesantren.', 'warning')
                        return redirect(url_for('boarding.manage_savings'))

                    locked_trx.status = SavingsTransactionStatus.APPROVED if action == 'approve' else SavingsTransactionStatus.REJECTED
                    locked_trx.approved_by_user_id = current_user.id
                    locked_trx.approved_at = utc_now_naive()
                    if action == 'approve':
                        locked_account = (
                            StudentSavingsAccount.query
                            .filter_by(id=locked_trx.account_id, tenant_id=tenant_id)
                            .with_for_update()
                            .first()
                        )
                        if not locked_account:
                            flash('Akun tabungan tidak ditemukan.', 'warning')
                            return redirect(url_for('boarding.manage_savings'))
                        if locked_trx.transaction_type == SavingsTransactionType.DEPOSIT:
                            locked_account.balance += locked_trx.amount
                        elif locked_account.balance >= locked_trx.amount:
                            locked_account.balance -= locked_trx.amount
                        else:
                            flash('Saldo akun tidak cukup untuk memproses transaksi.', 'warning')
                            return redirect(url_for('boarding.manage_savings'))
                db.session.commit()
                if action == 'approve':
                    try:
                        post_savings_transaction(
                            tenant_id=tenant_id,
                            savings_transaction_id=trx_id,
                            actor_user_id=current_user.id,
                        )
                    except Exception:
                        flash(
                            'Transaksi tabungan tersimpan, tetapi jurnal finance belum terposting otomatis. '
                            'Silakan cek menu rekonsiliasi posting.',
                            'warning'
                        )
                flash('Transaksi tabungan berhasil diproses.', 'success')
            except Exception:
                db.session.rollback()
                flash('Gagal memproses transaksi. Silakan coba lagi.', 'danger')
            return redirect(url_for('boarding.manage_savings'))

        if action == 'withdraw':
            student_id = request.form.get('student_id', type=int)
            amount_raw = (
                request.form.get('withdraw_amount')
                or request.form.get('amount')
                or '0'
            ).replace('.', '').replace(',', '')
            try:
                amount = int(amount_raw)
            except ValueError:
                amount = 0
            officer_pin = (request.form.get('officer_pin') or '').strip()
            student_pin = (request.form.get('student_pin') or '').strip()
            auth_state = _officer_auth_state()
            force_reauth = amount >= OFFICER_REAUTH_AMOUNT_THRESHOLD or auth_state.get('tx_count', 0) >= OFFICER_REAUTH_AFTER_TRANSACTIONS

            if not current_user.withdrawal_pin_hash:
                flash('PIN petugas belum diset. Silakan atur PIN petugas terlebih dahulu.', 'warning')
                return redirect(url_for('boarding.manage_savings'))

            lock_remaining = _pin_lock_remaining(current_user.withdrawal_pin_locked_until)
            if lock_remaining > 0:
                flash(f'PIN petugas terkunci sementara. Coba lagi {lock_remaining} menit lagi.', 'danger')
                return redirect(url_for('boarding.manage_savings'))

            if not auth_state.get('unlocked') or force_reauth:
                if not current_user.check_withdrawal_pin(officer_pin):
                    current_user.withdrawal_pin_failed_attempts = (current_user.withdrawal_pin_failed_attempts or 0) + 1
                    if current_user.withdrawal_pin_failed_attempts >= MAX_PIN_ATTEMPTS:
                        current_user.withdrawal_pin_locked_until = utc_now_naive() + timedelta(minutes=PIN_LOCK_MINUTES)
                        current_user.withdrawal_pin_failed_attempts = 0
                    db.session.commit()
                    flash('PIN petugas tidak valid.', 'danger')
                    return redirect(url_for('boarding.manage_savings'))
                current_user.withdrawal_pin_failed_attempts = 0
                current_user.withdrawal_pin_locked_until = None
                _set_officer_auth_session(current_user.id)
                db.session.commit()

            if amount <= 0:
                flash('Nominal tidak valid.', 'warning')
                return redirect(url_for('boarding.manage_savings'))

            try:
                with db.session.begin_nested():
                    pesantren_student = (
                        _tenant_pesantren_students_query(tenant_id)
                        .filter(Student.id == student_id)
                        .first()
                    )
                    if not pesantren_student:
                        flash('Penarikan hanya berlaku untuk santri program pesantren.', 'warning')
                        return redirect(url_for('boarding.manage_savings'))

                    account = (
                        StudentSavingsAccount.query
                        .filter_by(tenant_id=tenant_id, student_id=student_id)
                        .with_for_update()
                        .first()
                    )
                    if not account or account.balance < amount:
                        flash('Saldo tidak mencukupi atau akun tidak valid.', 'warning')
                        return redirect(url_for('boarding.manage_savings'))
                    if not account.pin_hash:
                        flash('PIN santri belum diset. Minta orang tua/santri set PIN terlebih dahulu.', 'warning')
                        return redirect(url_for('boarding.manage_savings'))

                    student_lock_remaining = _pin_lock_remaining(account.pin_locked_until)
                    if student_lock_remaining > 0:
                        flash(f'PIN santri terkunci sementara. Coba lagi {student_lock_remaining} menit lagi.', 'danger')
                        return redirect(url_for('boarding.manage_savings'))

                    if not account.check_pin(student_pin):
                        account.pin_failed_attempts = (account.pin_failed_attempts or 0) + 1
                        if account.pin_failed_attempts >= MAX_PIN_ATTEMPTS:
                            account.pin_locked_until = utc_now_naive() + timedelta(minutes=PIN_LOCK_MINUTES)
                            account.pin_failed_attempts = 0
                        db.session.flush()
                        flash('PIN santri tidak valid. Penarikan dibatalkan.', 'danger')
                        return redirect(url_for('boarding.manage_savings'))

                    account.pin_failed_attempts = 0
                    account.pin_locked_until = None
                    trx = StudentSavingsTransaction(
                        tenant_id=tenant_id,
                        account_id=account.id,
                        student_id=student_id,
                        amount=amount,
                        transaction_type=SavingsTransactionType.WITHDRAWAL,
                        status=SavingsTransactionStatus.APPROVED,
                        requested_by_user_id=current_user.id,
                        approved_by_user_id=current_user.id,
                        approved_at=utc_now_naive(),
                    )
                    account.balance -= amount
                    db.session.add(trx)
                db.session.commit()
                try:
                    post_savings_transaction(
                        tenant_id=tenant_id,
                        savings_transaction_id=trx.id,
                        actor_user_id=current_user.id,
                    )
                except Exception:
                    flash(
                        'Penarikan tercatat, tetapi jurnal finance belum terposting otomatis. '
                        'Silakan cek menu rekonsiliasi posting.',
                        'warning'
                    )
                _register_officer_tx_auth_use()
                flash('Penarikan tunai berhasil dicatat. Serahkan uang ke santri.', 'success')
            except Exception:
                db.session.rollback()
                flash('Gagal memproses penarikan. Silakan coba lagi.', 'danger')
            return redirect(url_for('boarding.manage_savings'))

    selected_mode = (request.args.get('mode') or 'kasir').strip().lower()
    if selected_mode not in {'kasir', 'rekonsiliasi'}:
        selected_mode = 'kasir'

    selected_recon_date = local_today()
    recon_start_utc, recon_end_utc = local_day_bounds_utc_naive(selected_recon_date)

    students = _tenant_pesantren_students_query(tenant_id).order_by(Student.full_name.asc()).all()
    pesantren_student_ids = [student.id for student in students]
    pending_query = (
        StudentSavingsTransaction.query
        .filter_by(tenant_id=tenant_id, status=SavingsTransactionStatus.PENDING)
    )
    if pesantren_student_ids:
        pending_query = pending_query.filter(StudentSavingsTransaction.student_id.in_(pesantren_student_ids))
    else:
        pending_query = pending_query.filter(False)
    pending = pending_query.order_by(StudentSavingsTransaction.id.desc()).all()

    accounts = (
        StudentSavingsAccount.query
        .filter_by(tenant_id=tenant_id)
        .filter(StudentSavingsAccount.student_id.in_(pesantren_student_ids) if pesantren_student_ids else False)
        .order_by(StudentSavingsAccount.id.asc())
        .all()
    )
    account_map = {a.student_id: a for a in accounts}

    daily_rows = (
        db.session.query(
            StudentSavingsTransaction.account_id.label('account_id'),
            func.coalesce(
                func.sum(
                    case((StudentSavingsTransaction.transaction_type == SavingsTransactionType.DEPOSIT, StudentSavingsTransaction.amount), else_=0)
                ), 0
            ).label('daily_deposit'),
            func.coalesce(
                func.sum(
                    case((StudentSavingsTransaction.transaction_type == SavingsTransactionType.WITHDRAWAL, StudentSavingsTransaction.amount), else_=0)
                ), 0
            ).label('daily_withdraw'),
        )
        .filter(
            StudentSavingsTransaction.tenant_id == tenant_id,
            StudentSavingsTransaction.status == SavingsTransactionStatus.APPROVED,
            StudentSavingsTransaction.created_at >= recon_start_utc,
            StudentSavingsTransaction.created_at < recon_end_utc,
        )
        .group_by(StudentSavingsTransaction.account_id)
        .all()
    )
    cumulative_rows = (
        db.session.query(
            StudentSavingsTransaction.account_id.label('account_id'),
            func.coalesce(
                func.sum(
                    case((StudentSavingsTransaction.transaction_type == SavingsTransactionType.DEPOSIT, StudentSavingsTransaction.amount), else_=0)
                ), 0
            ).label('total_deposit'),
            func.coalesce(
                func.sum(
                    case((StudentSavingsTransaction.transaction_type == SavingsTransactionType.WITHDRAWAL, StudentSavingsTransaction.amount), else_=0)
                ), 0
            ).label('total_withdraw'),
        )
        .filter(
            StudentSavingsTransaction.tenant_id == tenant_id,
            StudentSavingsTransaction.status == SavingsTransactionStatus.APPROVED,
        )
        .group_by(StudentSavingsTransaction.account_id)
        .all()
    )
    daily_map = {row.account_id: row for row in daily_rows}
    cumulative_map = {row.account_id: row for row in cumulative_rows}
    student_map = {student.id: student for student in students}
    recon_rows = []
    mismatch_count = 0
    for account in accounts:
        daily = daily_map.get(account.id)
        cumulative = cumulative_map.get(account.id)
        daily_deposit = int(getattr(daily, 'daily_deposit', 0) or 0)
        daily_withdraw = int(getattr(daily, 'daily_withdraw', 0) or 0)
        cumulative_net = int(getattr(cumulative, 'total_deposit', 0) or 0) - int(getattr(cumulative, 'total_withdraw', 0) or 0)
        daily_net = daily_deposit - daily_withdraw
        opening_balance = account.balance - daily_net
        mismatch = account.balance - cumulative_net
        if mismatch != 0:
            mismatch_count += 1
        recon_rows.append({
            'student_id': account.student_id,
            'student_name': student_map.get(account.student_id).full_name if student_map.get(account.student_id) else f'ID {account.student_id}',
            'opening_balance': opening_balance,
            'daily_deposit': daily_deposit,
            'daily_withdraw': daily_withdraw,
            'closing_balance': account.balance,
            'mismatch': mismatch,
        })

    recon_rows.sort(key=lambda item: item['student_name'].lower())
    selected_history_student_id = request.args.get('history_student_id', type=int)
    recon_student_ids = {row['student_id'] for row in recon_rows}
    if selected_history_student_id not in recon_student_ids:
        selected_history_student_id = None

    now_local = _utc_naive_to_local_naive(utc_now_naive()) or datetime.combine(local_today(), datetime.min.time())
    history_month_value = (request.args.get('history_month') or now_local.strftime('%Y-%m')).strip()
    try:
        history_year_raw, history_month_raw = history_month_value.split('-', 1)
        history_year = int(history_year_raw)
        history_month = int(history_month_raw)
        history_month_start_local = datetime(history_year, history_month, 1)
    except (ValueError, TypeError):
        history_month_start_local = datetime(now_local.year, now_local.month, 1)
        history_month_value = history_month_start_local.strftime('%Y-%m')
    if history_month_start_local.month == 12:
        history_month_end_local = datetime(history_month_start_local.year + 1, 1, 1)
    else:
        history_month_end_local = datetime(history_month_start_local.year, history_month_start_local.month + 1, 1)

    history_month_start_utc = _local_naive_to_utc_naive(history_month_start_local)
    history_month_end_utc = _local_naive_to_utc_naive(history_month_end_local)

    history_rows = []
    history_month_options = []
    selected_history_student = student_map.get(selected_history_student_id) if selected_history_student_id else None
    if selected_history_student_id:
        history_bounds = (
            db.session.query(
                func.min(StudentSavingsTransaction.created_at).label('first_created_at'),
                func.max(StudentSavingsTransaction.created_at).label('last_created_at'),
            )
            .filter(
                StudentSavingsTransaction.tenant_id == tenant_id,
                StudentSavingsTransaction.student_id == selected_history_student_id,
                StudentSavingsTransaction.status == SavingsTransactionStatus.APPROVED,
            )
            .first()
        )
        first_created_at = getattr(history_bounds, 'first_created_at', None)
        last_created_at = getattr(history_bounds, 'last_created_at', None)
        if first_created_at:
            first_local = _utc_naive_to_local_naive(first_created_at) or history_month_start_local
            last_local = _utc_naive_to_local_naive(last_created_at) or now_local
            first_month_local = datetime(first_local.year, first_local.month, 1)
            latest_local = last_local if last_local > now_local else now_local
            last_month_local = datetime(latest_local.year, latest_local.month, 1)
            cursor = last_month_local
            while cursor >= first_month_local:
                history_month_options.append({
                    'value': cursor.strftime('%Y-%m'),
                    'label': cursor.strftime('%m/%Y'),
                })
                if cursor.month == 1:
                    cursor = datetime(cursor.year - 1, 12, 1)
                else:
                    cursor = datetime(cursor.year, cursor.month - 1, 1)
        else:
            history_month_options.append({
                'value': history_month_start_local.strftime('%Y-%m'),
                'label': history_month_start_local.strftime('%m/%Y'),
            })

        approved_transactions = (
            StudentSavingsTransaction.query.options(
                joinedload(StudentSavingsTransaction.approved_by),
                joinedload(StudentSavingsTransaction.requested_by),
            )
            .filter(
                StudentSavingsTransaction.tenant_id == tenant_id,
                StudentSavingsTransaction.student_id == selected_history_student_id,
                StudentSavingsTransaction.status == SavingsTransactionStatus.APPROVED,
                StudentSavingsTransaction.created_at < history_month_end_utc,
            )
            .order_by(StudentSavingsTransaction.created_at.asc(), StudentSavingsTransaction.id.asc())
            .all()
        )
        running_balance = 0
        for trx in approved_transactions:
            if trx.transaction_type == SavingsTransactionType.DEPOSIT:
                running_balance += trx.amount
            else:
                running_balance -= trx.amount

            if trx.created_at < history_month_start_utc:
                continue

            officer_name = (
                trx.approved_by.username
                if trx.approved_by and trx.approved_by.username
                else (
                    trx.requested_by.username
                    if trx.requested_by and trx.requested_by.username
                    else '-'
                )
            )
            history_rows.append({
                'id': trx.id,
                'created_at_local': _utc_naive_to_local_naive(trx.created_at),
                'transaction_type': trx.transaction_type,
                'transaction_type_label': 'Top Up' if trx.transaction_type == SavingsTransactionType.DEPOSIT else 'Penarikan',
                'amount': trx.amount,
                'officer_name': officer_name,
                'ending_balance': running_balance,
            })
        history_rows.reverse()

    auth_state = _officer_auth_state()
    return render_template(
        'boarding/manage_savings.html',
        students=students,
        pending=pending,
        account_map=account_map,
        officer_pin_unlocked=auth_state.get('unlocked', False),
        officer_tx_count=auth_state.get('tx_count', 0),
        officer_pin_exists=bool(current_user.withdrawal_pin_hash),
        selected_recon_date=selected_recon_date,
        recon_rows=recon_rows,
        recon_mismatch_count=mismatch_count,
        selected_mode=selected_mode,
        selected_history_student=selected_history_student,
        selected_history_student_id=selected_history_student_id,
        history_month_value=history_month_value,
        history_month_options=history_month_options,
        history_rows=history_rows,
    )
