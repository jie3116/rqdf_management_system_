from datetime import datetime
from functools import wraps

from flask import Blueprint, g, jsonify, request

from app.extensions import csrf, db
from sqlalchemy import and_, or_

from app.models import (
    Attendance,
    AttendanceStatus,
    BoardingAttendance,
    ClassRoom,
    Invoice,
    ParticipantType,
    PaymentStatus,
    ProgramType,
    RecitationRecord,
    Schedule,
    Student,
    TahfidzEvaluation,
    TahfidzRecord,
    TahfidzSummary,
    Teacher,
    User,
    UserRole,
)
from app.routes.auth import _resolve_user_for_login
from app.routes.teacher import (
    _classroom_visible_for_teacher,
    _collect_teacher_assignment_summary,
    _count_teacher_students,
    _get_class_participants,
    _get_teacher_classes,
    _get_teacher_homeroom_classes,
)
from app.services.formal_service import get_student_formal_classroom
from app.services.majlis_enrollment_service import resolve_majlis_classroom
from app.utils.announcements import get_announcements_for_dashboard, mark_announcements_as_read
from app.utils.mobile_api_auth import (
    TOKEN_TYPE_ACCESS,
    TOKEN_TYPE_REFRESH,
    decode_mobile_token,
    issue_mobile_token_pair,
    revoke_mobile_token,
)
from app.utils.roles import get_default_role
from app.utils.tenant import resolve_tenant_id, scoped_classrooms_query
from app.utils.timezone import local_day_bounds_utc_naive, local_today, utc_now_naive


api_bp = Blueprint("api", __name__)
csrf.exempt(api_bp)


DAY_NAMES = {
    0: "Senin",
    1: "Selasa",
    2: "Rabu",
    3: "Kamis",
    4: "Jumat",
    5: "Sabtu",
    6: "Minggu",
}

ORDERED_DAYS = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]


def _api_success(data=None, message=None, status=200):
    payload = {"success": True, "data": data or {}}
    if message:
        payload["message"] = message
    return jsonify(payload), status


def _api_error(code, message, status=400):
    return jsonify({"success": False, "code": code, "message": message}), status


def _fmt_datetime(value):
    if not value:
        return "-"
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    return str(value)


def _fmt_date(value):
    if not value:
        return "-"
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    return str(value)


def _fmt_time(value):
    if not value:
        return "-"
    if hasattr(value, "strftime"):
        return value.strftime("%H:%M")
    return str(value)


def _extract_bearer_token():
    auth_header = (request.headers.get("Authorization") or "").strip()
    if not auth_header.lower().startswith("bearer "):
        return None
    return auth_header.split(" ", 1)[1].strip()


def _user_display_name(user):
    if not user:
        return "-"
    candidates = [
        getattr(getattr(user, "teacher_profile", None), "full_name", None),
        getattr(getattr(user, "staff_profile", None), "full_name", None),
        getattr(getattr(user, "parent_profile", None), "full_name", None),
        getattr(getattr(user, "student_profile", None), "full_name", None),
        getattr(getattr(user, "majlis_profile", None), "full_name", None),
        getattr(getattr(user, "boarding_guardian_profile", None), "full_name", None),
        getattr(user, "username", None),
    ]
    for candidate in candidates:
        if candidate and str(candidate).strip():
            return str(candidate).strip()
    return "-"


def _user_payload(user):
    roles = sorted([role.value for role in user.all_roles()])
    active_role = get_default_role(user) or user.role
    return {
        "id": user.id,
        "tenant_id": user.tenant_id,
        "name": _user_display_name(user),
        "full_name": _user_display_name(user),
        "username": user.username,
        "email": user.email,
        "role": active_role.value if active_role else "-",
        "active_role": active_role.value if active_role else "-",
        "roles": roles,
    }


def _announcement_payload(item):
    return {
        "id": item.id,
        "title": item.title or "-",
        "content": item.content or "-",
        "author_label": getattr(item, "author_label", None) or "Sistem",
        "created_at": _fmt_datetime(item.created_at),
        "is_unread": bool(getattr(item, "is_unread_for_current_user", False)),
    }


def _student_class_name(user, student):
    tenant_id = resolve_tenant_id(user, fallback_default=False)
    formal_class = get_student_formal_classroom(student)
    class_room = formal_class or student.current_class
    if class_room is None:
        return "-"
    if tenant_id is None:
        return class_room.name or "-"

    scoped_class = scoped_classrooms_query(tenant_id).filter(ClassRoom.id == class_room.id).first()
    return scoped_class.name if scoped_class else "-"


