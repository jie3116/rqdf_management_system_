# AUTH-RATE-004 Phase 1 Review Gate

Tanggal review: 2026-06-26

Status: APPROVED

## Scope Review

Review ini mencakup implementasi Phase 1 rate limiting application-level untuk login web dan mobile:

- config defaults
- shared service `auth_rate_limit_service`
- integrasi mobile login `/api/v1/auth/login`
- integrasi web login `/auth/login`
- service tests
- integration tests

Tidak ada migration baru, tidak ada perubahan ProxyFix/trusted proxy, tidak ada perubahan Nginx rate limit, dan tidak ada deploy.

## File Berubah

- `config.py`
- `app/services/auth_rate_limit_service.py`
- `app/routes/api/auth.py`
- `app/routes/auth.py`
- `tests/test_auth_rate_limit_service.py`
- `tests/test_auth_rate_limit_integration.py`
- `reviews/auth_rate_004_phase1_review.md`

Catatan: dokumen analysis dan verification gate AUTH-RATE-004 sudah ada sebagai artefak pendahulu:

- `reviews/auth_rate_004_impact_analysis.md`
- `reviews/auth_rate_004_verification_gate.md`

## Security Review

Keputusan: APPROVED

Temuan:

- Rate limit menggunakan model existing `MobileRateLimitBucket`, sesuai verification gate.
- `bucket_key` dan `scope_key` dibentuk dari HMAC-SHA256, tidak menyimpan identifier, tenant hint, atau IP mentah.
- Secret HMAC memakai `AUTH_RATE_LIMIT_HASH_PEPPER`, fallback ke `SECRET_KEY`.
- Key mencakup action, normalized identifier, tenant hint, IP-derived scope, dan fixed window.
- Mobile login mengembalikan HTTP 429 dengan code `too_many_requests`.
- Web login menampilkan flash message dan render halaman login tanpa perubahan UX besar.
- Tenant inactive dihitung sebagai failed attempt.
- Must-change-password tidak dihitung sebagai failed attempt.
- Login sukses tidak mereset atau mengurangi bucket.
- `request.remote_addr` tetap digunakan; tidak ada perubahan ProxyFix/trusted proxy.

Residual risk:

- Service melakukan `db.session.commit()` saat mencatat failed attempt. Dalam flow login saat ini belum ada mutasi domain sebelum pencatatan failure, sehingga acceptable untuk Phase 1. Jika nanti dipakai di flow lain, service ini perlu dievaluasi agar tidak commit perubahan transaksi caller yang belum siap.
- Limit berbasis IP dapat berdampak ke user sah di NAT/shared IP. Risiko dikurangi dengan kombinasi identifier+tenant dan identifier+tenant+IP, tetapi `AUTH_RATE_LIMIT_IP_ATTEMPTS` tetap perlu disetel konservatif di production.

## Code Review

Keputusan: APPROVED

Checklist:

- Config default tersedia dan configurable via environment.
- Shared service reusable untuk web dan mobile.
- Tidak ada migration baru.
- Tidak ada perubahan schema/model.
- Tidak ada perubahan behavior endpoint non-login.
- Tidak ada raw PII dalam persisted keys.
- Fixed-window boundary sudah konsisten antara `bucket_key` dan `window_ends_at`.
- Mobile integration ditempatkan setelah validasi request dasar dan sebelum credential resolution.
- Web integration ditempatkan setelah validasi form dan sebelum credential resolution.
- Scope tidak menyentuh finance, ppdb, package/capability, ProxyFix, Nginx, atau deploy config.

## Testing & QA

Keputusan: APPROVED

Test baru:

- `tests/test_auth_rate_limit_service.py`
  - hashed buckets tidak menyimpan PII mentah
  - block setelah configured attempts
  - window expiry
  - tenant hint dan IP mempartisi bucket

- `tests/test_auth_rate_limit_integration.py`
  - mobile invalid password menjadi 429 setelah limit
  - mobile valid credentials tidak bypass bucket yang sudah limited
  - mobile tenant inactive dihitung failure
  - mobile must-change-password tidak dihitung failure
  - mobile ambiguous identifier dihitung dan dibatasi
  - web login limited render login tanpa redirect/session login
  - web valid login di bawah limit tetap sukses

Hasil test relevan:

```text
tests/test_auth_rate_limit_service.py
4 passed

tests/test_auth_rate_limit_integration.py
7 passed

tests/test_mobile_auth_tenant_status.py tests/test_web_auth_tenant_status.py
15 passed
```

Full suite:

```text
50 passed, 1 failed
```

Kegagalan full suite:

- `tests/test_finance_core.py::test_reverse_journal_creates_opposite_lines_and_voids_cash_bank_source`
- Root cause: `reverse_journal()` memakai `date.today()` dan pada tanggal review 2026-06-26 fixture finance tidak membuat periode akuntansi untuk tanggal tersebut.
- Status: di luar scope AUTH-RATE-004 dan tidak diperbaiki pada task ini sesuai instruksi jangan menyentuh finance failure.

## Review Checklist

- [x] `MobileRateLimitBucket` existing dipakai ulang.
- [x] Tidak ada migration baru.
- [x] Web dan mobile memakai shared service.
- [x] Identifier dan tenant hint memakai HMAC-SHA256.
- [x] Tidak menyimpan PII mentah di `bucket_key` atau `scope_key`.
- [x] Mobile menggunakan HTTP 429.
- [x] Web menggunakan flash message dan render login seperti biasa.
- [x] Tenant inactive dihitung failed attempt.
- [x] Must-change-password tidak dihitung failed attempt.
- [x] Login sukses tidak mereset atau mengurangi bucket.
- [x] ProxyFix/trusted proxy tidak disentuh.
- [x] Nginx rate limit tidak disentuh.
- [x] Test service dan integration relevan lulus.

## Decision

APPROVED untuk lanjut ke review manusia/commit gate.

Catatan release: sebelum deploy production, pastikan nilai environment production untuk `AUTH_RATE_LIMIT_*` direview, terutama threshold IP untuk lingkungan NAT/shared IP.
