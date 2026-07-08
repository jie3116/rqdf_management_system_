from datetime import timedelta

import pytest
from itsdangerous import URLSafeTimedSerializer

from app import create_app
from app.extensions import db
from app.models import MobileRefreshToken, MobileRevokedToken, Tenant, TenantStatus, User, UserRole
from app.services.credential_security_service import set_user_password_and_invalidate_tokens
from app.utils.mobile_api_auth import (
    TOKEN_TYPE_ACCESS,
    TOKEN_TYPE_REFRESH,
    decode_mobile_token,
    mobile_token_hash,
)
from app.utils.timezone import utc_now_naive


PASSWORD = "ValidPass123!"
NEW_PASSWORD = "NextPass123!"
SESSION_EXPIRED = "Sesi sudah tidak berlaku. Silakan login ulang."


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
    response = client.post(
        "/api/v1/auth/login",
        json={"identifier": username, "password": password},
    )
    assert response.status_code == 200
    return response.get_json()["data"]


def bearer_headers(token):
    return {"Authorization": f"Bearer {token}"}


def refresh(client, refresh_token):
    return client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})


def logout(client, access_token, refresh_token=None):
    payload = {}
    if refresh_token is not None:
        payload["refresh_token"] = refresh_token
    return client.post(
        "/api/v1/auth/logout",
        json=payload,
        headers=bearer_headers(access_token),
    )


def assert_session_expired(response):
    payload = response.get_json()
    assert response.status_code == 401
    assert payload["success"] is False
    assert payload["code"] == "unauthorized"
    assert payload["message"] == SESSION_EXPIRED


def serializer():
    return URLSafeTimedSerializer(
        secret_key=TestConfig.SECRET_KEY,
        salt="mobile-api-auth-v1",
    )


def custom_mobile_token(user, token_type, *, jti, ver=0, tid=None, uid=None):
    payload = {
        "uid": user.id if uid is None else uid,
        "tid": user.tenant_id if tid is None else tid,
        "typ": token_type,
        "jti": jti,
    }
    if ver is not None:
        payload["ver"] = ver
    return serializer().dumps(payload)


def refresh_row_by_token(refresh_token):
    payload = decode_mobile_token(refresh_token, TOKEN_TYPE_REFRESH)
    return MobileRefreshToken.query.filter_by(jti=payload["jti"]).one()


def test_mobile_login_creates_active_refresh_token_row_and_stores_hash(client, tenant):
    user = create_user(tenant=tenant, username="login-row")
    db.session.commit()

    tokens = login_mobile(client, user.username)
    payload = decode_mobile_token(tokens["refresh_token"], TOKEN_TYPE_REFRESH)
    row = MobileRefreshToken.query.filter_by(jti=payload["jti"]).one()

    assert row.status == MobileRefreshToken.STATUS_ACTIVE
    assert row.user_id == user.id
    assert row.tenant_id == tenant.id
    assert row.family_id
    assert row.token_hash == mobile_token_hash(tokens["refresh_token"])
    assert row.token_hash != tokens["refresh_token"]


def test_refresh_consumes_old_row_and_creates_new_active_row(client, tenant):
    user = create_user(tenant=tenant, username="refresh-row")
    db.session.commit()
    tokens = login_mobile(client, user.username)
    old_payload = decode_mobile_token(tokens["refresh_token"], TOKEN_TYPE_REFRESH)
    old_row = MobileRefreshToken.query.filter_by(jti=old_payload["jti"]).one()
    family_id = old_row.family_id

    response = refresh(client, tokens["refresh_token"])

    assert response.status_code == 200
    new_token = response.get_json()["data"]["refresh_token"]
    new_payload = decode_mobile_token(new_token, TOKEN_TYPE_REFRESH)
    db.session.refresh(old_row)
    new_row = MobileRefreshToken.query.filter_by(jti=new_payload["jti"]).one()
    assert old_row.status == MobileRefreshToken.STATUS_CONSUMED
    assert old_row.consumed_at is not None
    assert old_row.replaced_by_jti == new_payload["jti"]
    assert new_row.status == MobileRefreshToken.STATUS_ACTIVE
    assert new_row.family_id == family_id


def test_reused_old_refresh_token_returns_401_and_revokes_family(client, tenant):
    user = create_user(tenant=tenant, username="reuse-row")
    db.session.commit()
    tokens = login_mobile(client, user.username)
    old_row = refresh_row_by_token(tokens["refresh_token"])

    first_response = refresh(client, tokens["refresh_token"])
    assert first_response.status_code == 200
    new_token = first_response.get_json()["data"]["refresh_token"]
    new_row = refresh_row_by_token(new_token)

    second_response = refresh(client, tokens["refresh_token"])

    assert_session_expired(second_response)
    db.session.refresh(old_row)
    db.session.refresh(new_row)
    assert old_row.status == MobileRefreshToken.STATUS_REUSED
    assert old_row.reuse_detected_at is not None
    assert new_row.status == MobileRefreshToken.STATUS_REVOKED
    assert new_row.revoked_at is not None


def test_two_refresh_attempts_with_same_token_cannot_both_succeed(client, tenant):
    user = create_user(tenant=tenant, username="double-refresh")
    db.session.commit()
    tokens = login_mobile(client, user.username)

    first_response = refresh(client, tokens["refresh_token"])
    second_response = refresh(client, tokens["refresh_token"])

    assert first_response.status_code == 200
    assert second_response.status_code == 401


def test_refresh_token_without_server_side_row_returns_401(client, tenant):
    user = create_user(tenant=tenant, username="cutover")
    db.session.commit()
    token = custom_mobile_token(user, TOKEN_TYPE_REFRESH, jti="missing-row", ver=user.token_version)

    response = refresh(client, token)

    assert_session_expired(response)