def _serialize_child(user, student):
    class_name = _student_class_name(user, student)
    return {
        "id": student.id,
        "name": student.full_name or "-",
        "full_name": student.full_name or "-",
        "class_name": class_name,
        "current_class_name": class_name,
    }


def _participant_name_from_record(record):
    if getattr(record, "student", None) and record.student.full_name:
        return record.student.full_name
    if getattr(record, "majlis_participant", None) and record.majlis_participant.full_name:
        return record.majlis_participant.full_name
    if getattr(record, "parent_participant", None) and record.parent_participant.full_name:
        return record.parent_participant.full_name
    return "-"


def _parent_children_for_tenant(user, parent):
    return (
        Student.query.join(User, Student.user_id == User.id)
        .filter(
            Student.parent_id == parent.id,
            User.tenant_id == user.tenant_id,
        )
        .order_by(Student.full_name.asc())
        .all()
    )


def mobile_auth_required(*roles):
    def decorator(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            access_token = _extract_bearer_token()
            if not access_token:
                return _api_error("unauthorized", "Token akses tidak ditemukan.", 401)

            try:
                payload = decode_mobile_token(access_token, TOKEN_TYPE_ACCESS)
            except ValueError as exc:
                return _api_error("unauthorized", str(exc), 401)

            user_id = payload.get("uid")
            token_tenant_id = payload.get("tid")
            user = User.query.filter_by(id=user_id).first()
            if user is None:
                return _api_error("unauthorized", "User tidak ditemukan.", 401)
            if token_tenant_id is not None and user.tenant_id != token_tenant_id:
                return _api_error("unauthorized", "Token tidak valid untuk tenant ini.", 401)

            if roles and not user.has_role(*roles):
                return _api_error("forbidden", "Akses role tidak diizinkan.", 403)

            g.mobile_user = user
            g.mobile_access_token = access_token
            g.mobile_access_payload = payload
            return fn(*args, **kwargs)

        return wrapped

    return decorator


@api_bp.post("/auth/login")
def auth_login():
    payload = request.get_json(silent=True) or {}
    identifier = (payload.get("identifier") or payload.get("login_id") or "").strip()
    password = payload.get("password") or ""

    if not identifier or not password:
        return _api_error("invalid_request", "Identifier dan password wajib diisi.", 400)

    user, is_ambiguous = _resolve_user_for_login(identifier)
    if is_ambiguous:
        return _api_error(
            "ambiguous_identifier",
            "Identifier terhubung ke lebih dari satu akun. Hubungi admin.",
            409,
        )
    if user is None or not user.check_password(password):
        return _api_error("invalid_credentials", "Username/Email/No identitas atau password salah.", 401)
    if user.must_change_password:
        return _api_error(
            "must_change_password",
            "Password default harus diganti terlebih dahulu melalui aplikasi web.",
            403,
        )

    tokens = issue_mobile_token_pair(user)
    user.last_login = utc_now_naive()
    db.session.commit()

    return _api_success(
        {
            "access_token": tokens["access_token"],
            "refresh_token": tokens["refresh_token"],
            "token_type": tokens["token_type"],
            "user": _user_payload(user),
        }
    )


@api_bp.get("/auth/me")
@mobile_auth_required()
def auth_me():
    return _api_success({"user": _user_payload(g.mobile_user)})


@api_bp.post("/auth/refresh")
def auth_refresh():
    payload = request.get_json(silent=True) or {}
    refresh_token = (payload.get("refresh_token") or "").strip()
    if not refresh_token:
        return _api_error("invalid_request", "refresh_token wajib diisi.", 400)

    try:
        refresh_payload = decode_mobile_token(refresh_token, TOKEN_TYPE_REFRESH)
    except ValueError as exc:
        return _api_error("unauthorized", str(exc), 401)

    user = User.query.filter_by(id=refresh_payload.get("uid")).first()
    if user is None:
        return _api_error("unauthorized", "User tidak ditemukan.", 401)
    if refresh_payload.get("tid") is not None and user.tenant_id != refresh_payload.get("tid"):
        return _api_error("unauthorized", "Token tidak valid untuk tenant ini.", 401)

    tokens = issue_mobile_token_pair(user)
    revoke_mobile_token(
        refresh_token,
        TOKEN_TYPE_REFRESH,
        expires_at=tokens["refresh_expires_at"],
    )
    db.session.commit()

    return _api_success(
        {
            "access_token": tokens["access_token"],
            "refresh_token": tokens["refresh_token"],
            "token_type": tokens["token_type"],
            "user": _user_payload(user),
        }
    )


@api_bp.post("/auth/logout")
@mobile_auth_required()
def auth_logout():
    payload = request.get_json(silent=True) or {}
    refresh_token = (payload.get("refresh_token") or "").strip()

    revoke_mobile_token(g.mobile_access_token, TOKEN_TYPE_ACCESS)

    if refresh_token:
        try:
            revoke_mobile_token(refresh_token, TOKEN_TYPE_REFRESH)
        except ValueError:
            pass

    db.session.commit()
    return _api_success({}, message="Logout berhasil.")


@api_bp.get("/parent/children")
@mobile_auth_required(UserRole.WALI_MURID)
def parent_children():
    user = g.mobile_user
    parent = user.parent_profile
    if parent is None:
        return _api_error("not_found", "Profil wali murid tidak ditemukan.", 404)

    children = _parent_children_for_tenant(user, parent)
    return _api_success(
        {
            "parent": {
                "id": parent.id,
                "full_name": parent.full_name or "-",
                "phone": parent.phone or "-",
                "is_majlis_participant": bool(parent.is_majlis_participant),
            },
            "children": [_serialize_child(user, child) for child in children],
        }
    )


@api_bp.get("/parent/dashboard")
@mobile_auth_required(UserRole.WALI_MURID)
def parent_dashboard():
    user = g.mobile_user
    parent = user.parent_profile
    if parent is None:
        return _api_error("not_found", "Profil wali murid tidak ditemukan.", 404)

    children = _parent_children_for_tenant(user, parent)
    if not children:
        return _api_error("not_found", "Data anak belum tersedia.", 404)

    selected_student_id = request.args.get("student_id", type=int)
    selected_child = None
    if selected_student_id:
        selected_child = next((item for item in children if item.id == selected_student_id), None)
        if selected_child is None:
            return _api_error("forbidden", "Akses data siswa tidak diizinkan.", 403)
    if selected_child is None:
        selected_child = children[0]

    summary = TahfidzSummary.query.filter_by(
        student_id=selected_child.id,
        participant_type=ParticipantType.STUDENT,
    ).first()
    memorization_progress = "-"
    if summary:
        target = []
        if summary.last_surah:
            target.append(summary.last_surah)
        if summary.last_ayat:
            target.append(str(summary.last_ayat))
        target_text = " : ".join(target) if target else "-"
        memorization_progress = f"{summary.total_juz or 0:.1f} Juz | {target_text}"

    latest_attendance = (
        Attendance.query.filter_by(
            student_id=selected_child.id,
            participant_type=ParticipantType.STUDENT,
        )
        .order_by(Attendance.date.desc(), Attendance.created_at.desc())
        .first()
    )
    attendance_status = latest_attendance.status.value if latest_attendance and latest_attendance.status else "-"

    invoices = (
        Invoice.query.filter_by(student_id=selected_child.id, is_deleted=False)
        .order_by(Invoice.created_at.desc())
        .all()
    )
    billing_total = float(
        sum(
            max(0, (invoice.total_amount or 0) - (invoice.paid_amount or 0))
            for invoice in invoices
            if invoice.status != PaymentStatus.PAID
        )
    )

    violations = selected_child.violations.all() if hasattr(selected_child.violations, "all") else []
    violation_points = sum(item.points or 0 for item in violations)

    recent_tahfidz = (
        TahfidzRecord.query.filter_by(
            student_id=selected_child.id,
            participant_type=ParticipantType.STUDENT,
        )
        .order_by(TahfidzRecord.date.desc())
        .limit(3)
        .all()
    )
    recent_recitation = (
        RecitationRecord.query.filter_by(
            student_id=selected_child.id,
            participant_type=ParticipantType.STUDENT,
        )
        .order_by(RecitationRecord.date.desc())
        .limit(3)
        .all()
    )
    recent_evaluations = (
        TahfidzEvaluation.query.filter_by(
            student_id=selected_child.id,
            participant_type=ParticipantType.STUDENT,
        )
        .order_by(TahfidzEvaluation.date.desc())
        .limit(3)
        .all()
    )

    activities = []
    for row in recent_tahfidz:
        activities.append(
            {
                "type": "tahfidz",
                "message": f"Setoran {row.type.value if row.type else 'Tahfidz'} - {row.surah or '-'}",
                "created_at": _fmt_datetime(row.date),
            }
        )
    for row in recent_recitation:
        material = row.book_name or row.surah or "Bacaan"
        activities.append(
            {
                "type": "recitation",
                "message": f"Setoran Bacaan - {material}",
                "created_at": _fmt_datetime(row.date),
            }
        )
    for row in recent_evaluations:
        activities.append(
            {
                "type": "evaluation",
                "message": f"Evaluasi Tahfidz - Nilai {row.score or 0}",
                "created_at": _fmt_datetime(row.date),
            }
        )
    activities = sorted(activities, key=lambda item: item["created_at"], reverse=True)[:8]

    target_ids = [user.id]
    if selected_child.user_id:
        target_ids.append(selected_child.user_id)

    active_class = get_student_formal_classroom(selected_child) or selected_child.current_class
    active_class_id = active_class.id if active_class else None
    tenant_id = resolve_tenant_id(user, fallback_default=False)
    if tenant_id and active_class_id:
        visible_class = scoped_classrooms_query(tenant_id).filter(ClassRoom.id == active_class_id).first()
        if visible_class is None:
            active_class_id = None
            active_class = None
        else:
            active_class = visible_class

    class_program = active_class.program_type.name if active_class and active_class.program_type else None
    announcements, unread_count = get_announcements_for_dashboard(
        user,
        class_ids=[active_class_id] if active_class_id else [],
        user_ids=target_ids,
        program_types=[class_program] if class_program else [],
        show_all=False,
    )

    return _api_success(
        {
            "guardian_name": parent.full_name or "-",
            "children": [_serialize_child(user, item) for item in children],
            "selected_child": _serialize_child(user, selected_child),
            "summary": {
                "billing_total": billing_total,
                "violation_points": violation_points,
                "memorization_progress": memorization_progress,
                "attendance_status": attendance_status,
            },
            "quick_actions": [
                {"key": "pengumuman", "label": "Pengumuman"},
                {"key": "keuangan", "label": "Keuangan"},
                {"key": "tahfidz", "label": "Tahfidz"},
                {"key": "jadwal", "label": "Jadwal"},
                {"key": "nilai", "label": "Nilai"},
                {"key": "absensi", "label": "Absensi"},
                {"key": "perilaku", "label": "Perilaku"},
            ],
            "recent_activities": activities,
            "announcements": [_announcement_payload(item) for item in announcements],
            "unread_announcements_count": unread_count,
            "is_majlis_participant": bool(parent.is_majlis_participant),
        }
    )


@api_bp.get("/teacher/dashboard")
@mobile_auth_required(UserRole.GURU)
def teacher_dashboard():
    user = g.mobile_user
    teacher = Teacher.query.filter_by(user_id=user.id).first()
    if teacher is None:
        return _api_error("not_found", "Profil guru tidak ditemukan.", 404)

    my_classes = _get_teacher_classes(teacher)
    homeroom_classes = _get_teacher_homeroom_classes(teacher)
    total_students = _count_teacher_students(my_classes) if my_classes else 0
    homeroom_class = homeroom_classes[0] if homeroom_classes else None
    _, teaching_assignments = _collect_teacher_assignment_summary(teacher)

    today = local_today()
    today_name = DAY_NAMES[today.weekday()]
    today_start_utc, today_end_utc = local_day_bounds_utc_naive(today)

    todays_schedules = (
        Schedule.query.filter_by(
            teacher_id=teacher.id,
            day=today_name,
            is_deleted=False,
        )
        .order_by(Schedule.start_time.asc())
        .all()
    )
    todays_schedules = [
        item
        for item in todays_schedules
        if _classroom_visible_for_teacher(teacher, item.class_room)
    ]

    today_tahfidz_count = TahfidzRecord.query.filter(
        TahfidzRecord.teacher_id == teacher.id,
        TahfidzRecord.date >= today_start_utc,
        TahfidzRecord.date < today_end_utc,
    ).count()
    today_recitation_count = RecitationRecord.query.filter(
        RecitationRecord.teacher_id == teacher.id,
        RecitationRecord.date >= today_start_utc,
        RecitationRecord.date < today_end_utc,
    ).count()
    today_evaluation_count = TahfidzEvaluation.query.filter(
        TahfidzEvaluation.teacher_id == teacher.id,
        TahfidzEvaluation.date >= today_start_utc,
        TahfidzEvaluation.date < today_end_utc,
    ).count()

    recent_tahfidz = (
        TahfidzRecord.query.filter_by(teacher_id=teacher.id)
        .order_by(TahfidzRecord.date.desc())
        .limit(5)
        .all()
    )
    recent_recitation = (
        RecitationRecord.query.filter_by(teacher_id=teacher.id)
        .order_by(RecitationRecord.date.desc())
        .limit(5)
        .all()
    )

    boarding_student_ids = set()
    for class_room in my_classes:
        students, _ = _get_class_participants(class_room.id, tenant_id=user.tenant_id)
        for student in students:
            if student.boarding_dormitory_id:
                boarding_student_ids.add(student.id)

    boarding_stats = {"hadir": 0, "sakit": 0, "izin": 0, "alpa": 0, "belum_input": 0}
    if boarding_student_ids:
        records = BoardingAttendance.query.filter(
            BoardingAttendance.date == today,
            BoardingAttendance.student_id.in_(list(boarding_student_ids)),
        ).all()
        seen_student_ids = set()
        for record in records:
            seen_student_ids.add(record.student_id)
            if record.status == AttendanceStatus.HADIR:
                boarding_stats["hadir"] += 1
            elif record.status == AttendanceStatus.SAKIT:
                boarding_stats["sakit"] += 1
            elif record.status == AttendanceStatus.IZIN:
                boarding_stats["izin"] += 1
            elif record.status == AttendanceStatus.ALPA:
                boarding_stats["alpa"] += 1
        boarding_stats["belum_input"] = max(0, len(boarding_student_ids) - len(seen_student_ids))

    class_programs = [item.program_type.name for item in my_classes if item and item.program_type]
    announcements, unread_count = get_announcements_for_dashboard(
        user,
        class_ids=[item.id for item in my_classes],
        user_ids=[user.id],
        program_types=class_programs,
        show_all=False,
    )

    if homeroom_class:
        homeroom_students, homeroom_majlis = _get_class_participants(homeroom_class.id, tenant_id=user.tenant_id)
        homeroom_menu = [
            {
                "key": "homeroom_students",
                "label": "Data Peserta",
                "description": "Lihat data siswa dan peserta aktif kelas perwalian.",
            },
            {
                "key": "class_announcements",
                "label": "Pengumuman Kelas",
                "description": "Kelola pengumuman khusus untuk kelas perwalian.",
            },
            {
                "key": "behavior_reports",
                "label": "Laporan Perilaku",
                "description": "Catat perkembangan perilaku siswa kelas perwalian.",
            },
        ]
        homeroom_payload = {
            "available": True,
            "class_id": homeroom_class.id,
            "class_name": homeroom_class.name or "-",
            "student_count": len(homeroom_students),
            "majlis_count": len(homeroom_majlis),
            "menu": homeroom_menu,
        }
    else:
        homeroom_payload = {
            "available": False,
            "class_id": 0,
            "class_name": "-",
            "student_count": 0,
            "majlis_count": 0,
            "menu": [],
        }

    return _api_success(
        {
            "profile": {
                "id": teacher.id,
                "full_name": teacher.full_name or _user_display_name(user),
                "nip": teacher.nip or "-",
                "homeroom_class_name": homeroom_class.name if homeroom_class else "Tidak Menjabat",
                "total_classes": len(my_classes),
                "total_students": total_students,
            },
            "summary": {
                "today_schedule_count": len(todays_schedules),
                "homeroom_label": homeroom_class.name if homeroom_class else "Tidak Menjabat",
                "today_tahfidz_count": today_tahfidz_count,
                "today_recitation_count": today_recitation_count,
                "today_evaluation_count": today_evaluation_count,
                "boarding": boarding_stats,
            },
            "announcements": [_announcement_payload(item) for item in announcements],
            "unread_announcements_count": unread_count,
            "today_name": today_name,
            "today_schedules": [
                {
                    "id": item.id,
                    "class_id": item.class_id or 0,
                    "class_name": item.class_room.name if item.class_room else "-",
                    "subject_id": item.subject_id or 0,
                    "majlis_subject_id": item.majlis_subject_id or 0,
                    "subject_name": (
                        item.subject.name
                        if item.subject
                        else (item.majlis_subject.name if item.majlis_subject else "-")
                    ),
                    "start_time": _fmt_time(item.start_time),
                    "end_time": _fmt_time(item.end_time),
                }
                for item in todays_schedules
            ],
            "teaching_assignments": [
                {
                    "class_id": class_id,
                    "class_name": class_name,
                    "subject_id": subject_id or 0,
                    "majlis_subject_id": majlis_subject_id or 0,
                    "subject_name": subject_name or "-",
                }
                for class_id, class_name, subject_id, majlis_subject_id, subject_name in teaching_assignments
            ],
            "class_options": [
                {"id": item.id, "name": item.name or "-"}
                for item in sorted(my_classes, key=lambda obj: obj.name or "")
            ],
            "input_menu": [
                {"key": "nilai", "label": "Input Nilai", "description": "Input nilai mapel untuk kelas yang diajar."},
                {"key": "absensi", "label": "Input Absensi", "description": "Catat kehadiran peserta per kelas."},
                {"key": "perilaku", "label": "Laporan Perilaku", "description": "Input catatan perilaku siswa."},
                {"key": "tahfidz", "label": "Input Tahfidz", "description": "Input setoran hafalan tahfidz."},
                {"key": "bacaan", "label": "Input Bacaan", "description": "Input setoran bacaan Al-Qur'an/kitab."},
                {"key": "evaluasi", "label": "Evaluasi Tahfidz", "description": "Input evaluasi periodik tahfidz."},
            ],
            "recent_tahfidz": [
                {
                    "id": item.id,
                    "participant_name": _participant_name_from_record(item),
                    "date": _fmt_datetime(item.date),
                    "detail": f"{item.surah or '-'} ({item.ayat_start or '-'}-{item.ayat_end or '-'})",
                    "score": item.score or 0,
                }
                for item in recent_tahfidz
            ],
            "recent_recitation": [
                {
                    "id": item.id,
                    "participant_name": _participant_name_from_record(item),
                    "date": _fmt_datetime(item.date),
                    "detail": item.book_name or item.surah or "-",
                    "score": item.score or 0,
                }
                for item in recent_recitation
            ],
            "history_menu": [
                {
                    "key": "riwayat_nilai",
                    "label": "Riwayat Nilai",
                    "description": "Lihat histori input nilai per kelas.",
                },
                {
                    "key": "riwayat_absensi",
                    "label": "Riwayat Absensi",
                    "description": "Lihat histori absensi yang telah diinput.",
                },
            ],
            "homeroom": homeroom_payload,
        }
    )


def _resolve_majlis_context(user):
    profile = user.majlis_profile
    parent_profile = user.parent_profile if user.has_role(UserRole.WALI_MURID) else None
    if profile is None:
        return None, parent_profile, None

    majlis_class = profile.majlis_class
    if parent_profile and getattr(parent_profile, "person_id", None):
        resolved = resolve_majlis_classroom(user.tenant_id, parent_profile.person_id)
        majlis_class = resolved or majlis_class
    if getattr(profile, "person_id", None):
        resolved = resolve_majlis_classroom(user.tenant_id, profile.person_id)
        majlis_class = resolved or majlis_class

    if majlis_class and user.tenant_id:
        scoped = scoped_classrooms_query(user.tenant_id).filter(ClassRoom.id == majlis_class.id).first()
        majlis_class = scoped

    return profile, parent_profile, majlis_class


def _majlis_announcements(user, profile, parent_profile, show_all=False):
    class_id = profile.majlis_class_id if profile else None
    if class_id is None and profile and getattr(profile, "person_id", None):
        majlis_class = resolve_majlis_classroom(user.tenant_id, profile.person_id)
        class_id = majlis_class.id if majlis_class else None
    if class_id is None and parent_profile and getattr(parent_profile, "person_id", None):
        majlis_class = resolve_majlis_classroom(user.tenant_id, parent_profile.person_id)
        class_id = majlis_class.id if majlis_class else None

    if class_id and user.tenant_id:
        scoped = scoped_classrooms_query(user.tenant_id).filter(ClassRoom.id == class_id).first()
        if scoped is None:
            class_id = None

    return get_announcements_for_dashboard(
        user,
        class_ids=[class_id] if class_id else [],
        user_ids=[user.id],
        program_types=[ProgramType.MAJLIS_TALIM.name],
        show_all=show_all,
    )


@api_bp.get("/majlis/announcements")
@mobile_auth_required(UserRole.MAJLIS_PARTICIPANT, UserRole.WALI_MURID)
def majlis_announcements():
    user = g.mobile_user
    profile, parent_profile, _ = _resolve_majlis_context(user)
    if profile is None:
        return _api_error("not_found", "Profil peserta majlis tidak ditemukan.", 404)

    scope = (request.args.get("scope") or "all").strip().lower()
    mark_as_read = (request.args.get("mark_as_read") or "").strip() in {"1", "true", "yes"}
    show_all = scope == "all"
    announcements, unread_count = _majlis_announcements(
        user,
        profile=profile,
        parent_profile=parent_profile,
        show_all=show_all,
    )
    if mark_as_read:
        mark_announcements_as_read(user, announcements)
        unread_count = 0

    return _api_success(
        {
            "items": [_announcement_payload(item) for item in announcements],
            "unread_announcements_count": unread_count,
        }
    )


@api_bp.get("/majlis/dashboard")
@mobile_auth_required(UserRole.MAJLIS_PARTICIPANT, UserRole.WALI_MURID)
def majlis_dashboard():
    user = g.mobile_user
    profile, parent_profile, majlis_class = _resolve_majlis_context(user)
    if profile is None:
        return _api_error("not_found", "Profil peserta majlis tidak ditemukan.", 404)

    summary_filters = [
        and_(
            TahfidzSummary.majlis_participant_id == profile.id,
            TahfidzSummary.participant_type == ParticipantType.EXTERNAL_MAJLIS,
        )
    ]
    tahfidz_filters = [
        and_(
            TahfidzRecord.majlis_participant_id == profile.id,
            TahfidzRecord.participant_type == ParticipantType.EXTERNAL_MAJLIS,
        )
    ]
    recitation_filters = [
        and_(
            RecitationRecord.majlis_participant_id == profile.id,
            RecitationRecord.participant_type == ParticipantType.EXTERNAL_MAJLIS,
        )
    ]
    evaluation_filters = [
        and_(
            TahfidzEvaluation.majlis_participant_id == profile.id,
            TahfidzEvaluation.participant_type == ParticipantType.EXTERNAL_MAJLIS,
        )
    ]
    attendance_filters = [
        and_(
            Attendance.majlis_participant_id == profile.id,
            Attendance.participant_type == ParticipantType.EXTERNAL_MAJLIS,
        )
    ]

    if parent_profile:
        summary_filters.append(
            and_(
                TahfidzSummary.parent_id == parent_profile.id,
                TahfidzSummary.participant_type == ParticipantType.PARENT_MAJLIS,
            )
        )
        tahfidz_filters.append(
            and_(
                TahfidzRecord.parent_id == parent_profile.id,
                TahfidzRecord.participant_type == ParticipantType.PARENT_MAJLIS,
            )
        )
        recitation_filters.append(
            and_(
                RecitationRecord.parent_id == parent_profile.id,
                RecitationRecord.participant_type == ParticipantType.PARENT_MAJLIS,
            )
        )
        evaluation_filters.append(
            and_(
                TahfidzEvaluation.parent_id == parent_profile.id,
                TahfidzEvaluation.participant_type == ParticipantType.PARENT_MAJLIS,
            )
        )
        attendance_filters.append(
            and_(
                Attendance.parent_id == parent_profile.id,
                Attendance.participant_type == ParticipantType.PARENT_MAJLIS,
            )
        )

    summary = TahfidzSummary.query.filter(or_(*summary_filters)).order_by(TahfidzSummary.updated_at.desc()).first()
    tahfidz_records = TahfidzRecord.query.filter(or_(*tahfidz_filters)).order_by(TahfidzRecord.date.desc()).limit(10).all()
    recitation_records = (
        RecitationRecord.query.filter(or_(*recitation_filters))
        .order_by(RecitationRecord.date.desc())
        .limit(10)
        .all()
    )
    evaluation_records = (
        TahfidzEvaluation.query.filter(or_(*evaluation_filters))
        .order_by(TahfidzEvaluation.date.desc())
        .limit(10)
        .all()
    )

    announcements, unread_count = _majlis_announcements(
        user,
        profile=profile,
        parent_profile=parent_profile,
        show_all=False,
    )

    attendance_rows = (
        Attendance.query.filter(or_(*attendance_filters))
        .order_by(Attendance.date.desc(), Attendance.created_at.desc())
        .limit(30)
        .all()
    )
    attendance_recap = {"hadir": 0, "sakit": 0, "izin": 0, "alpa": 0}
    for row in attendance_rows:
        if row.status == AttendanceStatus.HADIR:
            attendance_recap["hadir"] += 1
        elif row.status == AttendanceStatus.SAKIT:
            attendance_recap["sakit"] += 1
        elif row.status == AttendanceStatus.IZIN:
            attendance_recap["izin"] += 1
        elif row.status == AttendanceStatus.ALPA:
            attendance_recap["alpa"] += 1

    weekly_schedule = {day: [] for day in ORDERED_DAYS}
    if majlis_class:
        schedules = (
            Schedule.query.filter_by(class_id=majlis_class.id, is_deleted=False)
            .order_by(Schedule.start_time.asc())
            .all()
        )
        for item in schedules:
            if item.day in weekly_schedule:
                weekly_schedule[item.day].append(item)

    schedule_days = []
    for day in ORDERED_DAYS:
        schedule_days.append(
            {
                "day": day,
                "items": [
                    {
                        "id": item.id,
                        "start_time": _fmt_time(item.start_time),
                        "subject_name": (
                            item.majlis_subject.name
                            if item.majlis_subject
                            else (item.subject.name if item.subject else "-")
                        ),
                        "teacher_name": (
                            item.teacher.full_name if item.teacher and item.teacher.full_name else "-"
                        ),
                    }
                    for item in weekly_schedule[day]
                ],
            }
        )

    finance_payload = {
        "applicable": False,
        "invoices": [],
        "summary": {
            "total_amount": 0,
            "paid_amount": 0,
            "remaining_amount": 0,
            "unpaid_count": 0,
        },
    }
    if parent_profile:
        parent_invoices = (
            Invoice.query.join(Student, Invoice.student_id == Student.id).join(User, Student.user_id == User.id)
            .filter(
                Student.parent_id == parent_profile.id,
                User.tenant_id == user.tenant_id,
                Invoice.is_deleted.is_(False),
            )
            .order_by(Invoice.created_at.desc())
            .limit(25)
            .all()
        )
        total_amount = sum(item.total_amount or 0 for item in parent_invoices)
        paid_amount = sum(item.paid_amount or 0 for item in parent_invoices)
        remaining_amount = sum(max(0, (item.total_amount or 0) - (item.paid_amount or 0)) for item in parent_invoices)
        unpaid_count = sum(1 for item in parent_invoices if item.status != PaymentStatus.PAID)
        finance_payload = {
            "applicable": True,
            "invoices": [
                {
                    "id": item.id,
                    "invoice_number": item.invoice_number or "-",
                    "student_name": item.student.full_name if item.student else "-",
                    "fee_type": item.fee_type.name if item.fee_type else "-",
                    "remaining_amount": max(0, (item.total_amount or 0) - (item.paid_amount or 0)),
                    "status_label": item.status.value if item.status else "-",
                }
                for item in parent_invoices
            ],
            "summary": {
                "total_amount": total_amount,
                "paid_amount": paid_amount,
                "remaining_amount": remaining_amount,
                "unpaid_count": unpaid_count,
            },
        }

    summary_target = "-"
    if summary:
        target_parts = []
        if summary.last_surah:
            target_parts.append(summary.last_surah)
        if summary.last_ayat:
            target_parts.append(str(summary.last_ayat))
        summary_target = " : ".join(target_parts) if target_parts else "-"

    return _api_success(
        {
            "profile": {
                "id": profile.id,
                "full_name": profile.full_name or "-",
                "phone": profile.phone or "-",
                "address": profile.address or "-",
                "job": profile.job or "-",
                "majlis_class_id": majlis_class.id if majlis_class else 0,
                "majlis_class_name": majlis_class.name if majlis_class else "-",
                "join_date": _fmt_date(profile.join_date),
                "has_external_profile": bool(profile),
                "has_parent_profile": bool(parent_profile),
            },
            "summary": {
                "total_juz": summary.total_juz if summary else 0,
                "last_target_text": summary_target,
                "updated_at": _fmt_datetime(summary.updated_at if summary else None),
            },
            "announcements": [_announcement_payload(item) for item in announcements],
            "unread_announcements_count": unread_count,
            "tahfidz_records": [
                {
                    "id": item.id,
                    "date": _fmt_datetime(item.date),
                    "type_label": item.type.value if item.type else "-",
                    "surah": item.surah or "-",
                    "ayat_start": item.ayat_start or 0,
                    "ayat_end": item.ayat_end or 0,
                    "quality": item.quality or "-",
                    "score": item.score or 0,
                }
                for item in tahfidz_records
            ],
            "recitation_records": [
                {
                    "id": item.id,
                    "date": _fmt_datetime(item.date),
                    "recitation_source_label": item.recitation_source.value if item.recitation_source else "-",
                    "surah": item.surah or "-",
                    "ayat_start": item.ayat_start or 0,
                    "ayat_end": item.ayat_end or 0,
                    "book_name": item.book_name or "-",
                    "page_start": item.page_start or 0,
                    "page_end": item.page_end or 0,
                    "score": item.score or 0,
                }
                for item in recitation_records
            ],
            "evaluation_records": [
                {
                    "id": item.id,
                    "date": _fmt_datetime(item.date),
                    "period_type_label": item.period_type.value if item.period_type else "-",
                    "period_label": item.period_label or "-",
                    "score": item.score or 0,
                    "makhraj_errors": item.makhraj_errors or 0,
                    "tajwid_errors": item.tajwid_errors or 0,
                    "harakat_errors": item.harakat_errors or 0,
                }
                for item in evaluation_records
            ],
            "attendance": {
                "records": [
                    {
                        "id": item.id,
                        "date": _fmt_date(item.date),
                        "status": item.status.name if item.status else "-",
                        "status_label": item.status.value if item.status else "-",
                        "class_name": item.class_room.name if item.class_room else "-",
                        "teacher_name": item.teacher.full_name if item.teacher and item.teacher.full_name else "-",
                    }
                    for item in attendance_rows
                ],
                "recap": attendance_recap,
            },
            "schedule_days": schedule_days,
            "finance": finance_payload,
        }
    )
