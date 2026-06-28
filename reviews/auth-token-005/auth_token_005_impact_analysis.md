# AUTH-TOKEN-005 Impact Analysis

Tanggal: 2026-06-28
Mode: analysis + design only
Scope: invalidasi mobile token setelah password change/reset dan event security-sensitive terkait

Tidak dilakukan:

- perubahan kode aplikasi;
- migration;
- deploy;
- seed/backfill;
- operasi database production.

## 1. Finding

Finding asal:

- `MEDIUM-03` - Password change/reset tidak membatalkan mobile token existing.

Risiko:

- Access token yang sudah dicuri tetap valid sampai TTL access berakhir.
- Refresh token yang sudah dicuri tetap dapat dipakai untuk menerbitkan token pair baru sampai TTL refresh berakhir atau token direvoke satu per satu.
- Password reset/change tidak cukup sebagai respons insiden karena credential lama berubah, tetapi mobile bearer token lama masih dipercaya.

## 2. Current Behavior

### Mobile Token Format

File:

- `app/utils/mobile_api_auth.py`

Token mobile diterbitkan dengan payload:

```text
uid = user id
tid = tenant id
typ = access/refresh
jti = random token id
```

Token tidak membawa:

- `token_version`;
- `credentials_changed_at`;
- `password_changed_at`;
- `roles_changed_at`;
- `issued_at` eksplisit di payload aplikasi.

Catatan:

- `itsdangerous.URLSafeTimedSerializer` memiliki timestamp internal untuk `max_age`, tetapi aplikasi tidak membandingkannya dengan state user/security timestamp.
- `jti` hanya random identifier di payload; tidak ada server-side refresh session table yang melakukan atomic consume.

### Mobile Token Validation

File:

- `app/utils/mobile_api_auth.py`
- `app/routes/api/common.py`
- `app/routes/api/auth.py`

Validasi saat ini:

1. token ada;
2. token hash tidak ada di `MobileRevokedToken`;
3. signature valid;
4. token belum expired berdasarkan TTL;
5. `typ` sesuai expected type;
6. `uid` ada;
7. user masih ada;
8. tenant claim cocok dengan `user.tenant_id`;
9. tenant lifecycle active;
10. role/capability valid untuk protected endpoint.

Gap:

- Tidak ada check bahwa token diterbitkan sebelum atau sesudah perubahan credential.
- Tidak ada check bahwa token masih sesuai dengan versi security state user terbaru.

### Logout / Token-Specific Revocation

File:

- `app/routes/api/auth.py`
- `app/utils/mobile_api_auth.py`
- `app/models.py`

Logout mobile:

- merevoke access token current;
- jika refresh token dikirim, refresh token tersebut juga direvoke.

Revocation list:

- `MobileRevokedToken(token_hash, token_type, expires_at, created_at)`
- cocok untuk revoke token spesifik;
- tidak cocok untuk "revoke all tokens for user" tanpa menyimpan semua token aktif atau menambahkan state per user.

### Refresh Flow

File:

- `app/routes/api/auth.py`

Refresh flow:

1. decode refresh token;
2. load user;
3. check tenant claim;
4. check tenant lifecycle active;
5. issue token pair baru;
6. revoke refresh token lama;
7. commit.

Gap terkait AUTH-TOKEN-005:

- Refresh token lama tetap valid setelah password reset/change karena tidak ada user-level invalidation state.

Related existing finding:

- Refresh token rotation race window masih ada. Dua request concurrent bisa melewati revocation check sebelum salah satu commit.
- Ini bisa dianalisis bersama jika desain AUTH-TOKEN-005 memilih server-side refresh session, tetapi tidak harus diselesaikan dalam Phase 1 token invalidation.

## 3. Password and Credential Change Inventory

### User Self-Service Password Change

File:

- `app/routes/auth.py`

Route:

- `GET/POST /auth/ganti-password`

Current behavior:

- cek old password;
- update `current_user.password_hash`;
- set `must_change_password = False`;
- commit;
- web session tetap lanjut.

Gap:

- mobile access/refresh token existing milik user tidak dibatalkan.

### Admin Reset Password

File:

- `app/routes/admin.py`

