import pytest

from app import create_app
from app.extensions import db
from app.models import MobileRevokedToken, Tenant, TenantStatus, User, UserRole


PASSWORD = "ValidPass123!"


class TestConfig:
    SECRET_KEY = "test-secret"
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MOBILE_ACCESS_TOKEN_TTL_SECONDS = 3600
    MOBILE_REFRESH_TOKEN_TTL_SECONDS = 86400


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

    def create_tenant(*, status=TenantStatus.ACTIVE, name=None, slug=None, code=None):
        nonlocal counter
        counter += 1
        tenant = Tenant(
            name=name or f"Tenant {counter}",
            slug=slug or f"tenant-{counter}",
            code=code or f"T{counter}",
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

    def create_user(
        *,
        tenant,
        username=None,
        email=None,
        password=PASSWORD,
        role=UserRole.SISWA,
    ):
        nonlocal counter
        counter += 1
        user = User(
            tenant_id=tenant.id,
            username=username or f"user-{counter}",
            email=email or f"user-{counter}@example.test",
            role=role,
            must_change_password=False,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.flush()
        return user

    return create_user


def login_mobile(client, identifier, password=PASSWORD, payload_extra=None, headers=None):
    payload = {
        "identifier": identifier,
        "password": password,
    }
    payload.update(payload_extra or {})
    return client.post("/api/v1/auth/login", json=payload, headers=headers or {})


def bearer_headers(access_token):
    return {"Authorization": f"Bearer {access_token}"}


def assert_tenant_inactive(response):
    payload = response.get_json()
    assert response.status_code == 403
    assert payload["success"] is False
    assert payload["code"] == "tenant_inactive"
    assert "data" not in payload


def test_mobile_login_allows_active_tenant(client, tenant_factory, user_factory):
    tenant = tenant_factory(status=TenantStatus.ACTIVE)
    user = user_factory(tenant=tenant, username="active-user")
    db.session.commit()

    response = login_mobile(client, user.username)

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["data"]["access_token"]
    assert payload["data"]["refresh_token"]
    assert payload["data"]["token_type"] == "Bearer"
    assert payload["data"]["user"]["id"] == user.id
    assert payload["data"]["user"]["tenant_id"] == tenant.id

    db.session.refresh(user)
    assert user.last_login is not None

    me_response = client.get(
        "/api/v1/auth/me",
        headers=bearer_headers(payload["data"]["access_token"]),
    )
    assert me_response.status_code == 200
    assert me_response.get_json()["data"]["user"]["id"] == user.id


def test_mobile_login_rejects_suspended_tenant(client, tenant_factory, user_factory):
    tenant = tenant_factory(status=TenantStatus.SUSPENDED)
    user = user_factory(tenant=tenant, username="suspended-user")
    db.session.commit()

    response = login_mobile(client, user.username)

    assert_tenant_inactive(response)
    db.session.refresh(user)
    assert user.last_login is None
    assert MobileRevokedToken.query.count() == 0


def test_mobile_login_rejects_archived_tenant(client, tenant_factory, user_factory):
    tenant = tenant_factory(status=TenantStatus.ARCHIVED)
    user = user_factory(tenant=tenant, username="archived-user")
    db.session.commit()

    response = login_mobile(client, user.username)

    assert_tenant_inactive(response)
    db.session.refresh(user)
    assert user.last_login is None
    assert MobileRevokedToken.query.count() == 0


def test_mobile_refresh_rejects_token_after_tenant_is_suspended(
    client,
    tenant_factory,
    user_factory,
):
    tenant = tenant_factory(status=TenantStatus.ACTIVE)
    user = user_factory(tenant=tenant, username="refresh-user")
    db.session.commit()

    login_response = login_mobile(client, user.username)
    assert login_response.status_code == 200
    refresh_token = login_response.get_json()["data"]["refresh_token"]

    tenant.status = TenantStatus.SUSPENDED
    db.session.commit()

    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )

    assert_tenant_inactive(response)


def test_mobile_access_token_is_rejected_after_tenant_is_suspended(
    client,
    tenant_factory,
    user_factory,
):
    tenant = tenant_factory(status=TenantStatus.ACTIVE)
    user = user_factory(tenant=tenant, username="access-user")
    db.session.commit()

    login_response = login_mobile(client, user.username)
    assert login_response.status_code == 200
    access_token = login_response.get_json()["data"]["access_token"]

    before_suspension = client.get(
        "/api/v1/auth/me",
        headers=bearer_headers(access_token),
    )
    assert before_suspension.status_code == 200

    tenant.status = TenantStatus.SUSPENDED
    db.session.commit()

    after_suspension = client.get(
        "/api/v1/auth/me",
        headers=bearer_headers(access_token),
    )

    assert_tenant_inactive(after_suspension)


HINT_CASES = [
    pytest.param("json", "tenant_id", id="json-tenant-id"),
    pytest.param("json", "tenant_code", id="json-tenant-code"),
    pytest.param("json", "tenant_slug", id="json-tenant-slug"),
    pytest.param("header", "X-Tenant-Id", id="header-tenant-id"),
    pytest.param("header", "X-Tenant-Code", id="header-tenant-code"),
    pytest.param("header", "X-Tenant-Slug", id="header-tenant-slug"),
]


@pytest.mark.parametrize(("location", "key"), HINT_CASES)
def test_mobile_login_rejects_suspended_tenant_hint(
    client,
    tenant_factory,
    user_factory,
    location,
    key,
):
    active_tenant = tenant_factory(
        status=TenantStatus.ACTIVE,
        name="Active Tenant",
        slug="active-tenant",
        code="ACTIVE",
    )
    suspended_tenant = tenant_factory(
        status=TenantStatus.SUSPENDED,
        name="Suspended Tenant",
        slug="suspended-tenant",
        code="SUSPENDED",
    )
    shared_identifier = "shared-user"
    user_factory(
        tenant=active_tenant,
        username=shared_identifier,
        email="shared-active@example.test",
    )
    suspended_user = user_factory(
        tenant=suspended_tenant,
        username=shared_identifier,
        email="shared-suspended@example.test",
    )
    db.session.commit()

    hint_value_by_key = {
        "tenant_id": suspended_tenant.id,
        "tenant_code": suspended_tenant.code,
        "tenant_slug": suspended_tenant.slug,
        "X-Tenant-Id": str(suspended_tenant.id),
        "X-Tenant-Code": suspended_tenant.code,
        "X-Tenant-Slug": suspended_tenant.slug,
    }
    payload_extra = {}
    headers = {}
    if location == "json":
        payload_extra[key] = hint_value_by_key[key]
    else:
        headers[key] = hint_value_by_key[key]

    response = login_mobile(
        client,
        shared_identifier,
        payload_extra=payload_extra,
        headers=headers,
    )

    assert_tenant_inactive(response)
    db.session.refresh(suspended_user)
    assert suspended_user.last_login is None
