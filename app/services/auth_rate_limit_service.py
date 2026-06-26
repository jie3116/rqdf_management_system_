import hashlib
import hmac
import random
import re
from dataclasses import dataclass
from datetime import timedelta

from flask import current_app, request
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import MobileRateLimitBucket
from app.utils.timezone import utc_now_naive


SCOPE_IDENTIFIER_TENANT = "identifier_tenant"
SCOPE_IDENTIFIER_TENANT_IP = "identifier_tenant_ip"
SCOPE_IP = "ip"


@dataclass(frozen=True)
class RateLimitDecision:
    limited: bool
    retry_after_seconds: int = 0
    limited_scope: str | None = None


def _enabled():
    return bool(current_app.config.get("AUTH_RATE_LIMIT_ENABLED", True))


def _window_seconds():
    return max(1, int(current_app.config.get("AUTH_RATE_LIMIT_WINDOW_SECONDS", 300)))


def _limit_for_scope(scope_type):
    if scope_type == SCOPE_IP:
        return max(1, int(current_app.config.get("AUTH_RATE_LIMIT_IP_ATTEMPTS", 30)))
    if scope_type == SCOPE_IDENTIFIER_TENANT_IP:
        return max(1, int(current_app.config.get("AUTH_RATE_LIMIT_IDENTIFIER_IP_ATTEMPTS", 5)))
    return max(1, int(current_app.config.get("AUTH_RATE_LIMIT_IDENTIFIER_ATTEMPTS", 5)))


def _hash_secret():
    return (
        current_app.config.get("AUTH_RATE_LIMIT_HASH_PEPPER")
        or current_app.config.get("SECRET_KEY")
        or "auth-rate-limit"
    )


def _digest(value):
    return hmac.new(
        str(_hash_secret()).encode("utf-8"),
        str(value or "").encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def normalize_identifier(identifier):
    return re.sub(r"\s+", " ", str(identifier or "").strip().lower()) or "none"


def normalize_tenant_hint(tenant_hint=None):
    if tenant_hint is None:
        return "none"
    if isinstance(tenant_hint, dict):
        parts = []
        for key in sorted(tenant_hint):
            value = str(tenant_hint.get(key) or "").strip().lower()
            if value:
                parts.append(f"{key}:{value}")
        return "|".join(parts) or "none"
    return re.sub(r"\s+", " ", str(tenant_hint or "").strip().lower()) or "none"


def current_request_ip():
    return request.remote_addr or "unknown"


def _normalize_ip(ip_address):
    return str(ip_address or "unknown").strip().lower() or "unknown"


def _window_start_epoch(now):
    timestamp = int(now.timestamp())
    window_seconds = _window_seconds()
    return timestamp - (timestamp % window_seconds)


def _window_end(now):
    window_ends_epoch = _window_start_epoch(now) + _window_seconds()
    remaining_seconds = max(1, window_ends_epoch - int(now.timestamp()))
    return now + timedelta(seconds=remaining_seconds)


def _bucket_specs(action_name, identifier, tenant_hint=None, ip_address=None, now=None):
    now = now or utc_now_naive()
    action = str(action_name or "auth").strip().lower()
    identifier_hash = _digest(normalize_identifier(identifier))
    tenant_hash = _digest(normalize_tenant_hint(tenant_hint))
    ip_hash = _digest(_normalize_ip(ip_address or current_request_ip()))
    window_start = _window_start_epoch(now)

    raw_specs = [
        (
            SCOPE_IDENTIFIER_TENANT,
            f"id:{identifier_hash}:tenant:{tenant_hash}",
        ),
        (
            SCOPE_IDENTIFIER_TENANT_IP,
            f"id:{identifier_hash}:tenant:{tenant_hash}:ip:{ip_hash}",
        ),
        (
            SCOPE_IP,
            f"ip:{ip_hash}",
        ),
    ]

    specs = []
    for scope_type, scope_material in raw_specs:
        scope_hash = _digest(scope_material)
        scope_key = f"{scope_type}:{scope_hash}"
        bucket_key = f"auth:v1:{action}:{scope_type}:{scope_hash}:{window_start}"
        specs.append(
            {
                "action_name": action,
                "scope_type": scope_type,
                "scope_key": scope_key,
                "bucket_key": bucket_key,
            }
        )
    return specs


def _maybe_cleanup_expired(now):
    probability = float(current_app.config.get("AUTH_RATE_LIMIT_CLEANUP_PROBABILITY", 0.01))
    if probability <= 0 or random.random() > probability:
        return
    MobileRateLimitBucket.query.filter(MobileRateLimitBucket.window_ends_at < now).delete(
        synchronize_session=False
    )


def check_auth_rate_limit(action_name, identifier, tenant_hint=None, ip_address=None, now=None):
    if not _enabled():
        return RateLimitDecision(limited=False)

    now = now or utc_now_naive()
    specs = _bucket_specs(action_name, identifier, tenant_hint=tenant_hint, ip_address=ip_address, now=now)
    buckets = {
        row.bucket_key: row
        for row in MobileRateLimitBucket.query.filter(
            MobileRateLimitBucket.bucket_key.in_([spec["bucket_key"] for spec in specs])
        ).all()
    }

    for spec in specs:
        bucket = buckets.get(spec["bucket_key"])
        if bucket is None or bucket.window_ends_at <= now:
            continue
        if int(bucket.count or 0) >= _limit_for_scope(spec["scope_type"]):
            retry_after = max(1, int((bucket.window_ends_at - now).total_seconds()))
            return RateLimitDecision(
                limited=True,
                retry_after_seconds=retry_after,
                limited_scope=spec["scope_type"],
            )

    return RateLimitDecision(limited=False)


def record_auth_rate_limit_failure(action_name, identifier, tenant_hint=None, ip_address=None, now=None):
    if not _enabled():
        return

    now = now or utc_now_naive()
    _maybe_cleanup_expired(now)
    for spec in _bucket_specs(action_name, identifier, tenant_hint=tenant_hint, ip_address=ip_address, now=now):
        _increment_bucket(spec, now)
    db.session.commit()


def _increment_bucket(spec, now):
    bucket = MobileRateLimitBucket.query.filter_by(bucket_key=spec["bucket_key"]).first()
    if bucket is None:
        bucket = MobileRateLimitBucket(
            bucket_key=spec["bucket_key"],
            action_name=spec["action_name"],
            scope_key=spec["scope_key"],
            count=1,
            window_ends_at=_window_end(now),
            created_at=now,
            updated_at=now,
        )
        db.session.add(bucket)
        try:
            db.session.flush()
            return
        except IntegrityError:
            db.session.rollback()
            bucket = MobileRateLimitBucket.query.filter_by(bucket_key=spec["bucket_key"]).first()
            if bucket is None:
                raise

    if bucket.window_ends_at <= now:
        bucket.count = 1
        bucket.window_ends_at = _window_end(now)
    else:
        bucket.count = int(bucket.count or 0) + 1
    bucket.updated_at = now
    db.session.add(bucket)
    db.session.flush()
