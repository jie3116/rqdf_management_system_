import pytest
from itsdangerous import URLSafeTimedSerializer

from app import create_app
from app.extensions import db
from app.models import MobileRevokedToken, Parent, Staff, Teacher, Tenant, TenantStatus, User, UserRole
from app.services.credential_security_service import set_user_password_and_invalidate_tokens
from app.utils.mobile_api_auth import TOKEN_TYPE_ACCESS, TOKEN_TYPE_REFRESH, decode_mobile_token


PASSWORD = "ValidPass123!"
NEW_PASSWORD = "NextPass123!"


class TestConfig:
    SECRET_KEY = "test-secret"
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MOBILE_ACCESS_TOKEN_TTL_SECONDS = 3600
    MOBILE_REFRESH_TOKEN_TTL_SECONDS = 86400
    AUTH_RATE_LIMIT_ENABLED = False


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
def tenant(app):
    tenant = Tenant(
        name="Tenant",
        slug="tenant",
        code="TENANT",
        status=TenantStatus.ACTIVE,
        is_default=True,
    )
    db.session.add(tenant)
    db.session.flush()
    return tenant


def create_user(*, tenant, username, role=UserRole.SISWA, password=PASSWORD):
    user = User(
        tenant_id=tenant.id,
        username=username,
        email=f"{username}@example.test",
        role=role,
        must_change_password=False,
    )
    user.set_password(password)
    db.session.add(user)
    db.session.flush()
    return user


def login_mobile(client, username, password=PASSWORD):
    return client.post(
        "/api/v1/auth/login",
        json={"identifier": username, "password": password},
    )


def login_web(client, username, password=PASSWORD):
    return client.post(
        "/auth/login",
        data={"login_id": username, "password": password},
        follow_redirects=False,
    )


def bearer_headers(token):
    return {"Authorization": f"Bearer {token}"}


def token_pair(client, user, password=PASSWORD):
    response = login_mobile(client, user.username, password=password)
    assert response.status_code == 200
    return response.get_json()["data"]


def assert_unauthorized_session_expired(response):
    payload = response.get_json()
    assert response.status_code == 401
    assert payload["success"] is False
    assert payload["code"] == "unauthorized"
    assert payload["message"] == "Sesi sudah tidak berlaku. Silakan login ulang."


def legacy_mobile_token(user, token_type):
    serializer = URLSafeTimedSerializer(
        secret_key=TestConfig.SECRET_KEY,
        salt="mobile-api-auth-v1",
    )
    return serializer.dumps(
        {
            "uid": user.id,
            "tid": user.tenant_id,
            "typ": token_type,
            "jti": "legacy-token",
        }
    )


def login_admin(client, tenant):
    admin = create_user(tenant=tenant, username="admin", role=UserRole.ADMIN)
    db.session.commit()
    response = login_web(client, admin.username)
    assert response.status_code == 302
    return admin


def test_login_issues_token_with_current_version(client, tenant):
    user = create_user(tenant=tenant, username="mobile-user")
    db.session.commit()

    tokens = token_pair(client, user)
    payload = decode_mobile_token(tokens["access_token"], TOKEN_TYPE_ACCESS)

    assert payload["ver"] == user.token_version == 0


def test_old_access_and_refresh_tokens_rejected_after_password_change(client, tenant):
    user = create_user(tenant=tenant, username="change-user")
    db.session.commit()
    tokens = token_pair(client, user)

    set_user_password_and_invalidate_tokens(user, NEW_PASSWORD)
    db.session.commit()

    access_response = client.get("/api/v1/auth/me", headers=bearer_headers(tokens["access_token"]))
    refresh_response = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})

    assert_unauthorized_session_expired(access_response)
    assert_unauthorized_session_expired(refresh_response)


