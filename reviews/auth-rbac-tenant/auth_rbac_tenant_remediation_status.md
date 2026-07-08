# AUTH/RBAC/Tenant Remediation Status

Tanggal update: 2026-06-28

Sumber:

- `reviews/auth-rbac-tenant/auth_rbac_tenant_audit.md`
- `reviews/auth-rbac-tenant/auth_rbac_tenant_remediation_backlog.md`
- `reviews/auth-package-003/auth_package_003_impact_analysis.md`
- `reviews/auth-package-003/package_capability_matrix_v2.md`
- `reviews/auth-package-003/auth_package_003_phase1_review.md`
- `reviews/auth-rate-004/auth_rate_004_impact_analysis.md`
- `reviews/auth-rate-004/auth_rate_004_verification_gate.md`
- `reviews/auth-rate-004/auth_rate_004_phase1_review.md`
- `reviews/auth-token-005/auth_token_005_impact_analysis.md`
- `reviews/auth-token-005/auth_token_005_verification_gate.md`
- `reviews/auth-token-005/auth_token_005_phase1_code_review.md`
- `reviews/auth-token-005/auth_token_005_migration_deploy_gate.md`
- `reviews/auth-token-005/auth_token_005_post_deploy_verification.md`
- `reviews/platform-tenant/platform_tenant_super_admin_policy.md`
- `reviews/platform-tenant/platform_tenant_inventory.md`
- `reviews/platform-tenant/platform_tenant_script_review.md`

## Executive Summary

Remediation auth, RBAC, tenant lifecycle, mobile package enforcement, login rate limiting, dan mobile token invalidation sudah menyelesaikan lima item awal dari backlog utama:

1. `AUTH-TENANT-001` selesai.
2. `AUTH-TENANT-002` selesai.
3. `AUTH-PACKAGE-003` Phase 1 selesai.
4. `AUTH-RATE-004` Phase 1 selesai, sudah deploy, dan sudah smoke-tested aman oleh human operator.
5. `AUTH-TOKEN-005` Phase 1 selesai, migration production berhasil, dan post-deploy verification passed.

Sisa pekerjaan utama dari audit awal:

1. `TENANT-DATA-006` - master akademik global masih perlu keputusan ownership sebelum disentuh.
2. `AUTH-REFRESH-006` / refresh-token rotation race window - belum diselesaikan oleh `AUTH-TOKEN-005`.
3. Medium/low hardening lain: active-role semantics, soft-delete contract, fallback tenant resolver, dan package add-on enforcement.

Rekomendasi next work: lanjut ke `AUTH-REFRESH-006` dengan tahap analysis/design only, atau putuskan lebih dulu active-role semantics jika ingin menjadikannya authorization boundary. Jangan mulai `TENANT-DATA-006` sebelum keputusan ownership master akademik dan migration strategy disetujui.

## Status Matrix

| ID | Finding | Severity | Status | Migration | Deploy | Catatan |
|---|---|---:|---|---|---|---|
| `AUTH-TENANT-001` | Mobile authentication menerima user dari tenant nonaktif | HIGH | Done | Tidak | Done sebelumnya | Mobile login, refresh, dan access token existing mengikuti tenant lifecycle active. |
| `AUTH-TENANT-002` | Existing web session tetap aktif setelah tenant disuspensi | HIGH | Done | Tidak | Done sebelumnya | Web authenticated request sudah memakai tenant lifecycle guard. |
| Platform tenant | `SUPER_ADMIN` perlu platform/internal tenant | Policy dependency | Done | Tidak | Done sebelumnya | Platform tenant sudah dibuat dan `SUPER_ADMIN` sudah dipindahkan berdasarkan konfirmasi proses sebelumnya. |
| `AUTH-PACKAGE-003` Phase 1 | Mobile API bypass package/module restriction | HIGH | Done | Tidak | Done sebelumnya | Enforcement capability mobile sudah diterapkan untuk `teacher`, `boarding`, dan `majlis`. |
| `AUTH-RATE-004` Phase 1 | Login web/mobile belum punya application-level rate limiting | MEDIUM | Done | Tidak | Done | Human operator sudah deploy dan test hasil aman. |
| `AUTH-TOKEN-005` Phase 1 | Password change/reset tidak membatalkan mobile token existing | MEDIUM | Done | Ya, applied | Done | `users.token_version` diterapkan; mobile token membawa claim `ver`; token lama/stale ditolak; post-deploy verification passed. |
| `TENANT-DATA-006` | Master akademik global memungkinkan dampak lintas tenant | HIGH | Hold | Kondisional/kemungkinan ya | Belum | Jangan disentuh sampai keputusan platform-owned vs tenant-owned. |

