import pytest

from app import create_app
from app.extensions import db
from app.models import AppConfig, Tenant, TenantStatus, User, UserRole
from app.utils.tenant_modules import (
    CAPABILITY_BOARDING,
    CAPABILITY_FINANCE,
    CAPABILITY_MAJLIS,
    CAPABILITY_TEACHER,
    PACKAGE_FULL,
    PACKAGE_RUMAH_QURAN,
    PACKAGE_SEKOLAH,
    TENANT_PACKAGE_KEY,
    tenant_has_capability,
)


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

    def create_tenant(*, package, status=TenantStatus.ACTIVE):
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
        db.session.add(
            AppConfig(
                tenant_id=tenant.id,
                key=TENANT_PACKAGE_KEY,
                value=package,
                description="Test tenant package",
            )
        )
        db.session.flush()
        return tenant

    return create_tenant


@pytest.fixture()
def user_factory(app):
    counter = 0

    def create_user(*, tenant, role):
        nonlocal counter
        counter += 1
        user = User(
            tenant_id=tenant.id,
            username=f"user-{counter}",
            email=f"user-{counter}@example.test",
            role=role,
            must_change_password=False,
        )
        user.set_password(PASSWORD)
        db.session.add(user)
        db.session.flush()
        return user

    return create_user


def login_mobile(client, user):
    return client.post(
        "/api/v1/auth/login",
        json={"identifier": user.username, "password": PASSWORD},
    )


def bearer_headers(access_token):
    return {"Authorization": f"Bearer {access_token}"}


def authenticated_get(client, user, path):
    login_response = login_mobile(client, user)
    assert login_response.status_code == 200
    access_token = login_response.get_json()["data"]["access_token"]
    return client.get(path, headers=bearer_headers(access_token))


def assert_capability_disabled(response):
    payload = response.get_json()
    assert response.status_code == 403
    assert payload["success"] is False
    assert payload["code"] == "capability_disabled"


def assert_not_capability_disabled(response):
    payload = response.get_json()
    assert not (
        response.status_code == 403
        and payload
        and payload.get("code") == "capability_disabled"
    )


@pytest.mark.parametrize(
    ("package", "expected"),
    [
        (PACKAGE_FULL, {CAPABILITY_TEACHER, CAPABILITY_BOARDING, CAPABILITY_MAJLIS, CAPABILITY_FINANCE}),
        (PACKAGE_SEKOLAH, {CAPABILITY_TEACHER}),
        (PACKAGE_RUMAH_QURAN, {CAPABILITY_MAJLIS}),
    ],
)
def test_legacy_package_adapter_capabilities(tenant_factory, package, expected):
    tenant = tenant_factory(package=package)
    db.session.commit()

    for capability in [CAPABILITY_TEACHER, CAPABILITY_BOARDING, CAPABILITY_MAJLIS, CAPABILITY_FINANCE]:
        assert tenant_has_capability(tenant.id, capability) is (capability in expected)


@pytest.mark.parametrize(
    "capability",
    [CAPABILITY_TEACHER, CAPABILITY_BOARDING, CAPABILITY_MAJLIS],
)
def test_tenant_has_capability_fails_closed_without_tenant_id(capability):
    assert tenant_has_capability(None, capability) is False


def test_sekolah_allows_teacher(client, tenant_factory, user_factory):
    tenant = tenant_factory(package=PACKAGE_SEKOLAH)
    user = user_factory(tenant=tenant, role=UserRole.GURU)
    db.session.commit()

    response = authenticated_get(client, user, "/api/v1/teacher/dashboard")

    assert_not_capability_disabled(response)


def test_sekolah_rejects_boarding(client, tenant_factory, user_factory):
    tenant = tenant_factory(package=PACKAGE_SEKOLAH)
    user = user_factory(tenant=tenant, role=UserRole.WALI_ASRAMA)
    db.session.commit()

    response = authenticated_get(client, user, "/api/v1/boarding/dashboard")

    assert_capability_disabled(response)


def test_sekolah_rejects_majlis(client, tenant_factory, user_factory):
    tenant = tenant_factory(package=PACKAGE_SEKOLAH)
    user = user_factory(tenant=tenant, role=UserRole.MAJLIS_PARTICIPANT)
    db.session.commit()

    response = authenticated_get(client, user, "/api/v1/majlis/dashboard")

    assert_capability_disabled(response)


def test_rumah_quran_allows_majlis(client, tenant_factory, user_factory):
    tenant = tenant_factory(package=PACKAGE_RUMAH_QURAN)
    user = user_factory(tenant=tenant, role=UserRole.MAJLIS_PARTICIPANT)
    db.session.commit()

    response = authenticated_get(client, user, "/api/v1/majlis/dashboard")

    assert_not_capability_disabled(response)


def test_rumah_quran_rejects_teacher(client, tenant_factory, user_factory):
    tenant = tenant_factory(package=PACKAGE_RUMAH_QURAN)
    user = user_factory(tenant=tenant, role=UserRole.GURU)
    db.session.commit()

    response = authenticated_get(client, user, "/api/v1/teacher/dashboard")

    assert_capability_disabled(response)


def test_rumah_quran_rejects_boarding(client, tenant_factory, user_factory):
    tenant = tenant_factory(package=PACKAGE_RUMAH_QURAN)
    user = user_factory(tenant=tenant, role=UserRole.WALI_ASRAMA)
    db.session.commit()

    response = authenticated_get(client, user, "/api/v1/boarding/dashboard")

    assert_capability_disabled(response)


@pytest.mark.parametrize(
    ("role", "path"),
    [
        (UserRole.GURU, "/api/v1/teacher/dashboard"),
        (UserRole.WALI_ASRAMA, "/api/v1/boarding/dashboard"),
        (UserRole.MAJLIS_PARTICIPANT, "/api/v1/majlis/dashboard"),
    ],
)
def test_full_allows_teacher_boarding_and_majlis(client, tenant_factory, user_factory, role, path):
    tenant = tenant_factory(package=PACKAGE_FULL)
    user = user_factory(tenant=tenant, role=role)
    db.session.commit()

    response = authenticated_get(client, user, path)

    assert_not_capability_disabled(response)
