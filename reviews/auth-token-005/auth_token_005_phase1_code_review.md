# AUTH-TOKEN-005 Phase 1 Code Review

Review date: 2026-06-28

## Scope

This review covers AUTH-TOKEN-005 Phase 1 implementation:

- `token_version` model and migration;
- mobile token issuance claim `ver`;
- access token validation;
- refresh token validation;
- credential security service;
- replacement of existing-user password mutation flows;
- tests.

This review does not include:

- running production migration;
- deploy;
- database production operation;
- `AUTH-REFRESH-006` refresh rotation race remediation.

## Changed Files

- `app/models.py`
- `app/services/credential_security_service.py`
- `app/utils/mobile_api_auth.py`
- `app/routes/api/common.py`
- `app/routes/api/auth.py`
- `app/routes/auth.py`
- `app/routes/admin.py`
- `migrations/versions/af56gh78ij90_add_user_token_version.py`
- `tests/test_mobile_token_version_invalidation.py`

## Decision

**APPROVED FOR HUMAN CODE REVIEW**

**NOT APPROVED FOR MIGRATION OR DEPLOY YET**

## Checklist Results

### Migration

Status: **PASS**

- Migration adds `users.token_version` as `sa.Integer()`.
- Column is `nullable=False`.
- Column uses `server_default="0"`.
- Downgrade drops `token_version`.
- No unrelated schema changes were introduced.
- Migration was not run as part of this review.

### User Model

Status: **PASS**

- `User.token_version` exists in `app/models.py`.
- Field definition:

```python
token_version = db.Column(db.Integer, nullable=False, default=0, server_default="0")
```

- No unrelated model changes were introduced.

### Credential Security Service

Status: **PASS**

- `bump_user_token_version(user)` increments monotonically and treats `None` as `0`.
- `set_user_password_and_invalidate_tokens(user, raw_password, *, must_change_password=None)` sets password once and bumps `token_version` once.
- `must_change_password` is changed only when the argument is not `None`.
- `validate_mobile_token_version(payload, user)` uses `payload.get("ver")`.
- Missing `ver` is rejected.
- Non-integer `ver` is rejected.
- Valid integer `ver` is compared against `int(user.token_version or 0)`.
- Invalid token version handling cannot raise `KeyError` and is converted by callers into controlled `401 unauthorized`.

### Mobile Token Issuance

Status: **PASS**

- Issued access and refresh tokens include:

```text
ver = user.token_version
```

- `issue_mobile_token_pair(user)` remains the public helper.
- Login and refresh call sites still use `issue_mobile_token_pair(user)`.
- `issue_mobile_token()` now accepts the user object, so callers cannot accidentally omit `token_version`.

### Access Token Validation

Status: **PASS**

- `mobile_auth_required()` validates token version after loading user and checking tenant claim.
- Missing/stale/non-integer `ver` returns:

```python
api_error("unauthorized", "Sesi sudah tidak berlaku. Silakan login ulang.", 401)
```

- Response is controlled `401`, not `500`.

### Refresh Token Validation

Status: **PASS**

- `auth_refresh()` validates refresh token version after user load and tenant claim check.
- Validation happens before issuing a new token pair.
- Missing/stale/non-integer `ver` returns the same controlled `401 unauthorized`.

### Password Mutation Flows

Status: **PASS**

Required existing-user password mutation flows use `set_user_password_and_invalidate_tokens()`:

- `app/routes/auth.py::change_password`
- `app/routes/admin.py::edit_teacher` only when `new_password` is present
- `app/routes/admin.py::edit_staff` only when `new_password` is present
- `app/routes/admin.py::reset_password`
- `app/routes/admin.py::generic_reset_password`
- `app/routes/admin.py::change_login_phone` only when `reset_password` is true

User creation flows do not use this service.

### Test Coverage

Status: **PASS**

Tests cover:

- login token contains `ver`;
- old access token rejected after password change;
- old refresh token rejected after password change;
- login after password change works with latest `ver`;
- `token_version` increments monotonically;
- legacy access token without `ver` returns `401`, not `500`;
- legacy refresh token without `ver` returns `401`, not `500`;
- logout revocation behavior still works;
- required password mutation flows bump or do not bump according to the gate.

## Password Mutation Scan Evidence

- No route-level existing-user password mutation remains outside `credential_security_service`.
- Remaining app occurrences are either model/helper/service definitions or initial user creation flows.
- Tests and seed occurrences are test/seed initialization only.
- No suspicious occurrence was found.

## Test Evidence

Command:

```powershell
$env:PYTHONPATH='.'; .\.venv\Scripts\pytest.exe tests/test_mobile_token_version_invalidation.py -q
```

Result:

```text
18 passed
```

Command:

```powershell
$env:PYTHONPATH='.'; .\.venv\Scripts\pytest.exe tests/test_mobile_auth_tenant_status.py -q
```

Result:

```text
11 passed
```

Command:

```powershell
$env:PYTHONPATH='.'; .\.venv\Scripts\pytest.exe tests/test_mobile_package_capabilities.py -q
```

Result:

```text
15 passed
```

Command:

```powershell
$env:PYTHONPATH='.'; .\.venv\Scripts\pytest.exe tests/test_auth_rate_limit_integration.py tests/test_auth_rate_limit_service.py -q
```

Result:

```text
11 passed
```

## Risk Notes

- Strict cutover will force mobile re-login because old tokens without `ver` are rejected.
- Migration still requires human approval due to table lock.
- `AUTH-REFRESH-006` remains separate and is not solved by `token_version`.
- Production deployment must have a separate migration/deploy gate.

## Final Recommendation

AUTH-TOKEN-005 Phase 1 implementation is ready for human code review.

After human review, the next step is a dedicated migration/deploy gate.

Do not run migration until explicit human approval.

