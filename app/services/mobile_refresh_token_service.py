import uuid

from app.extensions import db
from app.models import MobileRefreshToken
from app.utils.mobile_api_auth import mobile_token_hash
from app.utils.timezone import utc_now_naive


SESSION_EXPIRED_MESSAGE = "Sesi sudah tidak berlaku. Silakan login ulang."


def new_refresh_token_family_id():
    return uuid.uuid4().hex


def create_refresh_token_record(user, refresh_token, refresh_payload, expires_at, *, family_id=None):
    now = utc_now_naive()
    record = MobileRefreshToken(
        user_id=user.id,
        tenant_id=user.tenant_id,
        family_id=family_id or new_refresh_token_family_id(),
        jti=str(refresh_payload.get("jti") or ""),
        token_hash=mobile_token_hash(refresh_token),
        status=MobileRefreshToken.STATUS_ACTIVE,
        issued_at=now,
        expires_at=expires_at,
        created_at=now,
        updated_at=now,
    )
    db.session.add(record)
    return record


def _revoke_active_family_tokens(family_id, now):
    if not family_id:
        return 0
    return (
        MobileRefreshToken.query.filter(
            MobileRefreshToken.family_id == family_id,
            MobileRefreshToken.status == MobileRefreshToken.STATUS_ACTIVE,
        ).update(
            {
                "status": MobileRefreshToken.STATUS_REVOKED,
                "revoked_at": now,
                "updated_at": now,
            },
            synchronize_session=False,
        )
    )


def _mark_reuse_and_revoke_family(record, now):
    if record is None:
        return

    record.reuse_detected_at = record.reuse_detected_at or now
    record.status = MobileRefreshToken.STATUS_REUSED
    record.updated_at = now
    _revoke_active_family_tokens(record.family_id, now)


def consume_refresh_token_for_rotation(refresh_token, refresh_payload, user):
    jti = refresh_payload.get("jti")
    if not jti:
        return None

    now = utc_now_naive()
    token_hash = mobile_token_hash(refresh_token)
    record = (
        MobileRefreshToken.query.filter_by(jti=jti)
        .with_for_update()
        .first()
    )
    if record is None:
        return None

    is_valid_active_token = (
        record.status == MobileRefreshToken.STATUS_ACTIVE
        and record.expires_at > now
        and record.user_id == user.id
        and record.tenant_id == user.tenant_id
        and record.token_hash == token_hash
    )
    if not is_valid_active_token:
        _mark_reuse_and_revoke_family(record, now)
        return None

    record.status = MobileRefreshToken.STATUS_CONSUMED
    record.consumed_at = now
    record.updated_at = now
    return record


def attach_replacement_refresh_token(old_record, new_jti):
    old_record.replaced_by_jti = str(new_jti or "")
    old_record.updated_at = utc_now_naive()
    return old_record


def revoke_refresh_token_family_for_payload(refresh_token, refresh_payload):
    jti = (refresh_payload or {}).get("jti")
    if not jti:
        return False

    now = utc_now_naive()
    token_hash = mobile_token_hash(refresh_token)
    record = (
        MobileRefreshToken.query.filter_by(jti=jti)
        .with_for_update()
        .first()
    )
    if record is None or record.token_hash != token_hash:
        return False

    if record.status == MobileRefreshToken.STATUS_ACTIVE:
        record.status = MobileRefreshToken.STATUS_REVOKED
        record.revoked_at = now
        record.updated_at = now

    _revoke_active_family_tokens(record.family_id, now)
    return True
