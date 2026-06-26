import pytest

from app import create_app
from app.extensions import db
from app.models import MobileRateLimitBucket, Tenant, TenantStatus, User, UserRole


PASSWORD = "ValidPass123!"


class TestConfig:
    SECRET_KEY = "test-secret"
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MOBILE_ACCESS_TOKEN_TTL_SECONDS = 3600
    MOBILE_REFRESH_TOKEN_TTL_SECONDS = 86400
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


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def tenant_factory(app):
    counter = 0

    def create_tenant(*, status=TenantStatus.ACTIVE):
        nonlocal counter
        counter += 1
        tenant = Tenant(
            name=f"Tenant {counter}",
            slug=f"tenant-{counter}",
            code=f"T{counter}",
            status=status,
            is_default=(counter == 1),
        )
        db.session.add(tenant)
        db.session.flush()
        return tenant

    return create_tenant


@pytest.fixture()
def user_factory(app):
    counter = 0

    def create_user(*, tenant, username=None, password=PASSWORD, must_change_password=False):
        nonlocal counter
        counter += 1
        user = User(
            tenant_id=tenant.id,
            username=username or f"user-{counter}",
            email=f"user-{counter}@example.test",
            role=UserRole.SISWA,
            must_change_password=must_change_password,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.flush()
        return user

    return create_user


def post_mobile_login(client, identifier, password, extra=None):
    payload = {"identifier": identifier, "password": password}
    payload.update(extra or {})
    return client.post("/api/v1/auth/login", json=payload)


def post_web_login(client, identifier, password):
    return client.post(
        "/auth/login",
        data={"login_id": identifier, "password": password},
        follow_redirects=False,
    )


def test_mobile_login_returns_429_after_repeated_invalid_password(client, tenant_factory, user_factory):
    tenant = tenant_factory()
    user = user_factory(tenant=tenant, username="mobile-user")
    db.session.commit()

    first = post_mobile_login(client, user.username, "wrong")
    second = post_mobile_login(client, user.username, "wrong")
    blocked = post_mobile_login(client, user.username, "wrong")

    assert first.status_code == 401
    assert second.status_code == 401
    assert blocked.status_code == 429
    assert blocked.get_json()["code"] == "too_many_requests"


def test_mobile_valid_credentials_do_not_bypass_existing_rate_limit(client, tenant_factory, user_factory):
    tenant = tenant_factory()
    user = user_factory(tenant=tenant, username="blocked-valid")
    db.session.commit()

    post_mobile_login(client, user.username, "wrong")
    post_mobile_login(client, user.username, "wrong")
    blocked = post_mobile_login(client, user.username, PASSWORD)

    assert blocked.status_code == 429
    assert blocked.get_json()["code"] == "too_many_requests"


def test_mobile_tenant_inactive_counts_as_failed_attempt(client, tenant_factory, user_factory):
    tenant = tenant_factory(status=TenantStatus.SUSPENDED)
    user = user_factory(tenant=tenant, username="inactive-user")
    db.session.commit()

    first = post_mobile_login(client, user.username, PASSWORD)
    second = post_mobile_login(client, user.username, PASSWORD)
    blocked = post_mobile_login(client, user.username, PASSWORD)

    assert first.status_code == 403
    assert first.get_json()["code"] == "tenant_inactive"
    assert second.status_code == 403
    assert blocked.status_code == 429
    assert blocked.get_json()["code"] == "too_many_requests"


def test_mobile_must_change_password_does_not_count_as_failed_attempt(client, tenant_factory, user_factory):
    tenant = tenant_factory()
    user = user_factory(tenant=tenant, username="must-change", must_change_password=True)
    db.session.commit()

    first = post_mobile_login(client, user.username, PASSWORD)
    second = post_mobile_login(client, user.username, PASSWORD)
    third = post_mobile_login(client, user.username, PASSWORD)

    assert first.status_code == 403
    assert first.get_json()["code"] == "must_change_password"
    assert second.status_code == 403
    assert third.status_code == 403
    assert third.get_json()["code"] == "must_change_password"
    assert MobileRateLimitBucket.query.count() == 0


def test_mobile_ambiguous_identifier_is_rate_limited(client, tenant_factory, user_factory):
    tenant_a = tenant_factory()
    tenant_b = tenant_factory()
    user_factory(tenant=tenant_a, username="shared-login")
    user_factory(tenant=tenant_b, username="shared-login")
    db.session.commit()

    first = post_mobile_login(client, "shared-login", PASSWORD)
    second = post_mobile_login(client, "shared-login", PASSWORD)
    blocked = post_mobile_login(client, "shared-login", PASSWORD)

    assert first.status_code == 409
    assert second.status_code == 409
    assert blocked.status_code == 429
    assert blocked.get_json()["code"] == "too_many_requests"


def test_web_login_rate_limit_renders_login_without_redirect(client, tenant_factory, user_factory):
    tenant = tenant_factory()
    user = user_factory(tenant=tenant, username="web-user")
    db.session.commit()

    first = post_web_login(client, user.username, "wrong")
    second = post_web_login(client, user.username, "wrong")
    blocked = post_web_login(client, user.username, PASSWORD)

    assert first.status_code == 200
    assert second.status_code == 200
    assert blocked.status_code == 200
    with client.session_transaction() as session:
        assert "_user_id" not in session
    assert sum(bucket.count for bucket in MobileRateLimitBucket.query.all()) == 6


def test_web_valid_login_below_limit_still_succeeds(client, tenant_factory, user_factory):
    tenant = tenant_factory()
    user = user_factory(tenant=tenant, username="web-valid")
    db.session.commit()

    response = post_web_login(client, user.username, PASSWORD)

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/dashboard")
