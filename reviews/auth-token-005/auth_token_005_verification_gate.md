# AUTH-TOKEN-005 Verification + Migration Gate

Tanggal: 2026-06-28
Mode: verification + migration gate only

Tidak dilakukan:

- perubahan kode aplikasi;
- perubahan model;
- migration baru;
- deploy;
- operasi database production.

## Decision

**APPROVED** untuk lanjut implementasi Phase 1 setelah approval implementasi.

Alasan:

- Mekanisme `users.token_version integer NOT NULL DEFAULT 0` sesuai finding dan keputusan manusia.
- Token issuance mobile terkonsentrasi di satu helper sehingga claim `ver` bisa ditambahkan tanpa menyentuh banyak caller.
- Access token validation terkonsentrasi di `mobile_auth_required()`.
- Refresh token validation terkonsentrasi di `auth_refresh()`.
- Semua flow password existing-user yang wajib bump teridentifikasi.
- Migration add-column integer default feasible dengan Alembic/PostgreSQL, dengan catatan production lock tetap perlu deployment gate.

## Approved Human Decisions

- Mekanisme: `users.token_version`.
- Tipe: integer `NOT NULL DEFAULT 0`.
- Tidak memakai timestamp-based invalidation.
- Tidak memakai server-side refresh session pada Phase 1.
- Strict cutover: token mobile lama tanpa claim `ver` ditolak setelah deploy.
- Forced re-login seluruh mobile user dapat diterima.
- Logout tetap memakai `MobileRevokedToken`.
- `AUTH-REFRESH-006` tetap backlog terpisah.

Event wajib bump:

- self-service password change;
- admin reset password;
- generic reset password;
- teacher edit dengan password baru;
- staff edit dengan password baru;
- change login phone jika sekaligus reset password.

Event tidak bump:

- create user baru;
- login normal;
- role change;
- tenant suspend;
- soft delete.

## 1. Password Change Inventory

### Existing User Password Changes - Must Bump

| Flow | File | Location | Current write | Required Phase 1 action |
|---|---|---:|---|---|
| Self-service password change | `app/routes/auth.py` | `change_password()` around line 148 | `current_user.password_hash = generate_password_hash(...)` | Replace with credential service that sets password and bumps `token_version`. |
| Teacher edit with password field | `app/routes/admin.py` | `edit_teacher()` around line 2702 | `teacher.user.password_hash = generate_password_hash(new_password)` | Use credential service only when `new_password` is present. |
| Staff edit with password field | `app/routes/admin.py` | `edit_staff()` around line 2837 | `staff.user.set_password(new_password)` | Use credential service only when `new_password` is present. |
| Student/user reset password | `app/routes/admin.py` | `reset_password(user_id)` around line 5876 | `user.password_hash = generate_password_hash(new_password)` | Use credential service and bump target user. |
| Generic reset password | `app/routes/admin.py` | `generic_reset_password()` around line 6420 | `user.set_password(new_password)` | Use credential service and bump target user. |
| Change login phone with reset password | `app/routes/admin.py` | `change_login_phone()` around line 6519 | `user.set_password(new_phone)` only if `reset_password` | Use credential service only when `reset_password` is true. |

Conclusion:

- These are the required Phase 1 mutation points.
- All are in `auth.py` and `admin.py`.
- No required existing-user password change flow was found in `teacher.py`.

### User Creation / Initial Password - Must Not Bump

| Flow | File | Location | Current write | Phase 1 action |
|---|---|---:|---|---|
| Create tenant admin user | `app/routes/admin.py` | around line 2130 | `new_user.set_password(password)` | Do not bump; new user starts `token_version=0`. |
| Create teacher | `app/routes/admin.py` | around line 2397 | `password_hash=generate_password_hash(password)` | Do not bump. |
| Import teacher | `app/routes/admin.py` | around line 2626 | `password_hash=generate_password_hash(password)` | Do not bump. |
| Create staff | `app/routes/admin.py` | around line 2747 | `user.set_password(password)` | Do not bump. |
| Create student/parent from admin add student | `app/routes/admin.py` | around lines 3139, 3168 | `set_password(...)` | Do not bump. |
| Import student/parent | `app/routes/admin.py` | around lines 3506, 3530 | `set_password(...)` | Do not bump. |
| PPDB accept majlis/student/parent | `app/routes/admin.py` | around lines 5729, 5763, 5791 | `password_hash=generate_password_hash(...)` | Do not bump. |
| Create boarding guardian | `app/routes/boarding.py` | around line 321 | `existing_user.set_password(password)` only in new-user branch | Do not bump because branch is `if not existing_user`. |
| Staff PPDB accept flows | `app/routes/staff.py` | around lines 1389, 1423, 1451 | `password_hash=generate_password_hash(...)` | Do not bump; these are user creation flows. |
| Admission service skeleton | `app/services/admission_service.py` | around line 19 | `user.set_password('rqdf1234')` | Do not bump; new user creation. |
| Seed script | `seed.py` | around line 19 | initial password hash | Do not bump; not production credential reset flow. |

