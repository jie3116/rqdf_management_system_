# AUTH-RATE-004 Impact Analysis

Tanggal: 2026-06-21  
Mode: analysis + test plan only  
Scope: application-level rate limiting untuk login web dan mobile  
Tidak dilakukan: perubahan kode aplikasi, migration, deploy, seed, backfill, atau maintenance script.

## 1. Current Behavior

Web login:

- Route: `app/routes/auth.py`, `auth.login`.
- Input identifier dari `LoginForm.login_id`.
- Resolver `_resolve_user_for_login()` mencari username/email lalu fallback ke profile identifier lintas role: NIP, phone wali, phone majlis, phone wali asrama, NIS/NISN.
- Jika identifier ambigu, web menampilkan pesan ambiguous.
- Jika user dan password benar, web memeriksa tenant lifecycle untuk non-`SUPER_ADMIN`, lalu login.
- Jika gagal, web menampilkan pesan generik: `Login gagal. Cek kembali Username/Email/NIS/NIP/No HP dan password.`
- Tidak terlihat application-level throttling sebelum atau sesudah password check.

Mobile login:

- Route: `app/routes/api/auth.py`, `POST /api/v1/auth/login`.
- Input identifier dari JSON `identifier` atau `login_id`.
- Tenant hint optional dari body/header: `tenant_id`, `tenant_code`, `tenant_slug`, `X-Tenant-Id`, `X-Tenant-Code`, `X-Tenant-Slug`.
- Resolver awal memakai `_resolve_user_for_login()` global, lalu bila tenant hint ada dapat memakai `_resolve_user_for_login_tenant()`.
- Mobile mengembalikan error berbeda untuk invalid request, ambiguous identifier, invalid credentials, tenant inactive, dan must-change-password.
- Tidak terlihat application-level throttling sebelum atau sesudah password check.

Kesimpulan current behavior:

- Endpoint password web dan mobile dapat menerima percobaan berulang tanpa limit aplikasi.
- Ada pesan ambiguous yang memang informatif untuk UX/tenant disambiguation, tetapi rate limiting harus menghindari memperkuat account enumeration.
- Tidak ada konfigurasi rate limit di `config.py`.

## 2. Existing Model/Table/Migration Evidence

Model tersedia di `app/models.py`:

```text
MobileRateLimitBucket
  id
  bucket_key unique indexed
  action_name indexed
  scope_key indexed
  count
  window_ends_at indexed
  created_at
  updated_at
```

Migration history tersedia:

- File: `migrations/versions/m3b4c5d6e7f8_add_mobile_auth_state_tables.py`
- Revision: `m3b4c5d6e7f8`
- Membuat tabel:
  - `mobile_revoked_tokens`
  - `mobile_rate_limit_buckets`
- Index rate limit:
  - `ix_mobile_rate_limit_buckets_action_name`
  - `ix_mobile_rate_limit_buckets_bucket_key` unique
  - `ix_mobile_rate_limit_buckets_scope_key`
  - `ix_mobile_rate_limit_buckets_window_ends_at`

Usability assessment:

- Schema cukup untuk fixed-window atau coarse sliding-window counter.
- Tabel tidak punya `tenant_id`, `identifier_hash`, atau `ip_hash` kolom terpisah; semua scope harus dikemas ke `bucket_key` dan `scope_key`.
- Tabel bisa dipakai untuk web dan mobile karena tidak ada kolom yang mobile-specific selain nama model.
- Nama `MobileRateLimitBucket` agak misleading untuk web, tetapi tidak perlu migration untuk dipakai sebagai bucket auth umum.
- Production readiness tergantung migration `m3b4c5d6e7f8` sudah benar-benar diterapkan di environment target. Tahap ini tidak menjalankan migration dan tidak memverifikasi database production.

Evidence penggunaan:

- Search source aktif hanya menemukan model `MobileRateLimitBucket`.
- Tidak ada helper/service rate limit aktif.
- Ada jejak `mobile_security.py` dan `test_mobile_api_auth.py` di `__pycache__`, tetapi source aktifnya tidak ada; tidak boleh dianggap implementasi yang tersedia.

## 3. Recommended Design

Buat service/helper rate limit bersama, bukan logic inline di route.

Nama konseptual:

- `app/services/auth_rate_limit_service.py`, atau
- `app/utils/auth_rate_limit.py`

API konseptual:

```text
check_auth_rate_limit(action, identifier, tenant_hint, ip_address, now) -> RateLimitDecision
record_auth_attempt(action, identifier, tenant_hint, ip_address, success, now)
```

Recommended behavior:

1. Rate limit dievaluasi sebelum password hash check untuk mengurangi biaya brute-force.
2. Tetap record failed attempts setelah resolver/password check agar policy account-aware.
3. Jangan membuat permanent account lockout.
4. Gunakan window pendek dan expiry otomatis berdasarkan `window_ends_at`.
5. Simpan identifier dan tenant hint dalam bentuk normalized hash, bukan PII mentah.
6. Gunakan response generik saat rate-limited.
7. Reset atau turunkan counter pada login sukses secara hati-hati; jangan biarkan attacker me-reset bucket milik korban tanpa password benar.
8. Cleanup bucket expired bisa opportunistic pada request login atau scheduled maintenance terpisah.

Recommended algorithm untuk tahap awal:

- Fixed window.
- Beberapa bucket dicek sekaligus:
  - IP-only bucket.
  - identifier+tenant bucket.
  - identifier+tenant+IP bucket.
- Request ditolak jika salah satu bucket melewati limit.
- Pada failed attempt, increment semua bucket.
- Pada success, optional reset hanya bucket identifier+tenant+IP atau set count lebih rendah; jangan reset IP-only global agar brute-force distributed per user tidak menghindar total.

Concurrency note:

- `bucket_key` unique mendukung upsert-like behavior.
- Implementasi harus menangani race pada insert/update bucket. Untuk PostgreSQL idealnya gunakan insert-on-conflict atau retry `IntegrityError`.
- SQLite test bisa memakai flow sederhana dengan retry.

## 4. Rate Limit Key Design

Komponen key:

| Component | Normalization | Stored form |
|---|---|---|
| `action` | stable string: `web_login`, `mobile_login` | plaintext action, bukan PII |
| `identifier` | trim, lowercase where applicable, collapse whitespace | HMAC/SHA-256 hash with app secret or dedicated pepper |
| `tenant_hint` | prefer tenant id if resolved; else normalized code/slug; else `none` | HMAC/SHA-256 hash or non-PII normalized id |
| `ip_scope` | trusted client IP from request; respect proxy headers only if trusted proxy configured | IP prefix hash, not raw IP |
| `window` | floor timestamp by configured window seconds | included in bucket_key or represented by reset when expired |

Suggested bucket key format:

```text
auth:v1:{action}:{scope_type}:{scope_hash}:{window_start_epoch}
```

Suggested `scope_key`:

```text
{scope_type}:{scope_hash}
```

Bucket types:

| Scope type | Purpose | Example limit |
|---|---|---|
| `ip` | stop high-volume brute force from one network | 30 attempts / 5 minutes |
| `identifier_tenant` | stop password guessing against one account/tenant | 5 attempts / 5 minutes |
| `identifier_tenant_ip` | protect one account from one source, useful for UX messaging | 5 attempts / 5 minutes |

Identifier normalization:

- Use same raw input before resolver to avoid leaking whether account exists.
- Lowercase username/email/phone-ish values after trim.
- Do not store NIS/NIP/phone/email in plaintext bucket keys.

Tenant hint:

- If provided and resolves to tenant id, use tenant id.
- If provided but does not resolve, hash the normalized raw hint to avoid letting invalid hints collapse into one bucket.
- If absent, use `tenant:none`.
- Do not reveal in response whether tenant hint was valid.

IP-derived scope:

- Use `request.remote_addr` unless trusted proxy processing is explicitly configured.
- If app is behind Nginx/Gunicorn, define whether `ProxyFix` or trusted `X-Forwarded-For` is already configured before using forwarded headers.
- Consider IPv4 `/24` and IPv6 `/64` prefix buckets to reduce evasion while limiting NAT blast radius carefully. Exact IP bucket is safer for false positives but easier to rotate around.

## 5. Web Login Behavior

Recommended flow:

1. On POST and form validation, normalize identifier and tenant hint as `none`.
2. Build rate-limit decision for action `web_login`.
3. If limited:
   - Do not resolve user or check password.
   - Flash generic message such as `Terlalu banyak percobaan login. Coba lagi beberapa menit.`
   - Return login template with HTTP `429` if practical, or `200` with message if preserving form behavior is preferred.