Routes/flows utama:

- `reset_password(user_id)` untuk student/user role tertentu;
- `generic_reset_password()`;
- `change_login_phone()` jika `reset_password=1`;
- edit teacher dengan password baru;
- edit staff dengan password baru.

Current behavior:

- update `password_hash` atau `set_password()`;
- sebagian flow set `must_change_password=True`;
- sebagian flow set `must_change_password=False`;
- commit.

Gap:

- semua token mobile existing milik target user tetap valid.

### User Creation / Admission Flows

Files:

- `app/routes/admin.py`
- `app/routes/boarding.py`
- `app/routes/staff.py`
- `app/services/admission_service.py`

Observed behavior:

- banyak flow membuat user baru dengan password default dan `must_change_password=True`.

Analysis:

- User creation tidak perlu invalidate token karena belum ada token existing untuk user baru.
- Jika flow memakai user existing lalu hanya menambah role/profile tanpa reset password, invalidation tergantung keputusan role/security event, bukan finding password reset.

### Role Change / Role Assignment

File:

- `app/routes/admin.py`
- `app/routes/boarding.py`

Observed behavior:

- `user.role` dapat diubah.
- `UserRoleAssignment` dapat ditambah/dihapus.

Analysis:

- Current token payload tidak membawa role, sehingga role change akan tercermin saat request berikutnya karena `mobile_auth_required()` load user dari DB dan cek role live.
- Namun jika role/capability/security posture berubah, ada argumen untuk memaksa refresh/login ulang.
- Ini harus menjadi keputusan manusia. Tidak wajib untuk Phase 1 password invalidation.

### Tenant Suspension / User Soft Delete

Current state:

- Tenant lifecycle sudah dicek pada mobile login, refresh, dan protected endpoint.
- User load memakai global soft-delete filter untuk `BaseModel`, sehingga soft-deleted user biasanya tidak ditemukan.

Analysis:

- Tenant suspension sudah menolak token existing melalui lifecycle guard, tanpa perlu token version.
- User soft-delete juga cenderung fail closed karena user tidak ditemukan.
- Tetap bisa diputuskan sebagai event yang bump security state untuk defense in depth, tetapi bukan blocker Phase 1.

## 4. Existing Model / Migration Evidence

### User Model

File:

- `app/models.py`

Relevant fields:

- `password_hash`
- `must_change_password`
- `last_login`
- `role`

Missing fields:

- `token_version`
- `credentials_changed_at`
- `password_changed_at`
- `security_stamp`
- `mobile_tokens_valid_after`

Conclusion:

- Solusi robust AUTH-TOKEN-005 membutuhkan state baru pada user atau token/session table baru.
- Dengan model saat ini, tidak ada field authoritative untuk membedakan token lama vs token baru setelah password change/reset.

### MobileRevokedToken

File:

- `app/models.py`
- `migrations/versions/m3b4c5d6e7f8_add_mobile_auth_state_tables.py`

Fields:

- `token_hash`
- `token_type`
- `expires_at`
- `created_at`

Assessment:

- Cukup untuk revoke token tertentu.
- Tidak cukup untuk revoke semua token milik user tanpa mengetahui token string/hash setiap token aktif.
- Tidak menyimpan `user_id` atau `jti`, sehingga tidak bisa query "all tokens for user".

### MobileDeviceToken

File:

- `app/models.py`
- `migrations/versions/w3l4m5n6o7p8_add_mobile_device_tokens.py`

Assessment:

- Ini device push token, bukan auth token/session.
- Tidak boleh dipakai sebagai source of truth invalidasi access/refresh token.

## 5. Design Options

### Option A - Shorten Mobile Token TTL Only

Idea:

- Turunkan `MOBILE_ACCESS_TOKEN_TTL_SECONDS` dan/atau `MOBILE_REFRESH_TOKEN_TTL_SECONDS`.

Pros:

- Tidak perlu migration.
- Tidak perlu token format change.
- Risiko implementasi kecil.

Cons:

- Tidak menyelesaikan finding.
- Token refresh yang dicuri tetap valid sampai TTL refresh berakhir.
- Password reset tetap tidak punya efek segera.

