from datetime import timedelta

import pytest

from app import create_app
from app.extensions import db
from app.models import MobileRateLimitBucket
from app.services.auth_rate_limit_service import (
    check_auth_rate_limit,
    record_auth_rate_limit_failure,
)
from app.utils.timezone import utc_now_naive


class TestConfig:
    SECRET_KEY = "test-secret"
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    AUTH_RATE_LIMIT_ENABLED = True
    AUTH_RATE_LIMIT_WINDOW_SECONDS = 300
    AUTH_RATE_LIMIT_IDENTIFIER_ATTEMPTS = 2
    AUTH_RATE_LIMIT_IDENTIFIER_IP_ATTEMPTS = 2
    AUTH_RATE_LIMIT_IP_ATTEMPTS = 20
    AUTH_RATE_LIMIT_CLEANUP_PROBABILITY = 0


@pytest.fixture()
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def test_rate_limit_creates_hashed_buckets_without_raw_pii(app):
    identifier = "User.One+Test@example.test"
    tenant_hint = {"tenant_code": "TENANT-ABC"}
    ip_address = "203.0.113.10"

    record_auth_rate_limit_failure(
        "mobile_login",
        identifier,
        tenant_hint=tenant_hint,
        ip_address=ip_address,
    )

    buckets = MobileRateLimitBucket.query.order_by(MobileRateLimitBucket.scope_key.asc()).all()
    assert len(buckets) == 3
    for bucket in buckets:
        assert bucket.action_name == "mobile_login"
        assert bucket.count == 1
        assert "User.One" not in bucket.bucket_key
        assert "example.test" not in bucket.bucket_key
        assert "TENANT-ABC" not in bucket.bucket_key
        assert "203.0.113.10" not in bucket.bucket_key
        assert "example.test" not in bucket.scope_key
        assert "TENANT-ABC" not in bucket.scope_key


def test_rate_limit_blocks_after_configured_identifier_attempts(app):
    identifier = "blocked@example.test"

    assert not check_auth_rate_limit("mobile_login", identifier, ip_address="203.0.113.20").limited
    record_auth_rate_limit_failure("mobile_login", identifier, ip_address="203.0.113.20")
    assert not check_auth_rate_limit("mobile_login", identifier, ip_address="203.0.113.20").limited
    record_auth_rate_limit_failure("mobile_login", identifier, ip_address="203.0.113.20")

    decision = check_auth_rate_limit("mobile_login", identifier, ip_address="203.0.113.20")

    assert decision.limited is True
    assert decision.retry_after_seconds > 0
    assert decision.limited_scope in {"identifier_tenant", "identifier_tenant_ip"}


def test_rate_limit_window_expires(app):
    now = utc_now_naive()
    identifier = "window@example.test"

    record_auth_rate_limit_failure("web_login", identifier, ip_address="203.0.113.30", now=now)
    record_auth_rate_limit_failure("web_login", identifier, ip_address="203.0.113.30", now=now)
    assert check_auth_rate_limit("web_login", identifier, ip_address="203.0.113.30", now=now).limited

    later = now + timedelta(seconds=301)

    assert not check_auth_rate_limit("web_login", identifier, ip_address="203.0.113.30", now=later).limited


def test_tenant_hint_and_ip_partition_buckets(app):
    identifier = "same@example.test"

    record_auth_rate_limit_failure(
        "mobile_login",
        identifier,
        tenant_hint={"tenant_code": "A"},
        ip_address="203.0.113.40",
    )
    record_auth_rate_limit_failure(
        "mobile_login",
        identifier,
        tenant_hint={"tenant_code": "B"},
        ip_address="203.0.113.40",
    )
    record_auth_rate_limit_failure(
        "mobile_login",
        identifier,
        tenant_hint={"tenant_code": "A"},
        ip_address="203.0.113.41",
    )

    scope_keys = {bucket.scope_key for bucket in MobileRateLimitBucket.query.all()}

    assert len(scope_keys) > 3