## Completed Work Details

### AUTH-TENANT-001

Status: Done.

Scope yang sudah diselesaikan:

- Mobile login menolak user tenant nonaktif.
- Mobile refresh menolak token user tenant nonaktif.
- Protected mobile endpoint menolak access token existing setelah tenant dinonaktifkan.
- Tenant hint tidak boleh membuat tenant nonaktif menjadi kandidat login valid.

Residual risk:

- Password change/reset token invalidation sudah ditangani oleh `AUTH-TOKEN-005` Phase 1.
- Role change, tenant suspend, dan soft delete tidak melakukan bump token version sesuai keputusan scope `AUTH-TOKEN-005`; tenant suspend dan soft delete tetap bergantung pada tenant/user lifecycle guard existing.

### AUTH-TENANT-002

Status: Done.

Scope yang sudah diselesaikan:

- Web authenticated request mengikuti tenant lifecycle policy.
- Existing session tenant suspended/archived tidak boleh terus memakai aplikasi.
- Flow login/logout/change-password tetap perlu dijaga dari redirect loop pada regression test.

Residual risk:

- Semantics active role belum diputuskan sebagai authorization boundary atau hanya UI context.

### Platform Tenant dan SUPER_ADMIN

Status: Done berdasarkan konteks operasional terakhir.

Catatan:

- Dokumen `platform_tenant_inventory.md` adalah snapshot lama saat platform tenant belum ada.
- Kondisi saat ini, menurut status remediation sebelumnya, platform tenant sudah dibuat dan `SUPER_ADMIN` sudah dipindahkan.
- Belum ada migration `tenant_type`; platform tenant masih memakai pendekatan tanpa schema change.

Residual risk:

- Model `Tenant` belum punya field eksplisit `tenant_type`.
- Long-term policy masih lebih kuat jika ada migration `tenant_type = PLATFORM/CUSTOMER`, tetapi ini bukan prasyarat item auth berikutnya.

### AUTH-PACKAGE-003 Phase 1

Status: Done.

Scope yang selesai:

- Capability constants/helper ditambahkan.
- Legacy adapter:
  - `full` -> integrated/all capabilities.
  - `sekolah` -> school capabilities.
  - `rumah_quran` -> quran capabilities.
- Mobile capability enforcement untuk:
  - teacher endpoints;
  - boarding endpoints;
  - majlis endpoints.
- `SUPER_ADMIN` bypass capability check, tetap mengikuti tenant policy existing.
- Scope tidak menyentuh parent mixed endpoints, finance, PPDB, online class, AI assistant, analytics, atau announcement.

Catatan audit trail:

- `reviews/auth-package-003/auth_package_003_phase1_review.md` masih memuat review gate lama dengan keputusan `REQUEST CHANGES` untuk blocker `tenant_has_capability(None, ...)`.
- Blocker tersebut kemudian diperbaiki dan review ulang dinyatakan approved dalam proses remediation.
- Dokumen ini menjadi status roll-up terbaru untuk menyatakan Phase 1 sudah selesai.

Residual risk:

- Parent mixed endpoints belum dipetakan capability.
- Finance/add-on enforcement belum dimulai.
- Web guard existing belum dimigrasikan penuh ke reusable capability policy.
- Tenant tanpa config package masih mengikuti compatibility default legacy.

### AUTH-RATE-004 Phase 1

Status: Done, deployed, dan smoke-tested aman oleh human operator.

Scope yang selesai:

