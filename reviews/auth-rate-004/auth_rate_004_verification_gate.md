# AUTH-RATE-004 Verification Gate

Tanggal: 2026-06-22  
Mode: verification gate, read-only  
Scope: migration `m3b4c5d6e7f8`, `MobileRateLimitBucket`, production/proxy assumptions, existing rate-limit helpers, dan kesiapan reuse untuk web/mobile login.  
Tidak dilakukan: implementasi kode, migration, deploy, seed, backfill, atau operasi database production.

## Decision

**APPROVED** untuk implementasi AUTH-RATE-004 Phase 1.

Approval ini hanya untuk implementasi kode dan test lokal. Sebelum deploy production tetap perlu gate terpisah untuk memastikan migration `m3b4c5d6e7f8` sudah applied pada database target.

## 1. Migration Verification

Migration yang diverifikasi:

- File: `migrations/versions/m3b4c5d6e7f8_add_mobile_auth_state_tables.py`
- Revision ID: `m3b4c5d6e7f8`
- `down_revision`: `l2a3b4c5d6e7`

Status codebase:

- File migration ada.
- Revision `m3b4c5d6e7f8` masih tersambung dalam migration graph.
- Downstream migration `n4c5d6e7f8g9_add_surah_fields_to_tahfidz_evaluations.py` memakai `down_revision = 'm3b4c5d6e7f8'`, sehingga revision ini tidak orphaned.

Migration definition membuat:

- `mobile_revoked_tokens`
- `mobile_rate_limit_buckets`

Definition `mobile_rate_limit_buckets`:

- `id`
- `bucket_key` string 255, not null, unique
- `action_name` string 50, not null, indexed
- `scope_key` string 255, not null, indexed
- `count` integer, not null
- `window_ends_at` datetime, not null, indexed
- `created_at` datetime, not null
- `updated_at` datetime, not null

Conclusion:

- Migration tersedia dan aktif pada codebase.
- Tidak perlu migration baru untuk Phase 1 jika DB target sudah menerapkan revision ini.

## 2. Model Audit

Model:

- File: `app/models.py`
- Class: `MobileRateLimitBucket`
- Table: `mobile_rate_limit_buckets`

Model fields match migration intent:

- `bucket_key = db.Column(db.String(255), nullable=False, unique=True, index=True)`
- `action_name = db.Column(db.String(50), nullable=False, index=True)`
- `scope_key = db.Column(db.String(255), nullable=False, index=True)`
- `count = db.Column(db.Integer, nullable=False, default=0)`
- `window_ends_at = db.Column(db.DateTime, nullable=False, index=True)`
- `created_at = db.Column(db.DateTime, default=utc_now_naive, nullable=False)`
- `updated_at = db.Column(db.DateTime, default=utc_now_naive, onupdate=utc_now_naive, nullable=False)`

Usability:

- Aman dipakai sebagai fixed-window bucket untuk web dan mobile login.
- Nama model masih mobile-specific, tetapi schema tidak mobile-specific.
- Tidak ada `tenant_id`, `identifier_hash`, atau `ip_hash` terpisah, sehingga composite scope harus dikemas ke `bucket_key` dan `scope_key`.
- `bucket_key` unique cukup untuk upsert/retry pattern.
- Implementasi harus menangani race insert/update dengan retry atau dialect-specific conflict handling.

## 3. Production Assumptions

Runtime artifacts:

- `docker-compose.yml` menjalankan `gunicorn -w 4 -b 0.0.0.0:8000 run:app`.
- Nginx config repo `config/nginx.app.conf` proxy ke `127.0.0.1:8000`.
- Nginx mengirim:
  - `X-Real-IP $remote_addr`
  - `X-Forwarded-For $proxy_add_x_forwarded_for`
  - `X-Forwarded-Proto $scheme`

Unverified assumptions:

