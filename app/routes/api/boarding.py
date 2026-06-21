from datetime import datetime, timedelta

from flask import g, request

from app.services.finance_posting_service import post_savings_transaction
from app.extensions import db
from app.models import (
    AttendanceStatus,
    BoardingActivitySchedule,
    BoardingAttendance,
    BoardingDormitory,
    BoardingHoliday,
    EnrollmentStatus,
    Program,
    ProgramEnrollment,
    SavingsTransactionStatus,
    SavingsTransactionType,
    Student,
    StudentSavingsAccount,
    StudentSavingsTransaction,
    User,
    UserRole,
)
from app.services.pesantren_service import list_students_for_dormitory
from app.utils.tenant import resolve_tenant_id, scoped_dormitories_query
from app.utils.timezone import local_today, utc_now_naive

from .common import api_error, api_success, fmt_date, fmt_time, mobile_auth_required


DAYS = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
MAX_PIN_ATTEMPTS = 5
PIN_LOCK_MINUTES = 5


def _weekday_label(date_obj):
    return DAYS[date_obj.weekday()]


def _selected_days(schedule):
    if schedule.applies_all_days:
        return DAYS
    raw = (schedule.selected_days or "").strip()
    if raw:
        return [item.strip() for item in raw.split(",") if item.strip()]
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
    return schedule.dormitory_id == dormitory_id


def _effective_schedules_for(dormitory_id, date_obj):
    day_name = _weekday_label(date_obj)
    holiday = _is_holiday(date_obj)
    schedules = (
        BoardingActivitySchedule.query.filter_by(is_active=True, is_deleted=False)
        .order_by(BoardingActivitySchedule.start_time.asc())
        .all()
    )

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


def _parse_date(value):
    raw = (value or "").strip()
    if not raw:
        return local_today()
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