4. If not limited:
   - Run existing `_resolve_user_for_login()` and password check.
   - Record failed attempt for invalid credentials, ambiguous identifier, inactive tenant, and must-change-password? Recommended:
     - Invalid credentials and ambiguous identifier: record failed.
     - Tenant inactive: record separately with same generic bucket but do not expose more info than current flow.
     - Must-change-password with correct password: do not count as password failure; optional separate action/audit.
   - On successful login, record success/reset allowed buckets.

Account enumeration control:

- Keep invalid credential response generic.
- Avoid rate-limit messages that say account-specific bucket was hit.
- For ambiguous identifier, current app intentionally returns a distinct message. Rate-limit should still apply before this response and not make ambiguity easier to probe at scale.

## 6. Mobile Login Behavior

Recommended flow:

1. Parse payload and tenant hints.
2. If identifier/password missing, return existing `invalid_request` without recording password failure; optional IP-only abuse bucket can be considered later.
3. Normalize identifier and tenant hint raw values before resolving user.
4. Check rate limit for action `mobile_login`.
5. If limited:
   - Return `429` with stable code, e.g. `too_many_requests`.
   - Message generic: `Terlalu banyak percobaan login. Coba lagi beberapa menit.`
   - Include `retry_after_seconds` only if product agrees; it helps clients but can reveal window behavior.
6. If not limited:
   - Run existing resolver and password check.
   - Record failures for invalid credentials and ambiguous identifier.
   - Avoid account-specific response for rate-limited cases.
   - On success, issue token as today and reset/reduce relevant buckets.

Response example:

```json
{
  "success": false,
  "code": "too_many_requests",
  "message": "Terlalu banyak percobaan login. Coba lagi beberapa menit."
}
```

HTTP status:

- Mobile: prefer `429 Too Many Requests`.
- Web: prefer `429` if templates/client can handle it; otherwise keep `200` form render with flash and document why.

## 7. Initial Limits and Configurability

Recommended config keys:

```text
AUTH_RATE_LIMIT_ENABLED=true
AUTH_RATE_LIMIT_WINDOW_SECONDS=300
AUTH_RATE_LIMIT_WEB_IDENTIFIER_ATTEMPTS=5
AUTH_RATE_LIMIT_WEB_IP_ATTEMPTS=30
AUTH_RATE_LIMIT_MOBILE_IDENTIFIER_ATTEMPTS=5
AUTH_RATE_LIMIT_MOBILE_IP_ATTEMPTS=30
AUTH_RATE_LIMIT_IDENTIFIER_IP_ATTEMPTS=5
AUTH_RATE_LIMIT_CLEANUP_PROBABILITY=0.01
AUTH_RATE_LIMIT_HASH_PEPPER=<optional separate secret>
```

Initial conservative defaults:

| Bucket | Limit | Window |
|---|---:|---:|
| identifier+tenant | 5 failed attempts | 5 minutes |
| identifier+tenant+IP | 5 failed attempts | 5 minutes |
| IP | 30 failed attempts | 5 minutes |

Rationale:

- 5 attempts per account/tenant slows password guessing without permanent lockout.
- 30 attempts per IP reduces high-volume attacks while allowing some NAT/shared networks.
- Values must be configurable because school environments may share public IPs.

## 8. Test Matrix

Unit/service tests:

| Test | Expected |
|---|---|
| first attempt creates bucket | count `1`, future `window_ends_at` |
| attempts below limit allowed | decision allowed |
| attempt at/over limit denied | decision denied with retry metadata |
| expired bucket resets | count resets and request allowed |
| identifier is hashed | bucket key/scope key does not contain raw email/phone/NIS |
| tenant hint affects key | same identifier different tenant hint has different identifier bucket |
| IP affects key | same identifier different IP has different identifier+IP bucket |
| unknown tenant hint still scoped | invalid hint does not collapse into global raw bucket |
| successful login resets/reduces expected buckets | subsequent valid login not blocked by stale failed bucket after policy allows |
| concurrent bucket creation handled | unique key race does not crash request |

Web integration tests:

| Test | Expected |
|---|---|
| valid login below limit succeeds | existing redirect/dashboard behavior |
| repeated invalid password hits limit | generic flash, no password check after limited |
| ambiguous identifier attempts are limited | no unlimited ambiguity probing |
| unknown identifier attempts are limited | generic behavior |
| valid password after limit | denied until window reset unless policy says success can override, recommended no override |
| expired window permits retry | allowed |

Mobile integration tests:

| Test | Expected |
|---|---|
| valid login below limit succeeds | token pair returned |
| repeated invalid password hits limit | `429`, code `too_many_requests` |
| missing identifier/password | existing `400 invalid_request`, not counted as password failure |
| ambiguous identifier attempts are limited | `429` after limit |
| tenant hint changes identifier bucket | tenant A and B do not incorrectly share account bucket |
| same IP many identifiers hits IP bucket | `429` after IP limit |
| active tenant lifecycle errors still follow existing policy below limit | `tenant_inactive` still returned below limit |

Security regression tests:

- Response does not reveal account existence when limited.
- Raw identifier/tenant/IP is absent from `bucket_key` and `scope_key`.
- Web and mobile use same service with different `action_name`.

## 9. Rollout Plan

Phase 0 - Verification:

- Confirm production/staging DB has migration `m3b4c5d6e7f8` applied.
- Confirm reverse proxy trusted IP behavior before using forwarded headers.
- Add config keys with safe defaults but keep `AUTH_RATE_LIMIT_ENABLED=false` if a staged rollout is desired.

Phase 1 - Service and tests:

- Implement shared helper/service using existing `MobileRateLimitBucket`.
- Add unit tests for key generation, fixed window, cleanup, and no raw PII in keys.
- No migration if existing table is confirmed.

Phase 2 - Mobile login:

- Apply to `POST /api/v1/auth/login`.
- Use `429 too_many_requests`.
- Monitor denied counts by action/scope type.

Phase 3 - Web login:

- Apply to `/auth/login`.
- Decide final web status code/flash behavior before rollout.
- Monitor support tickets for NAT/shared IP false positives.

Phase 4 - Tuning:

- Adjust limits by observed traffic.
- Consider separate tenant-level aggregate bucket if credential stuffing uses many identifiers per tenant.
- Add dashboard/logging for rate-limit decisions without PII.

Rollback:

- Feature flag can disable enforcement while leaving bucket writes off or in observe-only.
- If table growth is excessive, disable cleanup-on-request only after scheduled cleanup is available.
- No destructive operation required for rollback.

## 10. Risk Analysis

Account enumeration:

- Rate limit must run before revealing invalid/ambiguous/tenant-specific outcomes.
- Limited response must be generic and identical for existing/non-existing accounts.

Permanent lockout/DoS:

- Do not set account locked flags.
- Use temporary windows only.
- Avoid account-only buckets that let attacker lock a known identifier indefinitely; combine with short window and possibly IP/account buckets.

NAT/shared IP:

- IP-only bucket can block many legitimate users behind school or pesantren shared networks.
- Keep IP-only threshold higher than account threshold.
- Log/monitor IP bucket hits separately.

Database load:

- Every failed login writes to rate-limit bucket.
- Unique `bucket_key` and indexed `window_ends_at` help, but high attack traffic can create many rows.
- Need cleanup strategy for expired buckets.

PII:

- Identifier, phone, email, NIS/NIP, tenant slug/code, and IP should not be stored raw.
- Use HMAC or SHA-256 with pepper/secret.

Migration/table availability:

- Model and migration exist, but production database state is not verified in this analysis.
- If migration is not applied in any environment, implementation would fail at runtime.

Behavior change:

- Users with repeated typos may be temporarily blocked.
- Mobile clients must handle `429`.
- Web form UX must clearly tell user to wait without implying account existence.

## 11. Human Decisions Required

1. Is rate limiting authoritative in app, Nginx/WAF, or both?
2. Should web return HTTP `429`, or render login page with `200` plus flash for compatibility?
3. Should mobile include `retry_after_seconds` in response?
4. What initial limits are acceptable for shared school networks?
5. Should successful login reset failed counters, reduce them, or leave them until window expiry?
6. Which IP source is trusted in production: `remote_addr`, `X-Forwarded-For`, or proxy-provided header after `ProxyFix`?
7. Is a separate `AUTH_RATE_LIMIT_HASH_PEPPER` required, or may `SECRET_KEY` be used for HMAC?
8. Should tenant inactive and must-change-password outcomes count as failed login attempts?
9. Is observe-only rollout required before enforcement?
10. Who owns monitoring/alerting for rate-limit spikes?

## 12. Recommendation

Proceed with implementation only after confirming migration `m3b4c5d6e7f8` is applied in target environments or after explicitly planning a migration gate.

No new migration appears necessary if the existing table is present. The preferred implementation is a shared auth rate-limit service using `MobileRateLimitBucket`, with hashed composite keys, fixed short windows, generic responses, and configurable thresholds.