- Config defaults `AUTH_RATE_LIMIT_*`.
- Shared service untuk web dan mobile login.
- `MobileRateLimitBucket` existing dipakai ulang.
- HMAC-SHA256 untuk identifier, tenant hint, dan IP-derived scope.
- Tidak menyimpan PII mentah di `bucket_key` atau `scope_key`.
- Mobile login return `429 too_many_requests`.
- Web login memakai flash message dan render login seperti biasa.
- Tenant inactive dihitung failed attempt.
- Must-change-password tidak dihitung failed attempt.
- Login sukses tidak reset/reduce bucket.
- ProxyFix/trusted proxy dan Nginx rate limit tidak disentuh.

Review gate:

- `reviews/auth-rate-004/auth_rate_004_phase1_review.md`
- Decision: `APPROVED`

Test evidence terakhir:

```text
tests/test_auth_rate_limit_service.py
4 passed

tests/test_auth_rate_limit_integration.py
7 passed

tests/test_mobile_auth_tenant_status.py tests/test_web_auth_tenant_status.py
15 passed
```

Full suite terakhir:

```text
50 passed, 1 failed
```

Known unrelated failure:

- `tests/test_finance_core.py::test_reverse_journal_creates_opposite_lines_and_voids_cash_bank_source`
- Root cause: finance reversal memakai `date.today()` dan fixture tidak memiliki periode akuntansi untuk tanggal eksekusi test.
- Status: out of scope AUTH-RATE-004 dan tidak disentuh.

Residual risk:

- Threshold `AUTH_RATE_LIMIT_*` perlu dimonitor di production, terutama untuk NAT/shared IP.
- Service mencatat failed attempt dengan commit sendiri; acceptable untuk login flow saat ini, tetapi perlu evaluasi jika service digunakan di flow lain.

### AUTH-TOKEN-005 Phase 1

Status: Done, migration applied, deployed, dan post-deploy verification passed.

Scope yang selesai:

- Migration `af56gh78ij90_add_user_token_version.py` menambahkan `users.token_version INTEGER NOT NULL DEFAULT 0`.
- Mobile access/refresh token baru membawa claim `ver`.
- Mobile access-token validation menolak token lama/stale/missing `ver` dengan controlled `401 unauthorized`.
- Mobile refresh-token validation menolak token lama/stale/missing `ver` sebelum menerbitkan token pair baru.
- Existing-user password mutation flow dipusatkan melalui credential security service untuk bump `token_version`.
- Logout revocation tetap memakai `MobileRevokedToken`.
- Strict cutover diterapkan: token mobile lama tanpa `ver` ditolak dan user mobile mungkin perlu login ulang.

Production evidence:

- Migration reported: `ae45fg67hi89 -> af56gh78ij90, add user token version`.
- Alembic current/head production: `af56gh78ij90 (head)`.
- Schema production: `token_version integer NOT NULL default 0`.
- Backup: `backups/pre_deploy_2026-06-28_140722.dump`, verified with `pg_restore -l`.
- Post-deploy artifact: `reviews/auth-token-005/auth_token_005_post_deploy_verification.md`.

Residual risk:

- `AUTH-REFRESH-006` remains separate; token version does not implement server-side refresh session or atomic refresh rotation.
- Legacy token without `ver` rejection is intended strict-cutover behavior.
- Web sessions were not included in token_version invalidation scope.

## Remaining Findings

### AUTH-REFRESH-006 - Recommended Next

Finding:

- Refresh token rotation race window masih belum ditutup oleh `AUTH-TOKEN-005`.

Risiko:

- Jika dua refresh request memakai token lama secara hampir bersamaan, behavior atomic consume/revoke perlu diverifikasi. `token_version` hanya menolak token setelah credential version berubah, bukan menyelesaikan race antar-refresh token valid.

Kenapa ini next:

- Masih satu boundary mobile token security.
- Dapat dianalisis terpisah dari `TENANT-DATA-006`.
- Bisa mulai dari analysis/design only tanpa langsung migration.

Keputusan manusia yang dibutuhkan:

1. Apakah Phase 1 cukup dengan hardening `MobileRevokedToken`/JTI stateless, atau perlu server-side refresh session.
2. Apakah refresh token harus one-time use dengan atomic database update.
3. TTL access/refresh token target.
4. Apakah migration untuk refresh session table diterima.
5. Response contract untuk reuse/race token.

Recommended first step:

- Buat `reviews/auth-refresh-006/auth_refresh_006_impact_analysis.md`.
- Tahap awal analysis + test plan only, tanpa migration dan tanpa deploy.

### TENANT-DATA-006 - Hold

Finding:

- `AcademicYear`, `Subject`, dan master akademik legacy masih global sehingga admin satu tenant berpotensi memengaruhi tenant lain.

Status:

- Hold, jangan disentuh.

Keputusan manusia yang wajib sebelum mulai:

1. Master akademik platform-owned atau tenant-owned.
2. Jika platform-owned:
   - tenant admin read-only;
   - hanya `SUPER_ADMIN`/platform authority boleh mutasi.
3. Jika tenant-owned:
   - perlu migration `tenant_id`;
   - backfill;
   - unique/index per tenant;
   - update seluruh read/write path.
4. Rollout dan rollback migration.

Recommended first step nanti:

- Dependency inventory khusus master akademik.
- Spec terpisah.
- Characterization tests dua tenant.
- Baru setelah itu implementation/migration plan.

## Other Open Hardening Items

### Active Role Semantics

Finding asal:

- Active role belum menjadi authorization boundary.

Status:

- Belum diputuskan.

Decision needed:

- Active role hanya UI/dashboard context, atau harus membatasi authorization selama session.

Recommendation:

- Jika hanya UI context, dokumentasikan jelas.
- Jika authorization boundary, buat task terpisah karena akan mengubah decorator web/mobile dan multi-role behavior.

### Refresh Token Rotation Race Window

Finding asal:

- Refresh token rotation punya race window.

Status:

- Belum dimulai.

Recommendation:

- Jadikan task eksplisit `AUTH-REFRESH-006`.
- Jika tetap token stateless + revocation list, buat hardening terpisah untuk consume operation yang atomik.
- Jika memilih server-side refresh session/JTI, siapkan migration dan rollout terpisah.

### Tenant Resolver Fallback

Finding asal:

- `resolve_tenant_id()` punya fallback default yang bisa fail-open untuk caller tertentu.

Status:

- Belum dimulai.

Recommendation:

- Inventarisasi caller authenticated/privileged.
- Tambahkan `fallback_default=False` secara bertahap pada flow yang harus fail-closed.

### Soft-Delete Contract

Finding asal:

- `include_deleted=True` adalah bypass global.
- Tidak semua model mengikuti `BaseModel` soft-delete contract.

Status:

- Belum dimulai.

Recommendation:

- Dokumentasikan model yang soft-delete vs immutable/system-state.
- Tambahkan review rule agar route biasa tidak memakai `include_deleted=True`.

## Recommended Next Sequence

1. `AUTH-REFRESH-006` analysis + test plan only.
2. Active-role semantics decision, jika dibutuhkan sebagai security boundary.
3. Tenant resolver fallback hardening.
4. Soft-delete contract documentation/review rule.
5. `AUTH-PACKAGE-003` Phase 2 untuk add-on/capability lanjutan, setelah data lisensi siap.
6. `TENANT-DATA-006` hanya setelah ownership master akademik diputuskan.

## Current Release Notes

- AUTH-RATE-004 sudah deploy dan smoke-tested aman oleh human operator.
- AUTH-TOKEN-005 Phase 1 sudah deploy, migration `af56gh78ij90` applied, dan post-deploy verification passed.
- Tidak ada migration baru pada AUTH-PACKAGE-003 Phase 1 atau AUTH-RATE-004 Phase 1.
- Strict mobile token cutover sudah aktif; token mobile lama tanpa `ver` ditolak dan user mobile mungkin perlu login ulang.
- Known full-suite failure finance masih out of scope dan perlu ditangani dalam task finance terpisah.
- Jangan deploy/migration untuk item berikutnya tanpa gate baru.
