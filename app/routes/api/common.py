from datetime import datetime
from functools import wraps

from flask import g, jsonify, request

from app.models import ClassRoom, Student, User
from app.services.formal_service import get_student_formal_classroom
from app.utils.mobile_api_auth import TOKEN_TYPE_ACCESS, decode_mobile_token
from app.utils.roles import get_default_role
from app.utils.tenant import resolve_tenant_id, scoped_classrooms_query


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


def api_success(data=None, message=None, status=200):
    payload = {"success": True, "data": data or {}}
    if message:
        payload["message"] = message
    return jsonify(payload), status


def api_error(code, message, status=400):
    return jsonify({"success": False, "code": code, "message": message}), status


def fmt_datetime(value):
    if not value:
        return "-"
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    return str(value)


def fmt_date(value):
    if not value:
        return "-"
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    return str(value)


def fmt_time(value):
    if not value:
        return "-"
    if hasattr(value, "strftime"):
        return value.strftime("%H:%M")
    return str(value)


def extract_bearer_token():
    auth_header = (request.headers.get("Authorization") or "").strip()
    if not auth_header.lower().startswith("bearer "):
        return None
    return auth_header.split(" ", 1)[1].strip()


def user_display_name(user):
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


def user_payload(user):
    roles = sorted([role.value for role in user.all_roles()])
    active_role = get_default_role(user) or user.role
    return {
        "id": user.id,
        "tenant_id": user.tenant_id,
        "name": user_display_name(user),
        "full_name": user_display_name(user),
        "username": user.username,
        "email": user.email,
        "role": active_role.value if active_role else "-",
        "active_role": active_role.value if active_role else "-",
        "roles": roles,
    }


def announcement_payload(item):
    return {
        "id": item.id,
        "title": item.title or "-",
        "content": item.content or "-",
        "author_label": getattr(item, "author_label", None) or "Sistem",
        "created_at": fmt_datetime(item.created_at),
        "is_unread": bool(getattr(item, "is_unread_for_current_user", False)),
    }


def student_class_name(user, student):
    tenant_id = resolve_tenant_id(user, fallback_default=False)
    formal_class = get_student_formal_classroom(student)
    class_room = formal_class or student.current_class
    if class_room is None:
        return "-"
    if tenant_id is None:
        return class_room.name or "-"

    scoped_class = scoped_classrooms_query(tenant_id).filter(ClassRoom.id == class_room.id).first()
    return scoped_class.name if scoped_class else "-"


def serialize_child(user, student):
    class_name = student_class_name(user, student)
    return {
        "id": student.id,
        "name": student.full_name or "-",
        "full_name": student.full_name or "-",
        "class_name": class_name,
        "current_class_name": class_name,
    }


def participant_name_from_record(record):
    if getattr(record, "student", None) and record.student.full_name:
        return record.student.full_name
    if getattr(record, "majlis_participant", None) and record.majlis_participant.full_name:
        return record.majlis_participant.full_name
    if getattr(record, "parent_participant", None) and record.parent_participant.full_name:
        return record.parent_participant.full_name
    return "-"


def parent_children_for_tenant(user, parent):
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
            access_token = extract_bearer_token()
            if not access_token:
                return api_error("unauthorized", "Token akses tidak ditemukan.", 401)

            try:
                payload = decode_mobile_token(access_token, TOKEN_TYPE_ACCESS)
            except ValueError as exc:
                return api_error("unauthorized", str(exc), 401)

            user_id = payload.get("uid")
            token_tenant_id = payload.get("tid")
            user = User.query.filter_by(id=user_id).first()
            if user is None:
                return api_error("unauthorized", "User tidak ditemukan.", 401)
            if token_tenant_id is not None and user.tenant_id != token_tenant_id:
                return api_error("unauthorized", "Token tidak valid untuk tenant ini.", 401)

            if roles and not user.has_role(*roles):
                return api_error("forbidden", "Akses role tidak diizinkan.", 403)

            g.mobile_user = user
            g.mobile_access_token = access_token
            g.mobile_access_payload = payload
            return fn(*args, **kwargs)

        return wrapped

    return decorator
