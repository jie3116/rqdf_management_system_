from flask import g, request
from sqlalchemy import or_

from app.extensions import db
from app.models import BoardingGuardian, MajlisParticipant, Parent, Student, Teacher, Tenant, User
from app.routes.auth import _resolve_user_for_login
from app.utils.mobile_api_auth import (
    TOKEN_TYPE_ACCESS,
    TOKEN_TYPE_REFRESH,
    decode_mobile_token,
    issue_mobile_token_pair,
    revoke_mobile_token,
)
from app.utils.push_notifications import (
    deactivate_mobile_device_token,
    upsert_mobile_device_token,
)
from app.utils.timezone import utc_now_naive

from .common import api_error, api_success, mobile_auth_required, user_payload


def _safe_int(raw_value):
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return None


def _resolve_tenant_hint(payload):
    tenant_id = _safe_int(payload.get("tenant_id")) or _safe_int(request.headers.get("X-Tenant-Id"))
    if tenant_id:
        tenant = Tenant.query.filter_by(id=tenant_id).first()
        if tenant:
            return tenant.id

    tenant_code = (
        (payload.get("tenant_code") or request.headers.get("X-Tenant-Code") or "").strip()
    )
    if tenant_code:
        tenant = Tenant.query.filter_by(code=tenant_code).first()
        if tenant:
            return tenant.id

    tenant_slug = (
        (payload.get("tenant_slug") or request.headers.get("X-Tenant-Slug") or "").strip()
    )
    if tenant_slug:
        tenant = Tenant.query.filter_by(slug=tenant_slug).first()
        if tenant:
            return tenant.id

    return None


def _resolve_user_for_login_tenant(login_id, tenant_id):
    identifier = (login_id or "").strip()
    if not identifier or tenant_id is None:
        return None, False

    direct_users = (
        User.query.filter(
            User.tenant_id == tenant_id,
            or_(User.email == identifier, User.username == identifier),
        )
        .order_by(User.id.asc())
        .limit(2)
        .all()
    )
    if len(direct_users) > 1:
        return None, True
    if len(direct_users) == 1:
        return direct_users[0], False

    candidate_ids = set()

    teacher_rows = (
        db.session.query(Teacher.user_id)
        .join(User, Teacher.user_id == User.id)
        .filter(
            User.tenant_id == tenant_id,
            or_(Teacher.nip == identifier, Teacher.phone == identifier),
        )
        .all()
    )
    candidate_ids.update(row[0] for row in teacher_rows if row[0])

    parent_rows = (
        db.session.query(Parent.user_id)
        .join(User, Parent.user_id == User.id)
        .filter(
            User.tenant_id == tenant_id,
            Parent.phone == identifier,
        )
        .all()
    )
    candidate_ids.update(row[0] for row in parent_rows if row[0])

    majlis_rows = (
        db.session.query(MajlisParticipant.user_id)
        .join(User, MajlisParticipant.user_id == User.id)
        .filter(
            User.tenant_id == tenant_id,
            MajlisParticipant.phone == identifier,
        )
        .all()
    )
    candidate_ids.update(row[0] for row in majlis_rows if row[0])

    guardian_rows = (
        db.session.query(BoardingGuardian.user_id)
        .join(User, BoardingGuardian.user_id == User.id)
        .filter(
            User.tenant_id == tenant_id,
            BoardingGuardian.phone == identifier,
        )
        .all()
    )
    candidate_ids.update(row[0] for row in guardian_rows if row[0])

    student_rows = (
        db.session.query(Student.user_id)
        .join(User, Student.user_id == User.id)
        .filter(
            User.tenant_id == tenant_id,
            or_(Student.nis == identifier, Student.nisn == identifier),
        )
        .all()
    )
    candidate_ids.update(row[0] for row in student_rows if row[0])

    if not candidate_ids:
        return None, False
    if len(candidate_ids) > 1:
        return None, True

    user = User.query.get(next(iter(candidate_ids)))
    return user, False


