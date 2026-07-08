# AUTH-REFRESH-006 Verification + Migration Gate

Tanggal: 2026-07-08

Status: `APPROVED FOR PHASE 1 IMPLEMENTATION AFTER HUMAN APPROVAL`

Gate statement:

- Migration design accepted.
- Implementation belum boleh dilakukan sebelum approval manusia eksplisit.
- Deploy belum approved.
- Production migration belum approved.

## 1. Scope Phase 1

Phase 1 mencakup:

- server-side refresh token rotation;
- model/tabel `MobileRefreshToken`;
- migration `mobile_refresh_tokens`;
- strict one-time refresh token;
- token family;
- reuse detection;
- family revoke on reuse;
- strict cutover for legacy refresh token without server-side row;
- tests.

Out of scope:

- web session;
- tenant/package/rate-limit changes;
- device management UI;
- logout all devices UI;
- background scheduler;
- `TENANT-DATA-006`;
- deploy.

## 2. Approved Data Model

Model:

- `MobileRefreshToken`

Table:

- `mobile_refresh_tokens`

Columns:

| Column | Definition |
| --- | --- |
| `id` | integer primary key |
| `user_id` | integer not null |
| `tenant_id` | integer nullable only if existing `User.tenant_id` can be null; otherwise not null |
| `family_id` | string(64) not null |
| `jti` | string(64) not null |
| `token_hash` | string(64) not null |
| `status` | string(20) not null |
| `issued_at` | datetime not null |
| `expires_at` | datetime not null |
| `consumed_at` | datetime nullable |
| `revoked_at` | datetime nullable |
| `replaced_by_jti` | string(64) nullable |
| `reuse_detected_at` | datetime nullable |
| `created_at` | datetime not null |
| `updated_at` | datetime not null |

Constraints/indexes:

- unique `jti`
- unique `token_hash`
- index `user_id`
- index `tenant_id`
- index `family_id`
- index `status`
- index `expires_at`
- composite index `(user_id, tenant_id, status)`

Status representation:

- Use string constants, not DB enum, for Phase 1.

Status values:

- `ACTIVE`
- `CONSUMED`
- `REVOKED`
- `REUSED`

Expired token:

- Expiry is derived from `expires_at`.
- No `EXPIRED` status is required.

## 3. Token Storage Security

Requirements:

- Never store raw refresh token.
- Store SHA-256 or existing token hash convention.
- `token_hash` must be deterministic for lookup.
- `token_hash` must not expose raw token.
- Logs must not print raw refresh token.

Implementation note:

- Existing `MobileRevokedToken` uses SHA-256 of the raw token string. AUTH-REFRESH-006 may reuse that convention unless the implementation gate explicitly chooses HMAC hashing.
- If HMAC is selected, lookup must remain deterministic and secret rotation impact must be documented.

## 4. Refresh Token Claims

Refresh token must continue to include:

- `uid`
- `tid`
- `typ`
- `jti`
- `ver`

Requirements:

- `jti` must match server-side row.
- `token_hash` must match server-side row.
- `ver` must still be validated against `users.token_version`.
- `typ` must be `refresh`.

## 5. Flow Requirements

### Mobile Login

Requirements:

- issue access token;
- issue refresh token with `jti`;
- create new `family_id`;
- insert `ACTIVE` `MobileRefreshToken` row;
- commit login transaction;
- return token pair.

### Mobile Refresh

Requirements:

- decode refresh token;
- validate `uid`/`tid`/`typ`/`ver`;
- load user;
- validate tenant claim;
- validate tenant lifecycle;
- find server-side row by `jti` and `token_hash`;
- atomically consume only if `ACTIVE` and not expired;
- issue replacement refresh token;
- insert new `ACTIVE` row with same `family_id`;
- set old row `CONSUMED`, `consumed_at`, `replaced_by_jti`;
- commit;
- return token pair only after successful consume/insert.

### Reuse

If token row is missing, non-`ACTIVE`, expired, or hash mismatch:

- return controlled `401`;
- if row exists and belongs to a family, mark `reuse_detected_at` if applicable;
- revoke `ACTIVE` tokens in same family.

### Logout

Requirements:

- keep existing access token revocation behavior;
- if refresh token is supplied, revoke refresh row or family according to implementation decision;
- recommended Phase 1: revoke the refresh token family for that supplied refresh token;
- if no refresh token supplied, keep existing behavior and only revoke current access token.

### Password Change

Requirements:

- `AUTH-TOKEN-005` token_version remains primary invalidation mechanism;
- no required family revoke during password change in Phase 1;
- stale `ver` refresh token returns controlled `401`.

### Tenant Inactive

Requirements:

- keep existing tenant lifecycle behavior;
- tenant inactive refresh remains rejected according to existing API contract.

## 6. Atomicity / Transaction Requirements

