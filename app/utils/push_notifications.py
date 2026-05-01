import os
from typing import Iterable

from flask import current_app
from sqlalchemy import or_

from app.extensions import db
from app.models import (
    Announcement,
    ClassRoom,
    MajlisParticipant,
    MobileDeviceToken,
    Parent,
    ProgramType,
    Schedule,
    Student,
    Teacher,
    User,
    UserRole,
    UserRoleAssignment,
)
from app.utils.timezone import utc_now_naive

try:
    import firebase_admin
    from firebase_admin import credentials, messaging
except Exception:  # pragma: no cover - optional dependency at runtime
    firebase_admin = None
    credentials = None
    messaging = None


_firebase_app = None
_firebase_initialized = False


def upsert_mobile_device_token(
    user,
    token,
    *,
    platform="unknown",
    device_name=None,
    app_version=None,
):
    clean_token = (token or "").strip()
    if not clean_token:
        return None

    row = MobileDeviceToken.query.filter_by(token=clean_token).first()
    if row is None:
        row = MobileDeviceToken(token=clean_token)

    row.user_id = user.id
    row.platform = (platform or "unknown").strip().lower()[:20] or "unknown"
    row.device_name = (device_name or "").strip()[:120] or None
    row.app_version = (app_version or "").strip()[:40] or None
    row.is_active = True
    row.is_deleted = False
    row.last_seen_at = utc_now_naive()
    db.session.add(row)
    return row


def deactivate_mobile_device_token(user, token=None):
    query = MobileDeviceToken.query.filter_by(user_id=user.id, is_deleted=False)
    clean_token = (token or "").strip()
    if clean_token:
        query = query.filter(MobileDeviceToken.token == clean_token)

    rows = query.all()
    for row in rows:
        row.is_active = False
        row.last_seen_at = utc_now_naive()
    return len(rows)


def notify_announcement_created(announcement):
    if announcement is None or not announcement.is_active:
        return

    firebase_app = _get_firebase_app()
    if firebase_app is None:
        return

    recipient_ids = _announcement_recipient_user_ids(announcement)
    if not recipient_ids:
        return

    author_id = announcement.user_id or 0
    recipient_ids.discard(author_id)
    if not recipient_ids:
        return

    tokens = [
        row.token
        for row in MobileDeviceToken.query.filter(
            MobileDeviceToken.user_id.in_(list(recipient_ids)),
            MobileDeviceToken.is_active.is_(True),
            MobileDeviceToken.is_deleted.is_(False),
        ).all()
        if (row.token or "").strip()
    ]
    if not tokens:
        return

    body = (announcement.content or "").strip()
    if len(body) > 140:
        body = f"{body[:137].rstrip()}..."
    if not body:
        body = "Ada pengumuman baru."

    title = (announcement.title or "").strip() or "Pengumuman Baru"
    data = {
        "type": "announcement",
        "announcement_id": str(announcement.id or 0),
        "target_scope": (announcement.target_scope or "ALL").upper(),
    }

    chunk_size = 500
    for start in range(0, len(tokens), chunk_size):
        chunk_tokens = tokens[start : start + chunk_size]
        multicast = messaging.MulticastMessage(
            tokens=chunk_tokens,
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            data=data,
            android=messaging.AndroidConfig(priority="high"),
        )
        response = messaging.send_each_for_multicast(multicast, app=firebase_app)
        _mark_invalid_tokens(chunk_tokens, response)

    db.session.commit()


def _get_firebase_app():
    global _firebase_app, _firebase_initialized
    if _firebase_initialized:
        return _firebase_app

    _firebase_initialized = True
    if firebase_admin is None:
        current_app.logger.warning("firebase_admin belum terpasang; FCM dilewati.")
        return None

    credential_path = (
        os.environ.get("FCM_SERVICE_ACCOUNT_JSON")
        or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        or ""
    ).strip()
    if not credential_path:
        current_app.logger.info("FCM credential belum dikonfigurasi; FCM dilewati.")
        return None
    if not os.path.exists(credential_path):
        current_app.logger.warning(
            "FCM credential tidak ditemukan di path: %s", credential_path
        )
        return None

    try:
        cred = credentials.Certificate(credential_path)
        _firebase_app = firebase_admin.initialize_app(cred)
    except Exception:
        current_app.logger.exception("Gagal inisialisasi Firebase Admin.")
        _firebase_app = None
    return _firebase_app


def _announcement_recipient_user_ids(announcement):
    author = announcement.author or User.query.filter_by(id=announcement.user_id).first()
    if author is None:
        return set()

    tenant_id = author.tenant_id
    scope = (announcement.target_scope or "ALL").upper()
    if scope == "USER":
        return {announcement.target_user_id} if announcement.target_user_id else set()
    if scope == "CLASS":
        return _class_recipient_user_ids(announcement.target_class_id, tenant_id)
    if scope == "ROLE":
        return _role_recipient_user_ids(announcement.target_role, tenant_id)
    if scope == "PROGRAM":
        return _program_recipient_user_ids(announcement.target_program_type, tenant_id)
    return {
        row.id
        for row in User.query.filter(
            User.tenant_id == tenant_id,
            User.is_deleted.is_(False),
        ).all()
    }


