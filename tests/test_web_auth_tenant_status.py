import pytest

from app import create_app
from app.extensions import db
from app.models import Tenant, TenantStatus, User, UserRole


PASSWORD = "ValidPass123!"


class TestConfig:
    SECRET_KEY = "test-secret"
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False


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

    def create_tenant(*, status=TenantStatus.ACTIVE, is_deleted=False):
        nonlocal counter
        counter += 1
        tenant = Tenant(
            name=f"Tenant {counter}",
            slug=f"tenant-{counter}",
            code=f"T{counter}",
            status=status,
            is_deleted=is_deleted,
            is_default=(counter == 1),
        )
        db.session.add(tenant)
        db.session.flush()
        return tenant

    return create_tenant


@pytest.fixture()
def user_factory(app):
    counter = 0

    def create_user(*, tenant, role=UserRole.SISWA):
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


def login_web(client, user):
    return client.post(
        "/auth/login",
        data={
            "login_id": user.username,
            "password": PASSWORD,
        },
        follow_redirects=False,
    )


def assert_logged_in_session_is_cleared(client):
    with client.session_transaction() as session:
        assert "_user_id" not in session
        assert "active_role" not in session


def test_web_session_allows_active_tenant(client, tenant_factory, user_factory):
    tenant = tenant_factory(status=TenantStatus.ACTIVE)
    user = user_factory(tenant=tenant)
    db.session.commit()

    login_response = login_web(client, user)
    assert login_response.status_code == 302
    assert login_response.headers["Location"].endswith("/dashboard")

    response = client.get("/dashboard", follow_redirects=False)

    assert response.status_code == 302
    assert not response.headers["Location"].endswith("/auth/login")
    with client.session_transaction() as session:
        assert session.get("_user_id") == str(user.id)
        assert session.get("active_role") == UserRole.SISWA.name


@pytest.mark.parametrize(
    ("tenant_status", "is_deleted"),
    [
        pytest.param(TenantStatus.SUSPENDED, False, id="suspended"),
        pytest.param(TenantStatus.ARCHIVED, False, id="archived"),
        pytest.param(TenantStatus.ACTIVE, True, id="soft-deleted"),
    ],
)
def test_web_session_is_rejected_after_tenant_becomes_inactive(
    client,
    tenant_factory,
    user_factory,
    tenant_status,
    is_deleted,
):
    tenant = tenant_factory(status=TenantStatus.ACTIVE)
    user = user_factory(tenant=tenant)
    db.session.commit()

    login_response = login_web(client, user)
    assert login_response.status_code == 302

    tenant.status = tenant_status
    tenant.is_deleted = is_deleted
    db.session.commit()

    response = client.get("/dashboard", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/auth/login")
    assert_logged_in_session_is_cleared(client)