def test_logout_with_refresh_token_revokes_family(client, tenant):
    user = create_user(tenant=tenant, username="logout-family")
    db.session.commit()
    tokens = login_mobile(client, user.username)
    row = refresh_row_by_token(tokens["refresh_token"])

    response = logout(client, tokens["access_token"], tokens["refresh_token"])

    assert response.status_code == 200
    db.session.refresh(row)
    assert row.status == MobileRefreshToken.STATUS_REVOKED
    assert row.revoked_at is not None
    assert MobileRevokedToken.query.count() == 2
    assert refresh(client, tokens["refresh_token"]).status_code == 401


def test_logout_without_refresh_token_preserves_access_only_behavior(client, tenant):
    user = create_user(tenant=tenant, username="logout-access-only")
    db.session.commit()
    tokens = login_mobile(client, user.username)
    row = refresh_row_by_token(tokens["refresh_token"])

    response = logout(client, tokens["access_token"])

    assert response.status_code == 200
    db.session.refresh(row)
    assert row.status == MobileRefreshToken.STATUS_ACTIVE
    assert MobileRevokedToken.query.count() == 1
    access_response = client.get("/api/v1/auth/me", headers=bearer_headers(tokens["access_token"]))
    assert access_response.status_code == 401
    assert refresh(client, tokens["refresh_token"]).status_code == 200


def test_password_change_token_version_bump_rejects_old_refresh_token(client, tenant):
    user = create_user(tenant=tenant, username="password-bump")
    db.session.commit()
    tokens = login_mobile(client, user.username)

    set_user_password_and_invalidate_tokens(user, NEW_PASSWORD)
    db.session.commit()

    response = refresh(client, tokens["refresh_token"])

    assert_session_expired(response)


@pytest.mark.parametrize(
    ("ver", "jti"),
    [
        (None, "missing-ver"),
        (-1, "stale-ver"),
        ("not-int", "non-int-ver"),
    ],
)
def test_refresh_token_version_claim_invalid_returns_401(client, tenant, ver, jti):
    user = create_user(tenant=tenant, username=f"user-{jti}")
    db.session.commit()
    token = custom_mobile_token(user, TOKEN_TYPE_REFRESH, jti=jti, ver=ver)

    response = refresh(client, token)

    assert_session_expired(response)


def test_tenant_inactive_rejected_as_before(client, tenant):
    user = create_user(tenant=tenant, username="tenant-inactive")
    db.session.commit()
    tokens = login_mobile(client, user.username)

    tenant.status = TenantStatus.SUSPENDED
    db.session.commit()

    response = refresh(client, tokens["refresh_token"])
    payload = response.get_json()
    assert response.status_code == 403
    assert payload["code"] == "tenant_inactive"


def test_malformed_refresh_token_rejected(client):
    response = refresh(client, "not-a-token")

    payload = response.get_json()
    assert response.status_code == 401
    assert payload["code"] == "unauthorized"


def test_access_token_sent_to_refresh_endpoint_rejected(client, tenant):
    user = create_user(tenant=tenant, username="wrong-type")
    db.session.commit()
    tokens = login_mobile(client, user.username)

    response = refresh(client, tokens["access_token"])

    payload = response.get_json()
    assert response.status_code == 401
    assert payload["code"] == "unauthorized"


def test_missing_user_rejected(client, tenant):
    user = create_user(tenant=tenant, username="missing-user-source")
    db.session.commit()
    token = custom_mobile_token(user, TOKEN_TYPE_REFRESH, jti="missing-user", uid=999999)

    response = refresh(client, token)

    payload = response.get_json()
    assert response.status_code == 401
    assert payload["code"] == "unauthorized"


def test_tenant_mismatch_rejected(client, tenant):
    other_tenant = Tenant(
        name="Other",
        slug="other",
        code="OTHER",
        status=TenantStatus.ACTIVE,
        is_default=False,
    )
    db.session.add(other_tenant)
    db.session.flush()
    user = create_user(tenant=tenant, username="tenant-mismatch")
    db.session.commit()
    token = custom_mobile_token(user, TOKEN_TYPE_REFRESH, jti="tenant-mismatch", tid=other_tenant.id)

    response = refresh(client, token)

    payload = response.get_json()
    assert response.status_code == 401
    assert payload["code"] == "unauthorized"


def test_expired_server_side_row_rejected(client, tenant):
    user = create_user(tenant=tenant, username="expired-row")
    db.session.commit()
    tokens = login_mobile(client, user.username)
    row = refresh_row_by_token(tokens["refresh_token"])
    row.expires_at = utc_now_naive() - timedelta(seconds=1)
    db.session.commit()

    response = refresh(client, tokens["refresh_token"])

    assert_session_expired(response)
    db.session.refresh(row)
    assert row.status == MobileRefreshToken.STATUS_REUSED


def test_two_separate_login_families_are_isolated(client, tenant):
    user = create_user(tenant=tenant, username="family-isolated")
    db.session.commit()
    first_tokens = login_mobile(client, user.username)
    second_tokens = login_mobile(client, user.username)
    first_row = refresh_row_by_token(first_tokens["refresh_token"])
    second_row = refresh_row_by_token(second_tokens["refresh_token"])
    assert first_row.family_id != second_row.family_id

    assert refresh(client, first_tokens["refresh_token"]).status_code == 200
    reuse_response = refresh(client, first_tokens["refresh_token"])

    assert_session_expired(reuse_response)
    db.session.refresh(second_row)
    assert second_row.status == MobileRefreshToken.STATUS_ACTIVE