Conclusion:

- Creation flows should rely on model/database default `token_version=0`.
- They should not call credential bump helper.

### Role / Tenant / Delete Events - Must Not Bump

Verified examples:

- `app/routes/admin.py` role management updates `user.role` and `UserRoleAssignment` around line 6355+.
- tenant suspension is handled by tenant lifecycle guards.
- soft-delete of user/profile exists in admin routes.

Decision:

- Do not bump for role change, tenant suspend, or soft delete in Phase 1.

## 2. Mobile Token Issuance Inventory

Issuance helper:

- `app/utils/mobile_api_auth.py`
  - `issue_mobile_token(user_id, tenant_id, token_type)`
  - `issue_mobile_token_pair(user)`

Call sites:

| Call site | File | Location | Notes |
|---|---|---:|---|
| Login token pair | `app/routes/api/auth.py` | around line 206 | Uses `issue_mobile_token_pair(user)`. |
| Refresh token pair | `app/routes/api/auth.py` | around line 244 | Uses `issue_mobile_token_pair(user)`. |

Verification result:

- All mobile auth token issuance flows go through `issue_mobile_token_pair(user)`.
- Phase 1 should change helper signature so `issue_mobile_token()` receives enough context to include `ver=user.token_version`.
- Recommended internal API:

```text
issue_mobile_token(user, token_type)
issue_mobile_token_pair(user)
```

instead of:

```text
issue_mobile_token(user_id, tenant_id, token_type)
```

This avoids caller accidentally forgetting to pass `token_version`.

## 3. Access Token Validation Inventory

Access token validation path:

- `app/routes/api/common.py`
  - `mobile_auth_required()`
  - calls `decode_mobile_token(access_token, TOKEN_TYPE_ACCESS)`
  - loads `User`
  - checks tenant claim, tenant lifecycle, role, capability.

Protected mobile access:

- All protected API endpoints using `@mobile_auth_required()` pass through this path.
- `/api/v1/auth/me`, `/api/v1/auth/logout`, `/api/v1/auth/push-token`, teacher, boarding, majlis, parent, and other protected mobile routes use this decorator pattern.

Required Phase 1 validation:

```text
payload.ver exists
payload.ver == user.token_version
```

Recommended placement:

- after user is loaded;
- before tenant lifecycle/role/capability checks or immediately after tenant claim check.

Recommended error:

```text
HTTP 401
code = unauthorized
message = Sesi sudah tidak berlaku. Silakan login ulang.
```

Strict cutover:

- If `ver` missing, return the same `401 unauthorized`.
- Do not let missing `ver` cause `KeyError` or `500`.

## 4. Refresh Token Validation Inventory

Refresh token path:

- `app/routes/api/auth.py`
  - `auth_refresh()`
  - calls `decode_mobile_token(refresh_token, TOKEN_TYPE_REFRESH)`
  - loads `User`
  - checks tenant claim and tenant lifecycle
  - issues token pair
  - revokes old refresh token

Required Phase 1 validation:

```text
refresh_payload.ver exists
refresh_payload.ver == user.token_version
```

Recommended placement:

- after user load and tenant claim check;
- before `issue_mobile_token_pair(user)`;
- before revoking old refresh token is not security-critical, but validation should happen before issuing any new token.

Strict cutover:

- Refresh token without `ver` must return `401 unauthorized`, not `500`.

## 5. Migration Review

Proposed migration:

```sql
ALTER TABLE users
ADD COLUMN token_version INTEGER NOT NULL DEFAULT 0;
```

Recommended Alembic expression:

```python
op.add_column(
    "users",
    sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
)
```

Recommended model field:

```python
token_version = db.Column(db.Integer, nullable=False, default=0, server_default="0")
```

Whether to keep `server_default`:

- Keep server default `0` because human decision explicitly says `NOT NULL DEFAULT 0`.
- This also protects direct inserts/scripts that do not set `token_version`.

PostgreSQL compatibility:

- `INTEGER NOT NULL DEFAULT 0` is valid PostgreSQL DDL.
- PostgreSQL 11+ optimizes adding a column with constant default and generally avoids full table rewrite.
- Older PostgreSQL versions may rewrite the table.
- Any `ALTER TABLE users ADD COLUMN` still requires an `ACCESS EXCLUSIVE` lock during DDL, even if brief.

Backfill behavior:

- Existing rows see `0` as default.
- No separate backfill script is required for constant default.
- Application should still defensively handle `None` in helper during tests/edge cases, but DB contract is non-null.

Rollback behavior:

```python
op.drop_column("users", "token_version")
```

Rollback caution:

- Dropping the column after issuing versioned tokens makes existing tokens undecodable only if code still expects model field.
- Operational rollback should be code-first: rollback app code or keep code tolerant before DB downgrade.
- Production downgrade/drop column remains destructive metadata change and requires human approval.

Production locking risk:

- Low to medium depending `users` row count and PostgreSQL version.
- Deployment gate should verify DB version and run during a maintenance-safe window.
- No long-running backfill expected.

Decision:

- Migration plan is acceptable for Phase 1.

## 6. Strict Cutover Review

Required behavior:

- Token missing `ver` returns `401 unauthorized`.
- No `KeyError`.
- No `500`.
- No raw decode/signature failure caused by missing claim.

Recommended helper:

```text
validate_mobile_token_version(payload, user)
```

Semantics:

```text
if payload.get("ver") is None:
    invalid
if int(payload.get("ver")) != int(user.token_version or 0):
    invalid
else:
    valid
```

Important:

- Use `payload.get("ver")`, not `payload["ver"]`.
- Treat non-integer `ver` as invalid.
- Return controlled `ValueError` or boolean decision that routes convert to `401`.

Decision:

- Strict cutover is safe if implemented via helper with controlled error handling.

## 7. Helper / Service Design Review

Compared options:

### Option A - `bump_user_token_version(user)`

Pros:

- Small.
- Easy to call from password reset sites.
- Low overhead.

Cons:

- Does not centralize password setting.
- Developers can still call `user.set_password()` or assign `password_hash` without bump.
- Does not make credential mutation intent explicit.

### Option B - `credential_security_service.py`

Suggested API:

```text
set_user_password_and_invalidate_tokens(user, raw_password, *, must_change_password=None)
bump_user_token_version(user)
validate_mobile_token_version(payload, user)
```

Pros:

- Centralizes security-sensitive credential mutation.
- Reduces chance of missed bump in future.
- Keeps route code focused on HTTP/form flow.
- Gives tests a stable service boundary.
- Can later add audit logging without touching all routes again.

Cons:

- Slightly more code than a single helper.

Recommendation:

- Use **Option B: `credential_security_service.py`**.

Reason:

- Password writes are currently scattered and use both `set_password()` and direct `password_hash = generate_password_hash(...)`.
- A named service makes future review easier and aligns with repository guidance that business/security rules should not live ad hoc in routes.

## 8. Testing Plan Review

Required new test file recommendation:

- `tests/test_mobile_token_version_invalidation.py`

Recommended integration coverage:

| Case | Expected |
|---|---|
| login issues token with `ver=0` | decoded payload includes `ver == user.token_version`. |
| old access token after self-service password change | `/api/v1/auth/me` returns `401 unauthorized`. |
| old refresh token after self-service password change | `/api/v1/auth/refresh` returns `401 unauthorized`. |
| login after password change | new token has latest `ver` and works. |
| `token_version` increments monotonically | `0 -> 1 -> 2` across repeated credential changes. |
| legacy access token without `ver` | returns `401 unauthorized`, not `500`. |
| legacy refresh token without `ver` | returns `401 unauthorized`, not `500`. |
| logout still uses `MobileRevokedToken` | revoked current token returns `401`. |

Required flow-specific tests:

| Flow | Required assertion |
|---|---|
| self-service password change | bumps version and old mobile tokens denied. |
| `admin.reset_password(user_id)` | bumps target user version. |
| `admin.generic_reset_password()` | bumps target user version. |
| teacher edit with password | bumps teacher user version. |
| teacher edit without password | does not bump. |
| staff edit with password | bumps staff user version. |
| staff edit without password | does not bump. |
| change login phone with reset password | bumps target user version. |
| change login phone without reset password | does not bump. |
| normal login | does not bump. |
| role change | does not bump. |

Regression tests to keep running:

- `tests/test_mobile_auth_tenant_status.py`
- `tests/test_mobile_package_capabilities.py`
- `tests/test_auth_rate_limit_integration.py`
- `tests/test_auth_rate_limit_service.py`