def test_login_after_password_change_returns_latest_version_and_works(client, tenant):
    user = create_user(tenant=tenant, username="new-login")
    db.session.commit()
    set_user_password_and_invalidate_tokens(user, NEW_PASSWORD)
    db.session.commit()

    tokens = token_pair(client, user, password=NEW_PASSWORD)
    payload = decode_mobile_token(tokens["access_token"], TOKEN_TYPE_ACCESS)
    me_response = client.get("/api/v1/auth/me", headers=bearer_headers(tokens["access_token"]))

    assert payload["ver"] == user.token_version == 1
    assert me_response.status_code == 200


def test_token_version_increments_monotonically(tenant):
    user = create_user(tenant=tenant, username="mono-user")
    db.session.commit()

    set_user_password_and_invalidate_tokens(user, "one-pass")
    assert user.token_version == 1
    set_user_password_and_invalidate_tokens(user, "two-pass")
    assert user.token_version == 2


def test_legacy_access_token_without_version_returns_401_not_500(client, tenant):
    user = create_user(tenant=tenant, username="legacy-access")
    db.session.commit()
    token = legacy_mobile_token(user, TOKEN_TYPE_ACCESS)

    response = client.get("/api/v1/auth/me", headers=bearer_headers(token))

    assert_unauthorized_session_expired(response)


def test_legacy_refresh_token_without_version_returns_401_not_500(client, tenant):
    user = create_user(tenant=tenant, username="legacy-refresh")
    db.session.commit()
    token = legacy_mobile_token(user, TOKEN_TYPE_REFRESH)

    response = client.post("/api/v1/auth/refresh", json={"refresh_token": token})

    assert_unauthorized_session_expired(response)


def test_logout_still_uses_mobile_revoked_tokens(client, tenant):
    user = create_user(tenant=tenant, username="logout-user")
    db.session.commit()
    tokens = token_pair(client, user)

    response = client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": tokens["refresh_token"]},
        headers=bearer_headers(tokens["access_token"]),
    )

    assert response.status_code == 200
    assert MobileRevokedToken.query.count() == 2
    me_response = client.get("/api/v1/auth/me", headers=bearer_headers(tokens["access_token"]))
    assert me_response.status_code == 401