def register_auth_routes(api_bp):
    @api_bp.post("/auth/login")
    def auth_login():
        payload = request.get_json(silent=True) or {}
        identifier = (payload.get("identifier") or payload.get("login_id") or "").strip()
        password = payload.get("password") or ""
        tenant_hint_id = _resolve_tenant_hint(payload)

        if not identifier or not password:
            return api_error("invalid_request", "Identifier dan password wajib diisi.", 400)

        user, is_ambiguous = _resolve_user_for_login(identifier)
        if tenant_hint_id is not None and (is_ambiguous or user is None or user.tenant_id != tenant_hint_id):
            tenant_scoped_user, tenant_scoped_ambiguous = _resolve_user_for_login_tenant(identifier, tenant_hint_id)
            if tenant_scoped_ambiguous:
                user, is_ambiguous = None, True
            elif tenant_scoped_user is not None:
                user, is_ambiguous = tenant_scoped_user, False

        if is_ambiguous:
            return api_error(
                "ambiguous_identifier",
                "Identifier terhubung ke lebih dari satu akun. Tambahkan tenant_code/tenant_slug/tenant_id saat login.",
                409,
            )
        if user is None or not user.check_password(password):
            return api_error("invalid_credentials", "Username/Email/No identitas atau password salah.", 401)
        if user.must_change_password:
            return api_error(
                "must_change_password",
                "Password default harus diganti terlebih dahulu melalui aplikasi web.",
                403,
            )

        tokens = issue_mobile_token_pair(user)
        user.last_login = utc_now_naive()
        db.session.commit()

        return api_success(
            {
                "access_token": tokens["access_token"],
                "refresh_token": tokens["refresh_token"],
                "token_type": tokens["token_type"],
                "user": user_payload(user),
            }
        )

    @api_bp.get("/auth/me")
    @mobile_auth_required()
    def auth_me():
        return api_success({"user": user_payload(g.mobile_user)})

    @api_bp.post("/auth/refresh")
    def auth_refresh():
        payload = request.get_json(silent=True) or {}
        refresh_token = (payload.get("refresh_token") or "").strip()
        if not refresh_token:
            return api_error("invalid_request", "refresh_token wajib diisi.", 400)

        try:
            refresh_payload = decode_mobile_token(refresh_token, TOKEN_TYPE_REFRESH)
        except ValueError as exc:
            return api_error("unauthorized", str(exc), 401)

        user = User.query.filter_by(id=refresh_payload.get("uid")).first()
        if user is None:
            return api_error("unauthorized", "User tidak ditemukan.", 401)
        if refresh_payload.get("tid") is not None and user.tenant_id != refresh_payload.get("tid"):
            return api_error("unauthorized", "Token tidak valid untuk tenant ini.", 401)

        tokens = issue_mobile_token_pair(user)
        revoke_mobile_token(
            refresh_token,
            TOKEN_TYPE_REFRESH,
            expires_at=tokens["refresh_expires_at"],
        )
        db.session.commit()

        return api_success(
            {
                "access_token": tokens["access_token"],
                "refresh_token": tokens["refresh_token"],
                "token_type": tokens["token_type"],
                "user": user_payload(user),
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
        return api_success({}, message="Logout berhasil.")

    @api_bp.post("/auth/push-token")
    @mobile_auth_required()
    def auth_push_token():
        payload = request.get_json(silent=True) or {}
        token = (payload.get("token") or "").strip()
        is_active = payload.get("is_active")
        should_activate = not (is_active is False)

        if not token:
            return api_error("invalid_request", "Token device wajib diisi.", 400)

        if should_activate:
            upsert_mobile_device_token(
                g.mobile_user,
                token,
                platform=(payload.get("platform") or "unknown"),
                device_name=payload.get("device_name"),
                app_version=payload.get("app_version"),
            )
        else:
            deactivate_mobile_device_token(g.mobile_user, token=token)

        db.session.commit()
        return api_success({"token": token, "is_active": should_activate})