- Tidak dilakukan koneksi ke database production.
- Tidak diverifikasi tabel `mobile_rate_limit_buckets` benar-benar ada di production.
- Tidak diverifikasi apakah Nginx config repo identik dengan config live.

Deployment gate requirement:

- Sebelum deploy enforcement, manusia harus memastikan migration `m3b4c5d6e7f8` sudah applied di staging/production.

## 4. ProxyFix / X-Forwarded-For / remote_addr Audit

Findings:

- Tidak ditemukan `ProxyFix` di source aktif.
- Tidak ditemukan penggunaan `X-Forwarded-For`, `X-Real-IP`, atau `request.access_route` di source aktif.
- Penggunaan `request.remote_addr` ada pada route admin/staff untuk audit/logging:
  - `app/routes/admin.py`
  - `app/routes/staff.py`

Implication:

- Untuk Phase 1, helper rate limit sebaiknya menggunakan `request.remote_addr` sebagai sumber IP.
- Jangan langsung percaya `X-Forwarded-For` karena Flask app belum dikonfigurasi dengan trusted proxy handling.
- Bila nanti ingin memakai IP user asli dari Nginx, buat task terpisah untuk trusted proxy configuration, misalnya `ProxyFix` dengan jumlah proxy yang eksplisit dan review deployment topology.

Risk:

- Dalam deployment Nginx -> Gunicorn lokal, `request.remote_addr` kemungkinan bernilai alamat proxy/container, bukan user asli. Ini dapat membuat IP bucket terlalu luas dan memblokir banyak user.
- Karena itu Phase 1 harus menjaga IP-only limit cukup longgar dan mengandalkan identifier+tenant bucket sebagai kontrol utama.

## 5. Existing Rate-Limit Helper Audit

Search source aktif:

- `app/**/*.py`
- `tests/**/*.py`

Result:

- Tidak ditemukan helper/service rate-limit aktif.
- Tidak ditemukan penggunaan aktif `MobileRateLimitBucket` selain definisi model.
- Tidak ditemukan source `app/utils/mobile_security.py` atau `tests/test_mobile_api_auth.py`.
- Ada jejak nama tersebut di `__pycache__`, tetapi file source tidak ada dan tidak boleh dipakai sebagai dependency.

Conclusion:

- Tidak ada helper rate-limit existing yang terlewat.
- Implementasi Phase 1 harus membuat service/helper baru.

## 6. Reuse Decision

`MobileRateLimitBucket` aman dipakai ulang untuk:

- web login
- mobile login

Dengan batasan:

- Treat sebagai generic auth rate-limit bucket meskipun nama model mobile-specific.
- Jangan menyimpan PII raw di `bucket_key` atau `scope_key`.
- Gunakan `action_name` berbeda untuk web dan mobile, misalnya `web_login` dan `mobile_login`.
- Gunakan feature/config flag agar enforcement bisa dimatikan tanpa migration.
- Jangan memakai header forwarded sampai trusted proxy handling diputuskan.

## 7. APPROVED Implementation Plan - Phase 1

### Step 1 - Add Config Defaults

Tambahkan config non-secret di `config.py`:

- `AUTH_RATE_LIMIT_ENABLED`
- `AUTH_RATE_LIMIT_WINDOW_SECONDS`
- `AUTH_RATE_LIMIT_IDENTIFIER_ATTEMPTS`
- `AUTH_RATE_LIMIT_IDENTIFIER_IP_ATTEMPTS`
- `AUTH_RATE_LIMIT_IP_ATTEMPTS`
- `AUTH_RATE_LIMIT_CLEANUP_PROBABILITY`
- optional `AUTH_RATE_LIMIT_HASH_PEPPER`, fallback ke `SECRET_KEY`

Recommended initial defaults:

- enabled: `true` for tests; production value can be env-controlled
- window: `300` seconds
- identifier+tenant: `5`
- identifier+tenant+IP: `5`
- IP-only: `30`
- cleanup probability: `0.01`

### Step 2 - Add Shared Service