def test_self_service_password_change_bumps_version(client, tenant):
    user = create_user(tenant=tenant, username="self-change")
    db.session.commit()
    assert login_web(client, user.username).status_code == 302

    response = client.post(
        "/auth/ganti-password",
        data={
            "old_password": PASSWORD,
            "new_password": NEW_PASSWORD,
            "confirm_password": NEW_PASSWORD,
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    db.session.refresh(user)
    assert user.token_version == 1


def test_admin_reset_password_bumps_target_user(client, tenant):
    login_admin(client, tenant)
    user = create_user(tenant=tenant, username="reset-target")
    db.session.commit()

    response = client.post(f"/admin/student/reset-password/{user.id}", follow_redirects=False)

    assert response.status_code == 302
    db.session.refresh(user)
    assert user.token_version == 1


def test_generic_reset_password_bumps_target_user(client, tenant):
    login_admin(client, tenant)
    user = create_user(tenant=tenant, username="generic-target")
    db.session.commit()

    response = client.post(
        "/admin/users/reset-password-generic",
        data={"user_id": user.id, "new_password": NEW_PASSWORD},
        follow_redirects=False,
    )

    assert response.status_code == 302
    db.session.refresh(user)
    assert user.token_version == 1


def test_teacher_edit_with_password_bumps_teacher_user(client, tenant):
    login_admin(client, tenant)
    user = create_user(tenant=tenant, username="teacher-user", role=UserRole.GURU)
    teacher = Teacher(user_id=user.id, nip="T001", full_name="Teacher", phone="0801", specialty="Math")
    db.session.add(teacher)
    db.session.commit()

    response = client.post(
        f"/admin/sdm/guru/edit/{teacher.id}",
        data={
            "nip": "T001",
            "full_name": "Teacher Updated",
            "phone": "0801",
            "specialty": "Math",
            "password": NEW_PASSWORD,
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    db.session.refresh(user)
    assert user.token_version == 1


def test_teacher_edit_without_password_does_not_bump(client, tenant):
    login_admin(client, tenant)
    user = create_user(tenant=tenant, username="teacher-no-pass", role=UserRole.GURU)
    teacher = Teacher(user_id=user.id, nip="T002", full_name="Teacher", phone="0802", specialty="Math")
    db.session.add(teacher)
    db.session.commit()

    response = client.post(
        f"/admin/sdm/guru/edit/{teacher.id}",
        data={
            "nip": "T002",
            "full_name": "Teacher Updated",
            "phone": "0802",
            "specialty": "Math",
            "password": "",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    db.session.refresh(user)
    assert user.token_version == 0


def test_staff_edit_with_password_bumps_staff_user(client, tenant):
    login_admin(client, tenant)
    user = create_user(tenant=tenant, username="staff-user", role=UserRole.TU)
    staff = Staff(user_id=user.id, full_name="Staff", position="TU")
    db.session.add(staff)
    db.session.commit()

    response = client.post(
        f"/admin/sdm/staff/edit/{staff.id}",
        data={"full_name": "Staff Updated", "position": "TU", "password": NEW_PASSWORD},
        follow_redirects=False,
    )

    assert response.status_code == 302
    db.session.refresh(user)
    assert user.token_version == 1


def test_staff_edit_without_password_does_not_bump(client, tenant):
    login_admin(client, tenant)
    user = create_user(tenant=tenant, username="staff-no-pass", role=UserRole.TU)
    staff = Staff(user_id=user.id, full_name="Staff", position="TU")
    db.session.add(staff)
    db.session.commit()

    response = client.post(
        f"/admin/sdm/staff/edit/{staff.id}",
        data={"full_name": "Staff Updated", "position": "TU", "password": ""},
        follow_redirects=False,
    )

    assert response.status_code == 302
    db.session.refresh(user)
    assert user.token_version == 0


def test_change_login_phone_with_reset_password_bumps_target_user(client, tenant):
    login_admin(client, tenant)
    user = create_user(tenant=tenant, username="0811111111", role=UserRole.WALI_MURID)
    parent = Parent(user_id=user.id, full_name="Parent", phone="0811111111")
    db.session.add(parent)
    db.session.commit()

    response = client.post(
        "/admin/users/change-login-phone",
        data={
            "user_id": user.id,
            "new_phone": "0822222222",
            "reason": "test",
            "reset_password": "1",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    db.session.refresh(user)
    assert user.token_version == 1


def test_change_login_phone_without_reset_password_does_not_bump(client, tenant):
    login_admin(client, tenant)
    user = create_user(tenant=tenant, username="0833333333", role=UserRole.WALI_MURID)
    parent = Parent(user_id=user.id, full_name="Parent", phone="0833333333")
    db.session.add(parent)
    db.session.commit()

    response = client.post(
        "/admin/users/change-login-phone",
        data={
            "user_id": user.id,
            "new_phone": "0844444444",
            "reason": "test",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    db.session.refresh(user)
    assert user.token_version == 0


def test_normal_login_does_not_bump_token_version(client, tenant):
    user = create_user(tenant=tenant, username="normal-login")
    db.session.commit()

    assert login_mobile(client, user.username).status_code == 200
    db.session.refresh(user)
    assert user.token_version == 0


def test_role_change_does_not_bump_token_version(client, tenant):
    login_admin(client, tenant)
    user = create_user(tenant=tenant, username="role-target", role=UserRole.SISWA)
    db.session.commit()

    response = client.post(
        "/admin/users/roles",
        data={"user_id": user.id, "roles": ["TU"]},
        follow_redirects=False,
    )

    assert response.status_code == 302
    db.session.refresh(user)
    assert user.token_version == 0
