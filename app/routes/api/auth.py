from flask import g, request

from app.extensions import db
from app.models import User
from app.routes.auth import _resolve_user_for_login
from app.utils.mobile_api_auth import (
    TOKEN_TYPE_ACCESS,
    TOKEN_TYPE_REFRESH,
    decode_mobile_token,
    issue_mobile_token_pair,
    revoke_mobile_token,
)
from app.utils.timezone import utc_now_naive

from .common import api_error, api_success, mobile_auth_required, user_payload


def register_auth_routes(api_bp):
    @api_bp.post("/auth/login")
    def auth_login():
        payload = request.get_json(silent=True) or {}
        identifier = (payload.get("identifier") or payload.get("login_id") or "").strip()
        password = payload.get("password") or ""

        if not identifier or not password:
            return api_error("invalid_request", "Identifier dan password wajib diisi.", 400)

        user, is_ambiguous = _resolve_user_for_login(identifier)
        if is_ambiguous:
            return api_error(
                "ambiguous_identifier",
                "Identifier terhubung ke lebih dari satu akun. Hubungi admin.",
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