Create `app/services/auth_rate_limit_service.py`.

Core responsibilities:

- Normalize identifier.
- Normalize tenant hint.
- Resolve request IP from `request.remote_addr`.
- Hash PII/sensitive values with HMAC-SHA256.
- Build bucket keys for:
  - `identifier_tenant`
  - `identifier_tenant_ip`
  - `ip`
- Check if any bucket is over limit.
- Record failed attempts.
- Optionally clear/reduce relevant buckets on successful login.
- Opportunistically delete expired buckets.

Suggested API:

```python
check_auth_rate_limit(action_name, identifier, tenant_hint=None, ip_address=None)
record_auth_rate_limit_failure(action_name, identifier, tenant_hint=None, ip_address=None)
record_auth_rate_limit_success(action_name, identifier, tenant_hint=None, ip_address=None)
```

Return object:

- `limited`
- `retry_after_seconds`
- `limited_scope`

### Step 3 - Add Tests for Service

Create focused tests, likely `tests/test_auth_rate_limit_service.py`.

Must cover:

- first failed attempt creates buckets;
- below limit allowed;
- over limit denied;
- expired window resets;
- raw identifier absent from `bucket_key`/`scope_key`;
- different tenant hints produce different identifier buckets;
- different IPs produce different identifier+IP buckets;
- `request.remote_addr` behavior can be passed as explicit `ip_address` in service tests;
- no permanent lockout state on `User`.

### Step 4 - Apply to Mobile Login

File:

- `app/routes/api/auth.py`

Behavior:

- Before resolver/password check, call `check_auth_rate_limit("mobile_login", identifier, tenant_hint, ip)`.
- On limited, return:

```json
{
  "success": false,
  "code": "too_many_requests",
  "message": "Terlalu banyak percobaan login. Coba lagi beberapa menit."
}
```

Status:

- `429`

Record failure for:

- invalid credentials;
- ambiguous identifier;
- optionally tenant inactive, depending final decision.

Do not count:

- missing identifier/password `invalid_request`, unless abuse bucket is explicitly approved.

### Step 5 - Apply to Web Login

File:

- `app/routes/auth.py`

Behavior:

- Before `_resolve_user_for_login()`/password check, call same service with `action_name="web_login"`.
- On limited, flash generic message.
- Recommended status: `429` while rendering login template. If template/browser behavior makes this risky, use `200` and document compatibility decision.

Record failure for:

- invalid credentials;
- ambiguous identifier.

Do not create permanent user/account lock.

### Step 6 - Add Integration Tests

Mobile:

- valid login below limit succeeds;
- repeated invalid password returns `429 too_many_requests`;
- unknown identifier limited;
- ambiguous identifier limited;
- valid credentials after limit blocked until window expiry;
- tenant inactive behavior remains stable below limit.

Web:

- valid login below limit succeeds;
- repeated invalid password shows generic rate-limit response;
- ambiguous identifier limited;
- unknown identifier limited;
- raw identifier not stored.

### Step 7 - Verification

Run:

```powershell
$env:PYTHONPATH='.'; .\.venv\Scripts\pytest.exe tests/test_auth_rate_limit_service.py -q
$env:PYTHONPATH='.'; .\.venv\Scripts\pytest.exe tests/test_mobile_auth_tenant_status.py -q
$env:PYTHONPATH='.'; .\.venv\Scripts\pytest.exe tests/test_web_auth_tenant_status.py -q
```

Also run full suite if time permits. Existing unrelated finance date-sensitive failure should be tracked separately if it remains.

## 8. Human Follow-Up Before Deploy

Required before deploy, not before local implementation:

1. Confirm migration `m3b4c5d6e7f8` is applied to target DB.
2. Decide web limited response status: `429` vs `200`.
3. Decide whether mobile includes `retry_after_seconds`.
4. Decide whether tenant inactive attempts count as failures.
5. Decide whether to add `ProxyFix` in a separate deployment-aware task.