Decision:

- Testing plan is sufficient if all required flows above are implemented.

## 9. Risks and Mitigations

### Forced mobile re-login

Risk:

- Strict cutover rejects all existing mobile tokens without `ver`.

Mitigation:

- Human decision accepts forced re-login.
- Mobile clients receive controlled `401 unauthorized`.

### Missed password mutation path

Risk:

- Any remaining direct password hash write for existing user would bypass token invalidation.

Mitigation:

- Replace all existing-user password writes identified in this document.
- Keep user creation flows unchanged.
- Add grep-based review checklist for `set_password(` and `password_hash =`.

### Migration lock

Risk:

- `ALTER TABLE users ADD COLUMN` takes table lock.

Mitigation:

- Verify PostgreSQL version.
- Run migration during approved window.
- No data backfill loop.

### Refresh rotation race remains

Risk:

- Token version does not solve concurrent refresh reuse.

Mitigation:

- Tracked separately as `AUTH-REFRESH-006`.

## 10. APPROVED Implementation Plan - Phase 1

### Step 1 - Add Migration

Create Alembic migration:

```python
op.add_column(
    "users",
    sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
)
```

Downgrade:

```python
op.drop_column("users", "token_version")
```

Do not run migration without human approval.

### Step 2 - Add Model Field

File:

- `app/models.py`

Add to `User`:

```python
token_version = db.Column(db.Integer, nullable=False, default=0, server_default="0")
```

### Step 3 - Add Credential Security Service

Create:

- `app/services/credential_security_service.py`

Responsibilities:

- set password for existing user;
- bump `token_version`;
- validate token version from payload;
- keep logic reusable for route and API auth code.

Suggested functions:

```text
bump_user_token_version(user)
set_user_password_and_invalidate_tokens(user, raw_password, *, must_change_password=None)
validate_mobile_token_version(payload, user)
```

### Step 4 - Update Mobile Token Issuance

File:

- `app/utils/mobile_api_auth.py`

Change token payload to include:

```text
ver = user.token_version
```

Recommended:

- refactor `issue_mobile_token()` to accept `user`, not `user_id` and `tenant_id` separately.
- keep `issue_mobile_token_pair(user)` as public helper.

### Step 5 - Update Access Token Validation

File:

- `app/routes/api/common.py`

In `mobile_auth_required()`:

- after loading user and tenant claim check;
- call `validate_mobile_token_version(payload, user)`;
- on failure return `api_error("unauthorized", "Sesi sudah tidak berlaku. Silakan login ulang.", 401)`.

### Step 6 - Update Refresh Token Validation

File:

- `app/routes/api/auth.py`

In `auth_refresh()`:

- after loading user and tenant claim check;
- validate `refresh_payload.ver == user.token_version`;
- on failure return `401 unauthorized`;
- validate before issuing token pair.

### Step 7 - Replace Existing-User Password Writes

Use `set_user_password_and_invalidate_tokens()` in:

- `app/routes/auth.py::change_password`
- `app/routes/admin.py::edit_teacher` when `new_password`
- `app/routes/admin.py::edit_staff` when `new_password`
- `app/routes/admin.py::reset_password`
- `app/routes/admin.py::generic_reset_password`
- `app/routes/admin.py::change_login_phone` when `reset_password`

Do not use it for user creation flows.

### Step 8 - Add Tests

Add:

- `tests/test_mobile_token_version_invalidation.py`

Cover:

- token claim `ver`;
- old access token denied after bump;
- old refresh token denied after bump;
- legacy token without `ver` denied cleanly;
- login after bump succeeds with latest version;
- monotonic increment;
- required route flows bump or do not bump according to decision.

### Step 9 - Verification Commands

Run at minimum:

```powershell
$env:PYTHONPATH='.'; .\.venv\Scripts\pytest.exe tests/test_mobile_token_version_invalidation.py -q
$env:PYTHONPATH='.'; .\.venv\Scripts\pytest.exe tests/test_mobile_auth_tenant_status.py -q
$env:PYTHONPATH='.'; .\.venv\Scripts\pytest.exe tests/test_mobile_package_capabilities.py -q
$env:PYTHONPATH='.'; .\.venv\Scripts\pytest.exe tests/test_auth_rate_limit_integration.py tests/test_auth_rate_limit_service.py -q
```

Run full suite and track known finance failure separately if it remains.

### Step 10 - Review Gate Before Deploy

Before deploy:

- migration review;
- security review;
- code review;
- testing evidence;
- explicit human approval to run migration;
- explicit human approval to deploy strict cutover.

