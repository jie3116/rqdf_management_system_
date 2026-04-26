import hashlib
import uuid
from datetime import timedelta

from flask import current_app
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.extensions import db
from app.models import MobileRevokedToken
from app.utils.timezone import utc_now_naive


TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"


def _serializer():
    secret_key = current_app.config.get("SECRET_KEY")
    if not secret_key:
        raise RuntimeError("SECRET_KEY belum dikonfigurasi.")
    return URLSafeTimedSerializer(secret_key=secret_key, salt="mobile-api-auth-v1")


def _token_ttl_seconds(token_type):
    if token_type == TOKEN_TYPE_REFRESH:
        return int(current_app.config.get("MOBILE_REFRESH_TOKEN_TTL_SECONDS", 60 * 60 * 24 * 30))
    return int(current_app.config.get("MOBILE_ACCESS_TOKEN_TTL_SECONDS", 60 * 60 * 8))


def _token_hash(token):
    return hashlib.sha256((token or "").encode("utf-8")).hexdigest()


def issue_mobile_token(user_id, tenant_id, token_type):
    serializer = _serializer()
    payload = {
        "uid": int(user_id),
        "tid": int(tenant_id) if tenant_id is not None else None,
        "typ": token_type,
        "jti": uuid.uuid4().hex,
    }
    token = serializer.dumps(payload)
    expires_at = utc_now_naive() + timedelta(seconds=_token_ttl_seconds(token_type))
    return token, expires_at


def issue_mobile_token_pair(user):
    access_token, access_expires_at = issue_mobile_token(user.id, user.tenant_id, TOKEN_TYPE_ACCESS)
    refresh_token, refresh_expires_at = issue_mobile_token(user.id, user.tenant_id, TOKEN_TYPE_REFRESH)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "Bearer",
        "access_expires_at": access_expires_at,
        "refresh_expires_at": refresh_expires_at,
    }


def revoke_mobile_token(token, token_type, expires_at=None):
    token = (token or "").strip()
    if not token:
        return False

    token_hash = _token_hash(token)
    existing = MobileRevokedToken.query.filter_by(token_hash=token_hash).first()
    if existing:
        return False

    expires_at = expires_at or (utc_now_naive() + timedelta(seconds=_token_ttl_seconds(token_type)))
    db.session.add(
        MobileRevokedToken(
            token_hash=token_hash,
            token_type=token_type,
            expires_at=expires_at,
        )
    )
    return True


def cleanup_expired_revoked_tokens():
    now = utc_now_naive()
    MobileRevokedToken.query.filter(MobileRevokedToken.expires_at < now).delete(synchronize_session=False)


def is_mobile_token_revoked(token):
    token_hash = _token_hash(token)
    return (
        db.session.query(MobileRevokedToken.id)
        .filter(MobileRevokedToken.token_hash == token_hash)
        .first()
        is not None
    )


def decode_mobile_token(token, expected_type):
    raw_token = (token or "").strip()
    if not raw_token:
        raise ValueError("Token tidak ada.")

    cleanup_expired_revoked_tokens()
    if is_mobile_token_revoked(raw_token):
        raise ValueError("Token sudah tidak berlaku.")

    serializer = _serializer()
    try:
        payload = serializer.loads(raw_token, max_age=_token_ttl_seconds(expected_type))
    except SignatureExpired as exc:
        raise ValueError("Token kadaluarsa.") from exc
    except BadSignature as exc:
        raise ValueError("Token tidak valid.") from exc

    token_type = payload.get("typ")
    if token_type != expected_type:
        raise ValueError("Jenis token tidak sesuai.")

    user_id = payload.get("uid")
    if not user_id:
        raise ValueError("Payload token tidak valid.")

    return payload