def _class_recipient_user_ids(class_id, tenant_id):
    if not class_id:
        return set()

    user_ids = set()

    student_user_ids = db.session.query(Student.user_id).join(
        User, Student.user_id == User.id
    ).filter(
        Student.current_class_id == class_id,
        Student.user_id.isnot(None),
        User.tenant_id == tenant_id,
        User.is_deleted.is_(False),
    ).all()
    user_ids.update(row[0] for row in student_user_ids if row[0])

    parent_user_ids = db.session.query(Parent.user_id).join(
        Student, Parent.id == Student.parent_id
    ).join(
        User, Parent.user_id == User.id
    ).filter(
        Student.current_class_id == class_id,
        Parent.user_id.isnot(None),
        User.tenant_id == tenant_id,
        User.is_deleted.is_(False),
    ).all()
    user_ids.update(row[0] for row in parent_user_ids if row[0])

    majlis_parent_user_ids = db.session.query(Parent.user_id).join(
        User, Parent.user_id == User.id
    ).filter(
        Parent.majlis_class_id == class_id,
        Parent.user_id.isnot(None),
        User.tenant_id == tenant_id,
        User.is_deleted.is_(False),
    ).all()
    user_ids.update(row[0] for row in majlis_parent_user_ids if row[0])

    majlis_external_user_ids = db.session.query(MajlisParticipant.user_id).join(
        User, MajlisParticipant.user_id == User.id
    ).filter(
        MajlisParticipant.majlis_class_id == class_id,
        MajlisParticipant.user_id.isnot(None),
        User.tenant_id == tenant_id,
        User.is_deleted.is_(False),
    ).all()
    user_ids.update(row[0] for row in majlis_external_user_ids if row[0])

    teacher_user_ids = db.session.query(Teacher.user_id).join(
        User, Teacher.user_id == User.id
    ).outerjoin(
        Schedule, Schedule.teacher_id == Teacher.id
    ).outerjoin(
        ClassRoom, ClassRoom.homeroom_teacher_id == Teacher.id
    ).filter(
        User.tenant_id == tenant_id,
        User.is_deleted.is_(False),
        or_(
            Schedule.class_id == class_id,
            ClassRoom.id == class_id,
        ),
    ).all()
    user_ids.update(row[0] for row in teacher_user_ids if row[0])

    return user_ids


def _role_recipient_user_ids(role_value, tenant_id):
    role_key = (role_value or "").strip()
    if not role_key:
        return set()
    try:
        target_role = UserRole(role_key)
    except ValueError:
        return set()

    direct_ids = db.session.query(User.id).filter(
        User.tenant_id == tenant_id,
        User.role == target_role,
        User.is_deleted.is_(False),
    ).all()
    assigned_ids = db.session.query(UserRoleAssignment.user_id).join(
        User, UserRoleAssignment.user_id == User.id
    ).filter(
        User.tenant_id == tenant_id,
        UserRoleAssignment.role == target_role,
        User.is_deleted.is_(False),
    ).all()

    result = {row[0] for row in direct_ids if row[0]}
    result.update(row[0] for row in assigned_ids if row[0])
    return result


def _program_recipient_user_ids(program_type_value, tenant_id):
    program_key = (program_type_value or "").strip()
    if not program_key:
        return set()
    try:
        program_type = ProgramType[program_key]
    except KeyError:
        return set()

    class_ids = [
        row[0]
        for row in db.session.query(ClassRoom.id).filter(
            ClassRoom.program_type == program_type,
        ).all()
        if row[0]
    ]
    if not class_ids:
        return set()

    user_ids = set()
    for class_id in class_ids:
        user_ids.update(_class_recipient_user_ids(class_id, tenant_id))
    return user_ids


def _mark_invalid_tokens(tokens: Iterable[str], response):
    if response is None:
        return

    responses = getattr(response, "responses", []) or []
    for index, token in enumerate(tokens):
        if index >= len(responses):
            continue
        item = responses[index]
        if getattr(item, "success", False):
            continue

        exception = getattr(item, "exception", None)
        message_text = str(exception or "").lower()
        is_invalid = (
            "registration-token-not-registered" in message_text
            or "invalid-registration-token" in message_text
            or "invalid argument" in message_text
        )
        if not is_invalid:
            continue

        row = MobileDeviceToken.query.filter_by(token=token).first()
        if row:
            row.is_active = False
            row.last_seen_at = utc_now_naive()