def _my_dormitories(user, tenant_id):
    return (
        scoped_dormitories_query(tenant_id)
        .filter(BoardingDormitory.guardian_user_id == user.id)
        .order_by(BoardingDormitory.name.asc())
        .all()
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
            & (Program.code == "PESANTREN")
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


def _dormitory_payload(dormitory, tenant_id):
    students = list_students_for_dormitory(dormitory.id, tenant_id=tenant_id)
    return {
        "id": dormitory.id,
        "name": dormitory.name or "-",
        "gender": dormitory.gender.name if dormitory.gender else "-",
        "gender_label": dormitory.gender.value if dormitory.gender else "-",
        "capacity": dormitory.capacity or 0,
        "student_count": len(students),
    }


def _schedule_payload(schedule, dormitory=None):
    return {
        "id": schedule.id,
        "activity_name": schedule.activity_name or "-",
        "start_time": fmt_time(schedule.start_time),
        "end_time": fmt_time(schedule.end_time),
        "dormitory_id": dormitory.id if dormitory else schedule.dormitory_id,
        "dormitory_name": dormitory.name if dormitory else getattr(schedule.dormitory, "name", "-"),
    }


def _student_payload(student, existing_attendance=None):
    existing_attendance = existing_attendance or {}
    return {
        "id": student.id,
        "nis": student.nis or "-",
        "name": student.full_name or "-",
        "full_name": student.full_name or "-",
        "gender": student.gender.name if student.gender else "-",
        "gender_label": student.gender.value if student.gender else "-",
        "status": existing_attendance.get("status"),
        "status_label": existing_attendance.get("status_label"),
        "notes": existing_attendance.get("notes") or "",
    }


def _savings_student_payload(student, account=None):
    return {
        "id": student.id,
        "nis": student.nis or "-",
        "name": student.full_name or "-",
        "full_name": student.full_name or "-",
        "dormitory_id": student.boarding_dormitory_id,
        "dormitory_name": getattr(getattr(student, "boarding_dormitory", None), "name", "-"),
        "balance": int(getattr(account, "balance", 0) or 0),
        "has_pin": bool(getattr(account, "pin_hash", None)),
        "pin_locked": _pin_lock_remaining(getattr(account, "pin_locked_until", None)) > 0 if account else False,
    }


def register_boarding_routes(api_bp):
    @api_bp.get("/boarding/dashboard")
    @mobile_auth_required(UserRole.WALI_ASRAMA, capability="boarding")
    def boarding_dashboard():
        user = g.mobile_user
        tenant_id = resolve_tenant_id(user)
        if tenant_id is None:
            return api_error("tenant_not_found", "Tenant default tidak ditemukan.", 404)

        today = local_today()
        dormitories = _my_dormitories(user, tenant_id)
        dormitory_ids = [item.id for item in dormitories]
        total_students = sum(
            len(list_students_for_dormitory(dormitory.id, tenant_id=tenant_id))
            for dormitory in dormitories
        )
        attendance_today = (
            BoardingAttendance.query.filter(
                BoardingAttendance.dormitory_id.in_(dormitory_ids),
                BoardingAttendance.date == today,
            ).count()
            if dormitory_ids
            else 0
        )

        todays_schedules = []
        for dormitory in dormitories:
            for schedule in _effective_schedules_for(dormitory.id, today):
                todays_schedules.append(_schedule_payload(schedule, dormitory))
        todays_schedules.sort(key=lambda item: (item["start_time"], item["activity_name"]))

        return api_success(
            {
                "profile": {
                    "name": getattr(getattr(user, "boarding_guardian_profile", None), "full_name", None)
                    or user.username
                    or "-",
                    "phone": getattr(getattr(user, "boarding_guardian_profile", None), "phone", None)
                    or "-",
                },
                "today": fmt_date(today),
                "today_name": _weekday_label(today),
                "summary": {
                    "dormitory_count": len(dormitories),
                    "student_count": total_students,
                    "attendance_today": attendance_today,
                    "schedule_today": len(todays_schedules),
                },
                "dormitories": [_dormitory_payload(item, tenant_id) for item in dormitories],
                "today_schedules": todays_schedules,
            }
        )

    @api_bp.get("/boarding/attendance")
    @mobile_auth_required(UserRole.WALI_ASRAMA, capability="boarding")
    def boarding_attendance_form():
        user = g.mobile_user
        tenant_id = resolve_tenant_id(user)
        if tenant_id is None:
            return api_error("tenant_not_found", "Tenant default tidak ditemukan.", 404)

        dormitories = _my_dormitories(user, tenant_id)
        dormitory_ids = {item.id for item in dormitories}
        if not dormitories:
            return api_success(
                {
                    "date": fmt_date(local_today()),
                    "day_name": _weekday_label(local_today()),
                    "dormitories": [],
                    "schedules": [],
                    "students": [],
                    "status_options": _status_options(),
                }
            )

        selected_date = _parse_date(request.args.get("date"))
        if selected_date is None:
            return api_error("validation_error", "Format tanggal tidak valid.", 422)

        selected_dormitory_id = request.args.get("dormitory_id", type=int) or dormitories[0].id
        if selected_dormitory_id not in dormitory_ids:
            return api_error("forbidden", "Anda tidak memiliki akses ke asrama tersebut.", 403)

        selected_dormitory = next(item for item in dormitories if item.id == selected_dormitory_id)
        schedules = _effective_schedules_for(selected_dormitory.id, selected_date)
        selected_schedule_id = request.args.get("schedule_id", type=int)
        if schedules and selected_schedule_id is None:
            selected_schedule_id = schedules[0].id
        selected_schedule = next(
            (item for item in schedules if item.id == selected_schedule_id),
            None,
        )

        students = list_students_for_dormitory(selected_dormitory.id, tenant_id=tenant_id)
        existing = _existing_attendance_map(selected_dormitory.id, selected_schedule, selected_date)

        return api_success(
            {
                "date": fmt_date(selected_date),
                "day_name": _weekday_label(selected_date),
                "selected_dormitory_id": selected_dormitory.id,
                "selected_schedule_id": selected_schedule.id if selected_schedule else None,
                "dormitories": [_dormitory_payload(item, tenant_id) for item in dormitories],
                "schedules": [_schedule_payload(item, selected_dormitory) for item in schedules],
                "students": [
                    _student_payload(student, existing.get(student.id))
                    for student in students
                ],
                "status_options": _status_options(),
            }
        )

    @api_bp.post("/boarding/attendance")
    @mobile_auth_required(UserRole.WALI_ASRAMA, capability="boarding")
    def boarding_attendance_save():
        user = g.mobile_user
        tenant_id = resolve_tenant_id(user)
        if tenant_id is None:
            return api_error("tenant_not_found", "Tenant default tidak ditemukan.", 404)

        payload = request.get_json(silent=True) or {}
        selected_date = _parse_date(payload.get("date"))
        if selected_date is None:
            return api_error("validation_error", "Format tanggal tidak valid.", 422)

        dormitory_id = _safe_int(payload.get("dormitory_id"))
        schedule_id = _safe_int(payload.get("schedule_id"))
        records = payload.get("records") or []
        if not dormitory_id or not schedule_id:
            return api_error("validation_error", "Asrama dan jadwal wajib dipilih.", 422)
        if not isinstance(records, list):
            return api_error("validation_error", "Format data absensi tidak valid.", 422)

        dormitory = (
            scoped_dormitories_query(tenant_id)
            .filter(
                BoardingDormitory.id == dormitory_id,
                BoardingDormitory.guardian_user_id == user.id,
            )
            .first()
        )
        if dormitory is None:
            return api_error("forbidden", "Anda tidak memiliki akses ke asrama tersebut.", 403)

        schedule = next(
            (item for item in _effective_schedules_for(dormitory.id, selected_date) if item.id == schedule_id),
            None,
        )
        if schedule is None:
            return api_error("validation_error", "Jadwal kegiatan tidak valid untuk tanggal ini.", 422)

        students = list_students_for_dormitory(dormitory.id, tenant_id=tenant_id)
        student_ids = {student.id for student in students}
        saved = 0

        for row in records:
            if not isinstance(row, dict):
                continue
            student_id = _safe_int(row.get("student_id"))
            status_raw = str(row.get("status") or "").strip().upper()
            if student_id not in student_ids or not status_raw:
                continue
            if status_raw not in AttendanceStatus.__members__:
                return api_error("validation_error", f"Status absensi tidak valid: {status_raw}.", 422)

            notes = str(row.get("notes") or "").strip() or None
            existing = BoardingAttendance.query.filter_by(
                date=selected_date,
                schedule_id=schedule.id,
                student_id=student_id,
            ).first()
            if existing:
                existing.status = AttendanceStatus[status_raw]
                existing.notes = notes
                existing.attendance_by_user_id = user.id
            else:
                db.session.add(
                    BoardingAttendance(
                        dormitory_id=dormitory.id,
                        schedule_id=schedule.id,
                        student_id=student_id,
                        attendance_by_user_id=user.id,
                        date=selected_date,
                        status=AttendanceStatus[status_raw],
                        notes=notes,
                    )
                )
            saved += 1

        db.session.commit()
        return api_success({"saved": saved}, message=f"Absensi asrama tersimpan ({saved} santri).")

    @api_bp.get("/boarding/savings")
    @mobile_auth_required(UserRole.WALI_ASRAMA, capability="boarding")
    def boarding_savings():
        user = g.mobile_user
        tenant_id = resolve_tenant_id(user)
        if tenant_id is None:
            return api_error("tenant_not_found", "Tenant default tidak ditemukan.", 404)

        students = _tenant_pesantren_students_query(tenant_id).order_by(Student.full_name.asc()).all()
        student_ids = [student.id for student in students]
        accounts = (
            StudentSavingsAccount.query.filter_by(tenant_id=tenant_id)
            .filter(StudentSavingsAccount.student_id.in_(student_ids) if student_ids else False)
            .all()
        )
        account_map = {account.student_id: account for account in accounts}
        total_balance = sum(int(account.balance or 0) for account in accounts)

        return api_success(
            {
                "officer_pin_exists": bool(user.withdrawal_pin_hash),
                "officer_pin_locked_minutes": _pin_lock_remaining(user.withdrawal_pin_locked_until),
                "summary": {
                    "student_count": len(students),
                    "account_count": len(accounts),
                    "total_balance": total_balance,
                },
                "students": [
                    _savings_student_payload(student, account_map.get(student.id))
                    for student in students
                ],
            }
        )

    @api_bp.post("/boarding/savings/officer-pin")
    @mobile_auth_required(UserRole.WALI_ASRAMA, capability="boarding")
    def boarding_savings_set_officer_pin():
        user = g.mobile_user
        payload = request.get_json(silent=True) or {}
        old_pin = str(payload.get("old_pin") or "").strip()
        pin = str(payload.get("pin") or "").strip()
        pin_confirm = str(payload.get("pin_confirm") or "").strip()

        if user.withdrawal_pin_hash and not old_pin:
            return api_error("validation_error", "PIN lama wajib diisi untuk mengganti PIN petugas.", 422)
        if user.withdrawal_pin_hash and not user.check_withdrawal_pin(old_pin):
            return api_error("validation_error", "PIN lama tidak valid.", 422)
        if len(pin) < 4 or not pin.isdigit():
            return api_error("validation_error", "PIN petugas harus angka minimal 4 digit.", 422)
        if pin != pin_confirm:
            return api_error("validation_error", "Konfirmasi PIN petugas tidak sama.", 422)

        user.set_withdrawal_pin(pin)
        user.withdrawal_pin_failed_attempts = 0
        user.withdrawal_pin_locked_until = None
        db.session.commit()
        return api_success({"officer_pin_exists": True}, message="PIN petugas berhasil disimpan.")

    @api_bp.post("/boarding/savings/withdraw")
    @mobile_auth_required(UserRole.WALI_ASRAMA, capability="boarding")
    def boarding_savings_withdraw():
        user = g.mobile_user
        tenant_id = resolve_tenant_id(user)
        if tenant_id is None:
            return api_error("tenant_not_found", "Tenant default tidak ditemukan.", 404)

        payload = request.get_json(silent=True) or {}
        student_id = _safe_int(payload.get("student_id"))
        amount = _normalize_amount(payload.get("amount"))
        officer_pin = str(payload.get("officer_pin") or "").strip()
        student_pin = str(payload.get("student_pin") or "").strip()

        if not user.withdrawal_pin_hash:
            return api_error("officer_pin_required", "PIN petugas belum diset.", 422)
        officer_lock_remaining = _pin_lock_remaining(user.withdrawal_pin_locked_until)
        if officer_lock_remaining > 0:
            return api_error(
                "officer_pin_locked",
                f"PIN petugas terkunci sementara. Coba lagi {officer_lock_remaining} menit lagi.",
                423,
            )
        if not user.check_withdrawal_pin(officer_pin):
            user.withdrawal_pin_failed_attempts = (user.withdrawal_pin_failed_attempts or 0) + 1
            if user.withdrawal_pin_failed_attempts >= MAX_PIN_ATTEMPTS:
                user.withdrawal_pin_locked_until = utc_now_naive() + timedelta(minutes=PIN_LOCK_MINUTES)
                user.withdrawal_pin_failed_attempts = 0
            db.session.commit()
            return api_error("validation_error", "PIN petugas tidak valid.", 422)

        user.withdrawal_pin_failed_attempts = 0
        user.withdrawal_pin_locked_until = None
        if amount <= 0:
            db.session.commit()
            return api_error("validation_error", "Nominal penarikan harus lebih besar dari 0.", 422)

        try:
            student = _tenant_pesantren_students_query(tenant_id).filter(Student.id == student_id).first()
            if student is None:
                db.session.commit()
                return api_error("validation_error", "Penarikan hanya berlaku untuk santri program pesantren.", 422)

            account = (
                StudentSavingsAccount.query
                .filter_by(tenant_id=tenant_id, student_id=student_id)
                .with_for_update()
                .first()
            )
            if account is None or int(account.balance or 0) < amount:
                db.session.commit()
                return api_error("validation_error", "Saldo tidak mencukupi atau akun tidak valid.", 422)
            if not account.pin_hash:
                db.session.commit()
                return api_error("student_pin_required", "PIN santri belum diset.", 422)

            student_lock_remaining = _pin_lock_remaining(account.pin_locked_until)
            if student_lock_remaining > 0:
                db.session.commit()
                return api_error(
                    "student_pin_locked",
                    f"PIN santri terkunci sementara. Coba lagi {student_lock_remaining} menit lagi.",
                    423,
                )
            if not account.check_pin(student_pin):
                account.pin_failed_attempts = (account.pin_failed_attempts or 0) + 1
                if account.pin_failed_attempts >= MAX_PIN_ATTEMPTS:
                    account.pin_locked_until = utc_now_naive() + timedelta(minutes=PIN_LOCK_MINUTES)
                    account.pin_failed_attempts = 0
                db.session.commit()
                return api_error("validation_error", "PIN santri tidak valid. Penarikan dibatalkan.", 422)

            account.pin_failed_attempts = 0
            account.pin_locked_until = None
            trx = StudentSavingsTransaction(
                tenant_id=tenant_id,
                account_id=account.id,
                student_id=student_id,
                amount=amount,
                transaction_type=SavingsTransactionType.WITHDRAWAL,
                status=SavingsTransactionStatus.APPROVED,
                requested_by_user_id=user.id,
                approved_by_user_id=user.id,
                approved_at=utc_now_naive(),
            )
            account.balance -= amount
            db.session.add(trx)
            db.session.commit()
            journal_posted = True
            try:
                post_savings_transaction(
                    tenant_id=tenant_id,
                    savings_transaction_id=trx.id,
                    actor_user_id=user.id,
                )
            except Exception:
                journal_posted = False
            return api_success(
                {
                    "transaction_id": trx.id,
                    "student_id": student_id,
                    "amount": amount,
                    "balance": int(account.balance or 0),
                    "journal_posted": journal_posted,
                },
                message="Penarikan tunai berhasil dicatat.",
            )
        except Exception:
            db.session.rollback()
            return api_error("server_error", "Gagal memproses penarikan. Silakan coba lagi.", 500)


def _existing_attendance_map(dormitory_id, schedule, selected_date):
    if schedule is None:
        return {}
    rows = BoardingAttendance.query.filter_by(
        dormitory_id=dormitory_id,
        schedule_id=schedule.id,
        date=selected_date,
    ).all()
    return {
        row.student_id: {
            "status": row.status.name if row.status else None,
            "status_label": row.status.value if row.status else None,
            "notes": row.notes or "",
        }
        for row in rows
    }


def _status_options():
    return [
        {"key": status.name, "label": status.value}
        for status in AttendanceStatus
    ]


def _safe_int(raw_value):
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return None


def _normalize_amount(raw_value):
    raw = str(raw_value or "0").replace(".", "").replace(",", "").strip()
    try:
        return int(raw)
    except ValueError:
        return 0


def _pin_lock_remaining(locked_until):
    if not locked_until:
        return 0
    now = utc_now_naive()
    if locked_until <= now:
        return 0
    delta = locked_until - now
    return max(1, int(delta.total_seconds() // 60) + (1 if delta.total_seconds() % 60 else 0))