Requirements:

- Two parallel refresh requests using same token must not both return `200`.
- Consume must be atomic.
- Prefer row-level lock with `SELECT FOR UPDATE` or conditional `UPDATE`.
- Do not issue/return token pair if old refresh token was not consumed.
- Old token consume and new token insert must be one transaction.
- Commit failure must not return token pair.
- Duplicate `jti`/`token_hash` constraint errors must be handled as controlled failure where applicable.

Recommended implementation shape:

- Validate token cryptographically first.
- Resolve server-side row by `jti` and `token_hash`.
- Lock row or perform conditional update where `status = ACTIVE` and `expires_at > now`.
- Continue only if exactly one row was consumed.
- Create replacement token row in the same transaction.
- Commit before returning token pair.

## 7. Strict Cutover

Strict cutover is approved.

Behavior:

- Existing refresh tokens without DB row are rejected controlled `401`.
- Mobile users may need login again.
- No backfill.
- This is accepted by human decision.

Response requirements:

- Missing server-side row must not produce `500`.
- Missing server-side row must return controlled `401 unauthorized`.
- Use a generic session-expired message unless implementation gate approves a different response contract.

## 8. Retention / Cleanup Policy

Requirements:

- Raw tokens are never stored.
- Refresh token rows are retained only for security/audit for limited time.
- Recommended initial retention: 30-90 days after `expires_at`.
- Expired rows with status `CONSUMED`, `REVOKED`, or `REUSED` may be cleaned periodically.
- Expired `ACTIVE` rows may be cleaned or marked revoked after retention.
- No background scheduler required in Phase 1 unless already exists.
- Create backlog item or manual script for cleanup if not implemented now.

## 9. Migration Plan

Migration should:

- create `mobile_refresh_tokens`;
- add all approved columns;
- add unique constraints and indexes;
- use string status column, not DB enum;
- add FK to `users` if consistent with existing model/migration pattern;
- add FK to `tenants` if `tenant_id` not nullable and consistent with existing pattern;
- downgrade drops table.

Do not run migration during implementation review.

Migration approval boundaries:

- Migration design is accepted.
- Creating the migration file during implementation still requires human implementation approval.
- Running production migration requires a separate deploy/migration gate.

## 10. Required Tests

Implementation must include tests for:

- mobile login creates `ACTIVE` refresh token row;
- row stores hash, not raw refresh token;
- refresh consumes old row and creates new `ACTIVE` row;
- old row becomes `CONSUMED`;
- `replaced_by_jti` points to new refresh `jti`;
- reused old token returns controlled `401`;
- reuse revokes active tokens in same family;
- two refresh attempts with same token cannot both succeed;
- token without server-side row returns controlled `401`;
- logout with refresh token revokes family or token according to final implementation;
- logout without refresh token preserves existing access-only behavior;
- password change/token_version bump rejects old refresh token;
- missing `ver` rejected;
- stale `ver` rejected;
- non-integer `ver` rejected;
- tenant inactive rejected as before;
- malformed token rejected;
- access token sent to refresh endpoint rejected;
- missing user rejected;
- tenant mismatch rejected;
- expired server-side row rejected;
- two separate login families are isolated.

## 11. Regression Tests

Run these relevant regression suites after implementation:

```powershell
$env:PYTHONPATH='.'; .\.venv\Scripts\pytest.exe tests/test_mobile_token_version_invalidation.py -q
$env:PYTHONPATH='.'; .\.venv\Scripts\pytest.exe tests/test_mobile_auth_tenant_status.py -q
$env:PYTHONPATH='.'; .\.venv\Scripts\pytest.exe tests/test_mobile_package_capabilities.py -q
$env:PYTHONPATH='.'; .\.venv\Scripts\pytest.exe tests/test_auth_rate_limit_integration.py -q
$env:PYTHONPATH='.'; .\.venv\Scripts\pytest.exe tests/test_auth_rate_limit_service.py -q
```

Expected:

- Relevant AUTH-TOKEN, tenant lifecycle, package capability, and rate-limit suites remain green.
- Any known unrelated failure must be documented separately and not hidden.

## 12. Review Checklist Before Implementation Approval

Before approving implementation, verify:

- migration file only creates new table;
- no existing table altered except migration metadata;
- no web session behavior changed;
- no `AUTH-TOKEN-005` behavior regressed;
- `token_hash` does not store raw token;
- strict cutover response is controlled `401`;
- family revoke behavior is tested;
- no deploy/migration run.

## 13. Final Decision

`AUTH-REFRESH-006 OPTION B DESIGN GATE APPROVED`

`MIGRATION DESIGN ACCEPTED`

`NOT APPROVED TO RUN MIGRATION`

`NOT APPROVED TO DEPLOY`

`IMPLEMENTATION REQUIRES HUMAN APPROVAL`
