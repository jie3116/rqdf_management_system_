# AUTH/RBAC/Tenant Remediation Changelog

Tanggal dibuat: 2026-06-26

Scope changelog:

- Authentication hardening
- Tenant lifecycle enforcement
- Platform tenant / `SUPER_ADMIN` separation
- Mobile package/capability enforcement
- Login rate limiting

Dokumen ini adalah changelog remediation security, bukan changelog produk umum.

## 2026-06-28

### Added

- Menambahkan artifact `AUTH-TOKEN-005 Phase 1`:
  - `reviews/auth-token-005/auth_token_005_impact_analysis.md`
  - `reviews/auth-token-005/auth_token_005_verification_gate.md`
  - `reviews/auth-token-005/auth_token_005_phase1_code_review.md`
  - `reviews/auth-token-005/auth_token_005_migration_deploy_gate.md`
  - `reviews/auth-token-005/auth_token_005_post_deploy_verification.md`

### Implemented

- `AUTH-TOKEN-005 Phase 1` diterapkan untuk invalidasi mobile token setelah password existing user diubah/reset.
- Migration menambahkan `users.token_version INTEGER NOT NULL DEFAULT 0`.
- Mobile access dan refresh token baru membawa claim `ver`.
- Mobile access/refresh token lama, stale, atau tanpa `ver` ditolak dengan controlled `401 unauthorized`.
- Existing-user password mutation flow dipusatkan lewat credential security service.
- Logout tetap menggunakan `MobileRevokedToken`.

### Production Verification

- Production migration berhasil:
  - `ae45fg67hi89 -> af56gh78ij90, add user token version`
- Production Alembic current/head:
  - `af56gh78ij90 (head)`
- Production schema verified:
  - `token_version integer NOT NULL default 0`
- Backup sebelum deploy:
  - `backups/pre_deploy_2026-06-28_140722.dump`
  - verified with `pg_restore -l`
- Post-deploy verification:
  - `POST-DEPLOY VERIFICATION PASSED`

### Decisions

- Strict cutover diterima; token mobile lama tanpa `ver` ditolak.
- Mobile users mungkin perlu login ulang.
- `AUTH-REFRESH-006` tetap backlog terpisah karena refresh rotation race belum diselesaikan oleh token version.

### Documentation

- Status roll-up diperbarui agar `AUTH-TOKEN-005 Phase 1` tercatat done/deployed/post-deploy passed.
- Recommended next work digeser ke `AUTH-REFRESH-006` analysis + test plan only atau active-role semantics decision.

## 2026-06-26

### Added

- Membuat status roll-up remediation:
  - `reviews/auth-rbac-tenant/auth_rbac_tenant_remediation_status.md`
- Menandai `AUTH-RATE-004 Phase 1` sebagai:
  - implemented;
  - review gate approved;
  - deployed by human operator;
  - smoke-tested aman berdasarkan konfirmasi human operator.

### Confirmed

- `AUTH-RATE-004 Phase 1` memakai existing `MobileRateLimitBucket`.
- Tidak ada migration baru untuk `AUTH-RATE-004`.
- Tidak ada perubahan ProxyFix/trusted proxy.
- Tidak ada perubahan Nginx rate limit.
- Mobile login memakai HTTP `429` untuk rate-limited request.
- Web login memakai flash message dan render login seperti biasa.
- Identifier, tenant hint, dan IP-derived scope tidak disimpan sebagai PII mentah dalam bucket key.

### Known Issues

- Full test suite terakhir masih memiliki 1 failure di finance:
  - `tests/test_finance_core.py::test_reverse_journal_creates_opposite_lines_and_voids_cash_bank_source`
- Root cause yang tercatat:
  - `reverse_journal()` memakai `date.today()`;
  - fixture finance tidak membuat accounting period untuk tanggal eksekusi test.
- Status:
  - out of scope untuk AUTH/RBAC/Tenant remediation saat ini;
  - jangan diperbaiki sebagai bagian dari auth remediation tanpa task finance terpisah.

## 2026-06-22

### Added

- Membuat verification gate untuk `AUTH-RATE-004`:
  - `reviews/auth-rate-004/auth_rate_004_verification_gate.md`

### Verified

- Migration `m3b4c5d6e7f8_add_mobile_auth_state_tables.py` ada dalam codebase dan tersambung dalam migration graph.
- Model `MobileRateLimitBucket` tersedia dan field-nya sesuai kebutuhan fixed-window rate limiting:
  - `bucket_key`
  - `action_name`
  - `scope_key`
  - `count`
  - `window_ends_at`
  - `created_at`
  - `updated_at`
- Tidak ditemukan helper rate-limit existing yang aktif.
- Untuk Phase 1, `request.remote_addr` dipakai sebagai sumber IP karena trusted proxy handling belum dikonfigurasi di aplikasi.

### Decision

- `AUTH-RATE-004 Verification Gate`: `APPROVED`.
- `MobileRateLimitBucket` boleh dipakai ulang untuk web dan mobile login.
- Tidak perlu migration baru untuk Phase 1 jika DB target sudah memiliki migration existing.

## 2026-06-21

### Added