Recommendation:

- Tidak direkomendasikan sebagai remediation utama.
- Bisa menjadi mitigation sementara hanya jika migration belum bisa dilakukan.

### Option B - Revoke Known Token Only on Password Change

Idea:

- Saat user mengganti password, revoke current mobile token jika tersedia.

Pros:

- Tidak perlu migration jika token string diketahui.

Cons:

- Web password change tidak punya semua token mobile user.
- Admin reset tidak tahu token mobile target user.
- Tidak membatalkan token di device lain.
- Tidak menyelesaikan finding.

Recommendation:

- Tidak cukup.

### Option C - `token_version` on User

Idea:

- Tambah kolom integer `users.token_version`.
- Token membawa claim `ver`.
- Saat password change/reset, increment `user.token_version`.
- Saat access/refresh decode, compare `payload.ver == user.token_version`.

Pros:

- Simple dan robust.
- Tidak bergantung pada clock precision/timezone.
- Mudah ditest.
- Revoke-all-user-tokens cukup increment version.
- Tidak perlu menyimpan semua token aktif.

Cons:

- Membutuhkan migration.
- Token lama tanpa `ver` harus diperlakukan sebagai invalid setelah rollout strict.
- Perubahan token format perlu backward compatibility plan.
- Concurrent update perlu hati-hati agar increment tidak lost update.

Recommendation:

- Direkomendasikan untuk Phase 1 AUTH-TOKEN-005.

### Option D - `credentials_changed_at` / `mobile_tokens_valid_after`

Idea:

- Tambah timestamp pada user, misalnya `credentials_changed_at` atau `mobile_tokens_valid_after`.
- Token membawa issued-at aplikasi (`iat`).
- Token valid jika `iat >= credentials_changed_at`.

Pros:

- Semantics mudah dipahami.
- Bisa juga dipakai untuk audit kapan credential berubah.
- Bisa revoke all tokens by setting timestamp to now.

Cons:

- Perlu token `iat` eksplisit karena serializer timestamp internal tidak mudah/aman dipakai sebagai business claim.
- Rentan edge case precision: token diterbitkan pada detik yang sama dengan password change.
- Perlu timezone-naive/aware consistency.

Recommendation:

- Alternatif valid, tetapi lebih riskan daripada integer `token_version` untuk implementasi kecil.

### Option E - Server-Side Mobile Refresh Sessions

Idea:

- Buat table refresh session/JTI:
  - `user_id`
  - `tenant_id`
  - `refresh_jti`
  - `token_version`
  - `revoked_at`
  - `consumed_at`
  - metadata device/IP
- Access token tetap stateless pendek.
- Refresh token harus match active session dan consume/rotate atomik.

Pros:

- Solusi paling kuat.
- Bisa menutup refresh-token rotation race window.
- Mendukung revoke per device/all device.
- Observability lebih baik.

Cons:

- Migration lebih besar.
- Implementasi dan rollout lebih luas.
- Perlu desain device/session UX.

Recommendation:

- Target long-term atau Phase 2.
- Tidak wajib untuk menutup AUTH-TOKEN-005 Phase 1 jika `token_version` sudah diterapkan.

## 6. Recommended Design

Recommendation: gunakan `token_version` per user untuk Phase 1.

### Data Model

Tambah field:

```text
users.token_version integer not null default 0
```

Migration:

- required;
- backfill existing user ke `0`;
- nullable false + default `0`;
- index tidak wajib untuk Phase 1 karena lookup user by primary key sudah terjadi sebelum compare version.

### Token Payload

Update mobile token payload:

```text
uid = user id
tid = tenant id
typ = access/refresh
jti = random token id
ver = user.token_version
```

### Validation

Add validation after user loaded:

```text
payload.ver must equal user.token_version
```

Apply to:

- `mobile_auth_required()` for access token;
- `auth_refresh()` for refresh token.

Recommended API error:

```text
HTTP 401
code = unauthorized
message = Sesi sudah tidak berlaku. Silakan login ulang.
```

Reason:

- Token is no longer authorized, not tenant/package forbidden.
- Message generic and client-actionable.

### Password Change / Reset Events

Increment `token_version` when an existing user credential changes:

Required Phase 1:

- user self-service password change;
- admin student/user reset password;
- admin generic reset password;
- edit teacher with new password;
- edit staff with new password;
- change login phone with reset password.

Not required for user creation:

- new user has no previous tokens.

Helper recommended:

```text
bump_user_token_version(user)
```

or service:

```text
mark_user_credentials_changed(user, reason, actor_user_id=None)
```

Do not scatter raw `user.token_version += 1` across routes if avoidable.

### Successful Login

Do not increment token version on normal login.

New token pair automatically carries current `token_version`.

### Logout

Keep existing token-specific revocation list.

No change required:

- logout current token still revokes current access and optional refresh;
- token_version handles global invalidation;
- revocation list handles individual token logout.

### Web Session

Recommended Phase 1:

- Do not invalidate current web session on self-service password change because current UX expects redirect to dashboard after change.
- Admin password reset of another user may leave target web session alive unless web session invalidation is also designed.

Security note:

- Finding is about mobile token existing.
- Web session invalidation after admin reset is a related hardening item but should be an explicit decision, not accidental scope expansion.

## 7. Backward Compatibility and Rollout

Problem:

- Existing mobile tokens issued before deployment do not have `ver`.

Recommended rollout options:

### Strict Cutover

Behavior:

- Token without `ver` is rejected after deploy.

Pros:

- Simple.
- Forces all mobile users to login again.
- Immediately closes old-token gap.

Cons:

- Mobile clients experience forced logout.
- Requires communication/support readiness.

Recommended if:

- User base can tolerate one forced re-login.
- Security priority is immediate invalidation correctness.

### Grace Period Compatibility

Behavior:

- Token without `ver` is accepted temporarily if a config flag allows legacy tokens.
- After a fixed date/window, legacy tokens rejected.

Pros:

- Less disruptive.

Cons:

- During grace period, password reset still cannot invalidate legacy tokens without `ver`.
- More branches and test cases.

Recommendation:

- Not preferred unless forced logout is unacceptable.

### Suggested Phase 1 Default

Use strict cutover unless product explicitly requires grace period.

Reason:

- Refresh token TTL may be long.
- Allowing legacy tokens means AUTH-TOKEN-005 remains partially open.

## 8. Test Plan

### Unit / Service Tests

Create tests for token version helper/service:

| Test | Expected |
|---|---|
| new user default token_version | `0` |
| bump increments version | `0 -> 1` |
| repeated bump increments monotonically | `1 -> 2` |
| helper handles missing/null old value during migration compatibility | coerces to next valid int |

### Mobile Token Tests

| Test | Expected |
|---|---|
| login issues token with current user `token_version` | payload has `ver` |
| access token valid before version bump | `/api/v1/auth/me` returns `200` |
| access token invalid after version bump | `/api/v1/auth/me` returns `401 unauthorized` |
| refresh token invalid after version bump | `/api/v1/auth/refresh` returns `401 unauthorized` |
| new login after version bump returns valid tokens | token `ver` matches new version |
| logout token-specific revocation still works | revoked current token returns `401` |
| token tenant lifecycle still enforced | suspended tenant returns `403 tenant_inactive` |

### Password Change Integration Tests

| Test | Expected |
|---|---|
| mobile token issued before web self-service password change is rejected | access + refresh old token denied |
| token issued after password change is accepted | login with new password succeeds |
| wrong old password does not bump version | old mobile token remains valid unless other policy denies |
| must-change-password flow that succeeds bumps version | previous mobile token denied, if any existed |

### Admin Reset Integration Tests

Required routes/flows:

- `admin.reset_password(user_id)`
- `admin.generic_reset_password()`
- teacher edit with password field;
- staff edit with password field;
- `change_login_phone(reset_password=1)`.

Expected:

- target user `token_version` increments only when password actually changes;
- existing mobile access/refresh tokens for target user are denied;
- new login with reset password returns valid tokens.

### Non-Password Flow Tests

| Test | Expected |
|---|---|
| edit teacher without password does not bump version | existing token remains valid |
| edit staff without password does not bump version | existing token remains valid |
| create new user has default version and can login normally | no invalidation side effect |

