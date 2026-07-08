# AUTH-REFRESH-006 Phase 1 Code Review

Tanggal review: 2026-07-09

## Scope Review

Review ini mencakup:

- server-side refresh token rotation;
- model `MobileRefreshToken`;
- migration `mobile_refresh_tokens`;
- mobile login refresh-row creation;
- mobile refresh one-time consume;
- reuse detection;
- family revoke on reuse;
- logout refresh-family revoke;
- strict cutover for legacy refresh token without server-side row;
- tests.

Review ini tidak mencakup:

- production migration;
- deploy;
- web session change;
- `AUTH-TOKEN-005` behavior change;
- tenant/package/rate-limit remediation;
- `TENANT-DATA-006`.

## Changed Files Reviewed

Implementation files reviewed:

- `app/models.py`
- `app/routes/api/auth.py`
- `app/utils/mobile_api_auth.py`
- `app/services/mobile_refresh_token_service.py`
- `migrations/versions/bg67hi89jk01_add_mobile_refresh_tokens.py`
- `tests/test_mobile_refresh_token_rotation.py`

Catatan:

- Ada working tree changes lain di `reviews/`.
- Perubahan tersebut dianggap documentation/review artifacts, bukan implementation scope AUTH-REFRESH-006.

## Decision

`APPROVED FOR HUMAN CODE REVIEW`

`READY FOR MIGRATION/DEPLOY GATE AFTER HUMAN REVIEW`

`NOT APPROVED TO RUN PRODUCTION MIGRATION`

`NOT APPROVED TO DEPLOY`

## Checklist Results

### Changed Files Scope

PASS.

Implementation scope terbatas pada model, route mobile auth, token helper, service refresh-token rotation, migration, dan focused tests.

### Migration Review

PASS.

Migration:

- hanya membuat table `mobile_refresh_tokens`;
- tidak mengubah table existing selain Alembic metadata saat migration nanti dijalankan;
- memakai string status, bukan DB enum;
- menambahkan required columns;
- menambahkan unique constraint `jti`;
- menambahkan unique constraint `token_hash`;
- menambahkan index `user_id`;
- menambahkan index `tenant_id`;
- menambahkan index `family_id`;
- menambahkan index `status`;
- menambahkan index `expires_at`;
- menambahkan composite index `(user_id, tenant_id, status)`;
- menambahkan FK ke `users` dan `tenants`;
- downgrade drops table.

### Model Review

PASS.

`MobileRefreshToken`:

- table name benar: `mobile_refresh_tokens`;
- kolom sesuai gate;
- status constants tersedia: `ACTIVE`, `CONSUMED`, `REVOKED`, `REUSED`;
- `tenant_id` non-null, konsisten dengan `User.tenant_id`;
- `token_hash` menyimpan hash, bukan raw token;
- timestamp fields mengikuti pola project.

### Token Helper Review

PASS.

- Refresh token tetap membawa `uid`, `tid`, `typ`, `jti`, `ver`.
- `jti` tetap dibuat unik.
- `mobile_token_hash()` memakai SHA-256 convention existing.
- Raw token tidak dilog.
- `AUTH-TOKEN-005` `ver` behavior tidak berubah.
- Access token validation tidak diubah secara tidak perlu.

### Service Review

PASS.

`app/services/mobile_refresh_token_service.py`:

- login creates `ACTIVE` row correctly;
- lookup memakai `jti` dan `token_hash`;
- expired server-side row ditolak;
- missing row ditolak controlled;
- reuse detection menandai `reuse_detected_at` jika possible;
- reuse revokes `ACTIVE` tokens in same family;
- logout with refresh token revokes refresh family;
- logout without refresh token behavior tetap existing;
- no raw refresh token stored.

### Atomicity Review

PASS with FOLLOW-UP.

Detail:

- Implementation uses `with_for_update()` row lock.
- Old-token consume and new-token insert happen in one DB transaction.
- Token pair is not returned if consume or commit fails.
- `IntegrityError` is handled as controlled `401`.
- Two refresh attempts with same token should not both return `200`.
- Follow-up: SQLite tests do not prove true PostgreSQL concurrent locking.
- PostgreSQL-backed staging verification is required before production migration/deploy.

### Route Review

PASS.

`app/routes/api/auth.py`:

- mobile login membuat server-side refresh row;
- `auth_refresh()` menjaga urutan decode token, load user, validate tenant claim, validate token_version, validate tenant lifecycle, consume old refresh token server-side, issue/create replacement token, commit, return response;
- controlled `401` memakai message `Sesi sudah tidak berlaku. Silakan login ulang.`;
- tenant inactive behavior tidak berubah;
- logout tetap memakai `MobileRevokedToken` untuk access token.

### Strict Cutover Review

PASS.

- Refresh token valid secara cryptographic tapi tanpa server-side row ditolak controlled `401`.
- Tidak ada compatibility fallback yang menerima legacy refresh token lama.
- Behavior sesuai human decision.

### Test Review

PASS.

`tests/test_mobile_refresh_token_rotation.py` mencakup:

- mobile login creates `ACTIVE` refresh token row;
- row stores hash, not raw refresh token;
- refresh consumes old row and creates new `ACTIVE` row;
- old row becomes `CONSUMED`;
- `replaced_by_jti` points to new refresh `jti`;
- reused old token returns controlled `401`;
- reuse revokes active tokens in same family;
- two refresh attempts with same token cannot both succeed;
- token without server-side row returns controlled `401`;
- logout with refresh token revokes family;
- logout without refresh token preserves existing access-only behavior;
- password change/token_version bump rejects old refresh token;
- missing/stale/non-integer `ver` rejected;
- tenant inactive rejected as before;
- malformed token rejected;
- access token sent to refresh endpoint rejected;
- missing user rejected;
- tenant mismatch rejected;
- expired server-side row rejected;
- two separate login families are isolated.

### Regression Test Evidence

PASS.

Relevant regression suites passed.

## Test Evidence

```text
tests/test_mobile_refresh_token_rotation.py -q
18 passed

tests/test_mobile_token_version_invalidation.py -q
18 passed

tests/test_mobile_auth_tenant_status.py -q
11 passed

tests/test_mobile_package_capabilities.py -q
15 passed

tests/test_auth_rate_limit_integration.py -q
7 passed

tests/test_auth_rate_limit_service.py -q
4 passed
```

## Risk Classification

### Blockers

- None.

### Should Fix Before Migration

- None required from code review.

### Follow-Up

- Run PostgreSQL-backed concurrency/staging verification before production migration/deploy.
- Add retention/cleanup plan for old `mobile_refresh_tokens` rows.
- Strict cutover may force mobile re-login; release notes/client messaging should cover this.

## Final Recommendation

AUTH-REFRESH-006 Phase 1 implementation is ready for human code review.

After human code review, next step is a dedicated migration/deploy gate.

Production migration must not be run until explicit human approval.

Deploy must not be performed until explicit human approval.