- Membuat analysis untuk `AUTH-PACKAGE-003`:
  - `reviews/auth-package-003/auth_package_003_impact_analysis.md`
- Membuat capability design v2:
  - `reviews/auth-package-003/package_capability_matrix_v2.md`
- Membuat review gate awal untuk `AUTH-PACKAGE-003 Phase 1`:
  - `reviews/auth-package-003/auth_package_003_phase1_review.md`
- Membuat analysis untuk `AUTH-RATE-004`:
  - `reviews/auth-rate-004/auth_rate_004_impact_analysis.md`
- Membuat platform tenant artefak:
  - `reviews/platform-tenant/platform_tenant_super_admin_policy.md`
  - `reviews/platform-tenant/platform_tenant_inventory.md`
  - `reviews/platform-tenant/platform_tenant_script_review.md`

### Changed

- Desain package authorization diarahkan dari legacy package name ke capability-based model:
  - `tenant_has_capability(tenant, capability)`
- Mapping bisnis target ditetapkan:
  - `QURAN`
  - `SCHOOL`
  - `BOARDING`
  - `INTEGRATED`
- Add-on target didefinisikan:
  - `FINANCE`
  - `PPDB`
  - `ONLINE_CLASS`
  - `AI_ASSISTANT`

### Implemented

- `AUTH-PACKAGE-003 Phase 1` diterapkan untuk mobile API capability yang jelas:
  - `teacher`
  - `boarding`
  - `majlis`

### Compatibility Decisions

- Legacy `full` diperlakukan sebagai `INTEGRATED` adapter.
- Legacy `sekolah` diperlakukan sebagai `SCHOOL` adapter.
- Legacy `rumah_quran` diperlakukan sebagai `QURAN` adapter.
- Scope Phase 1 tidak menyentuh:
  - parent mixed endpoints;
  - finance;
  - PPDB;
  - online class;
  - AI assistant;
  - analytics;
  - announcement.

### Review Findings

- Review awal `AUTH-PACKAGE-003 Phase 1` menemukan blocker:
  - `tenant_has_capability(None, capability)` belum fail-closed.
- Minimum fix yang kemudian disepakati:
  - `tenant_has_capability(None, CAPABILITY_TEACHER) is False`
  - `tenant_has_capability(None, CAPABILITY_BOARDING) is False`
  - `tenant_has_capability(None, CAPABILITY_MAJLIS) is False`

### Confirmed Later

- Berdasarkan proses remediation setelah review awal, blocker `tenant_id=None` diperbaiki dan Phase 1 dinyatakan selesai.
- Catatan audit trail:
  - file `reviews/auth-package-003/auth_package_003_phase1_review.md` masih menyimpan review awal `REQUEST CHANGES`;
  - status roll-up terbaru ada di `reviews/auth-rbac-tenant/auth_rbac_tenant_remediation_status.md`.

## 2026-06-19

### Added

- Membuat audit awal:
  - `reviews/auth-rbac-tenant/auth_rbac_tenant_audit.md`
- Membuat backlog remediation:
  - `reviews/auth-rbac-tenant/auth_rbac_tenant_remediation_backlog.md`
- Membuat test plan `AUTH-TENANT-001`:
  - `reviews/auth-tenant/auth_tenant_001_test_plan.md`

### Findings

- `HIGH-01`: Mobile authentication menerima user dari tenant nonaktif.
- `HIGH-02`: Existing web session tetap aktif setelah tenant disuspensi.
- `HIGH-03`: Tenant package/module restriction tidak diterapkan pada mobile API.
- `HIGH-04`: Master akademik global memungkinkan dampak lintas tenant.
- `MEDIUM-02`: Login web/mobile belum terlihat memiliki application-level rate limiting.
- `MEDIUM-03`: Password change/reset tidak membatalkan mobile token existing.

### Backlog Created

Urutan remediation awal:

1. `AUTH-TENANT-001`
2. `AUTH-TENANT-002`
3. `AUTH-PACKAGE-003`
4. `AUTH-RATE-004`
5. `AUTH-TOKEN-005`
6. `TENANT-DATA-006`

## Current Status Snapshot

Selesai:

- `AUTH-TENANT-001`
- `AUTH-TENANT-002`
- Platform tenant / `SUPER_ADMIN` separation
- `AUTH-PACKAGE-003 Phase 1`
- `AUTH-RATE-004 Phase 1`
- `AUTH-TOKEN-005 Phase 1`

Hold:

- `TENANT-DATA-006`

Open hardening:

- Active-role semantics.
- `AUTH-REFRESH-006` / refresh-token rotation race window.
- Tenant resolver fallback behavior.
- Soft-delete contract and `include_deleted=True` usage policy.
- AUTH-PACKAGE add-on enforcement Phase 2.

## Next Recommended Work

1. Mulai `AUTH-REFRESH-006` dengan analysis + test plan only.
2. Putuskan active-role semantics jika active role akan dijadikan authorization boundary.
3. Jangan membuat migration sebelum verification/design gate.
4. Jangan menyentuh `TENANT-DATA-006` sampai ownership master akademik diputuskan.
5. Lanjutkan `AUTH-PACKAGE-003` Phase 2 hanya setelah data lisensi add-on siap.