### Backward Compatibility Tests

If strict cutover:

- token without `ver` returns `401 unauthorized`.

If grace period:

- config on: token without `ver` accepted until expiry;
- config off: token without `ver` rejected.

## 9. Implementation Sequence

Phase 0 - Human decision gate:

1. Approve `token_version` vs timestamp vs server-side session.
2. Approve strict cutover vs grace period.
3. Decide event scope:
   - password change/reset only;
   - role change;
   - tenant suspension;
   - user soft-delete;
   - web session invalidation.

Phase 1 - Migration design:

1. Add `users.token_version`.
2. Backfill default `0`.
3. Add model field.
4. No data deletion.
5. Rollback plan:
   - code rollback must tolerate unused column;
   - DB downgrade drops column only if explicitly approved.

Phase 2 - Token helper changes:

1. Include `ver` in issued mobile tokens.
2. Add validation helper comparing payload `ver` to `user.token_version`.
3. Apply validation in access and refresh paths.
4. Keep token-specific revocation unchanged.

Phase 3 - Credential event service:

1. Add helper to set password and bump version.
2. Replace existing password update sites for existing users.
3. Do not bump on user creation.

Phase 4 - Tests:

1. Add migration/model tests if available.
2. Add mobile token invalidation tests.
3. Add web password change and admin reset integration tests.
4. Run related tenant/rate/package auth tests.

Phase 5 - Review gate:

1. Security review.
2. Code review.
3. Testing & QA review.
4. Migration review.
5. Human deploy approval.

## 10. Risk Analysis

### Mobile forced logout

Strict cutover will invalidate all legacy tokens without `ver`. This is secure but user-visible.

Mitigation:

- communicate forced login;
- deploy during low-traffic window;
- monitor mobile login failures.

### Incomplete password update coverage

Password changes are scattered across routes. Missing one update path leaves token invalidation gap.

Mitigation:

- introduce one helper/service;
- search and replace all `set_password`, `password_hash = generate_password_hash`, and reset flows;
- add regression tests for each existing-password-change flow.

### Migration risk

Adding a non-null field to `users` requires careful migration.

Mitigation:

- add default/backfill safely;
- verify production migration plan;
- no destructive migration.

### Race conditions

If password reset and refresh happen concurrently, order matters.

Expected safe behavior:

- any token pair issued before version bump becomes invalid after bump;
- a refresh that completes after bump should validate against latest version and fail.

Implementation note:

- compare version after loading user and before issuing token pair.

### Web session residual risk

Phase 1 may leave web sessions alive after admin resets another user's password.

Mitigation:

- document as explicit out-of-scope or include web session invalidation in human decision.

### Refresh rotation race remains

`token_version` does not fully solve concurrent refresh reuse.

Mitigation:

- keep as separate hardening item unless server-side refresh sessions are chosen.

## 11. Human Decisions Required

1. Approve preferred mechanism:
   - recommended: `users.token_version`.
2. Approve migration for `users.token_version`.
3. Decide strict cutover vs legacy token grace period.
4. Decide whether `AUTH-TOKEN-005 Phase 1` covers only mobile tokens or also web sessions.
5. Decide invalidation event list:
   - password change;
   - admin reset;
   - role change;
   - tenant suspension;
   - user soft-delete;
   - login phone/security identifier change.
6. Decide API error contract:
   - recommended: `401 unauthorized`, message `Sesi sudah tidak berlaku. Silakan login ulang.`
7. Decide whether to use a central credential service and prohibit direct password hash writes in routes.
8. Decide whether refresh-token rotation race should be merged into this task or split into later `AUTH-REFRESH-006`.

## 12. Recommendation

Proceed to verification/design gate for `AUTH-TOKEN-005` with this direction:

1. Use `users.token_version integer not null default 0`.
2. Include `ver` claim in mobile access and refresh tokens.
3. Reject tokens where `payload.ver != user.token_version`.
4. Reject legacy tokens without `ver` by default unless human approves grace period.
5. Increment version on all existing-user password change/reset flows.
6. Keep logout token-specific revocation unchanged.
7. Do not solve `TENANT-DATA-006` or finance failures in this task.

