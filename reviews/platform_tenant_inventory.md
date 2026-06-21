# Platform Tenant Inventory

Tanggal: 2026-06-21  
Mode: read-only data inventory  
Sumber policy: `reviews/platform_tenant_super_admin_policy.md`  
Database scope: database yang dikonfigurasi oleh environment lokal saat inventory dijalankan

## 1. Executive Summary

Inventory menemukan 1 akun `SUPER_ADMIN`:

- username: `superadmin`
- email: `superadmin@local.test`
- tenant: `RQDF`
- tenant slug/code: `default` / `DEFAULT`
- tenant status: `ACTIVE`

Tenant tersebut bukan platform tenant berdasarkan sentinel short-term yang direkomendasikan (`slug = "platform"`, `code = "PLATFORM"`). Tenant yang sama juga berisi 54 user non-`SUPER_ADMIN`.

Tidak ditemukan tenant dengan:

- `slug = "platform"`
- `slug = "system"`
- `code = "PLATFORM"`
- `code = "SYSTEM"`

Kesimpulan: platform tenant belum ada. `SUPER_ADMIN` saat ini masih berada di tenant customer/default yang juga dipakai user operasional. Implementasi policy `SUPER_ADMIN` platform tenant tidak boleh langsung diaktifkan tanpa langkah migrasi data.

## 2. SUPER_ADMIN Accounts

| User ID | Username | Email | Primary Role | User Deleted | Tenant ID | Tenant Name | Tenant Slug | Tenant Code | Tenant Status | Tenant Default | Tenant Deleted |
|---:|---|---|---|---|---:|---|---|---|---|---|---|
| 61 | `superadmin` | `superadmin@local.test` | `SUPER_ADMIN` | `False` | 1 | `RQDF` | `default` | `DEFAULT` | `ACTIVE` | `True` | `False` |

Catatan:

- Query mencari `SUPER_ADMIN` dari `users.role` dan `user_role_assignments.role`.
- Tidak ditemukan `SUPER_ADMIN` tambahan dari role assignment.

## 3. Tenant User Count

Tenant yang berisi akun `SUPER_ADMIN`:

| Tenant ID | Tenant Name | Total Users | SUPER_ADMIN Users | Non-SUPER_ADMIN Users | Deleted Users |
|---:|---|---:|---:|---:|---:|
| 1 | `RQDF` | 55 | 1 | 54 | 0 |

Distribusi primary role pada tenant `RQDF`:

| Role | User Count |
|---|---:|
| `ADMIN` | 1 |
| `GURU` | 6 |
| `SISWA` | 22 |
| `WALI_MURID` | 18 |
| `TU` | 2 |
| `MAJLIS_PARTICIPANT` | 3 |
| `WALI_ASRAMA` | 1 |
| `SUPER_ADMIN` | 1 |
| `PIMPINAN` | 1 |

## 4. Platform Tenant Availability

Candidate lookup:

| Sentinel | Result |
|---|---|
| `slug = "platform"` | Tidak ada |
| `code = "PLATFORM"` | Tidak ada |
| `slug = "system"` | Tidak ada |
| `code = "SYSTEM"` | Tidak ada |

Analisis:

- Sentinel `platform` / `PLATFORM` masih tersedia pada database yang diperiksa.
- Sentinel `system` / `SYSTEM` juga masih tersedia.
- Karena `Tenant.slug` dan `Tenant.code` unique, tidak ada konflik langsung untuk membuat platform tenant dengan sentinel tersebut nanti.

## 5. Risiko Konflik Data

### Risiko 1 — SUPER_ADMIN berada di customer/default tenant

Current state:

- `SUPER_ADMIN` berada pada tenant `RQDF/default/DEFAULT`.
- Tenant ini juga memiliki 54 user non-`SUPER_ADMIN`.
- Tenant ini terlihat sebagai tenant operasional/customer, bukan platform/internal.

Risiko:

- Jika policy baru langsung menolak `SUPER_ADMIN` di customer tenant, akun `superadmin` akan terkunci.
- Jika tenant `RQDF` suatu saat disuspend/archived sebagai customer tenant, akses platform admin ikut terpengaruh.
- Jika tenant `RQDF` diperlakukan sebagai platform tenant, 54 user customer lain akan ikut berada di platform tenant, melanggar policy.

### Risiko 2 — `is_default=True` tidak boleh dipakai sebagai platform marker

Current state:

- Tenant `RQDF` memiliki `is_default=True`.

Risiko:

- `is_default` kemungkinan dipakai untuk fallback/default public flow.
- Menganggap `is_default` sebagai platform marker akan salah mengklasifikasikan tenant customer/default sebagai platform tenant.

### Risiko 3 — Tidak ada platform tenant existing

Current state:

- Tidak ditemukan tenant `platform` atau `system`.

Risiko:

- Tidak ada target tenant aman untuk memindahkan akun `SUPER_ADMIN`.
- Implementasi helper `is_platform_admin(user)` dengan sentinel akan menolak semua `SUPER_ADMIN` sampai platform tenant dibuat dan akun dipindahkan.

### Risiko 4 — Migration tanpa staging bisa memutus akses admin

Risiko:

- Jika enforcement login dilakukan sebelum data `SUPER_ADMIN` dipindahkan, akses platform tenant management bisa hilang.
- Karena route pembuatan tenant platform juga membutuhkan `SUPER_ADMIN`, sequencing harus dirancang hati-hati.

## 6. Rekomendasi Langkah Migrasi

### Rekomendasi short-term tanpa migration

1. Approve sentinel final:
   - `slug = "platform"`
   - `code = "PLATFORM"`

2. Buat platform tenant secara manual/administratif melalui flow yang disetujui manusia.
   - Status wajib `ACTIVE`.
   - `is_deleted=False`.
   - Jangan jadikan tenant ini customer/default tenant.

3. Pindahkan akun `superadmin` dari tenant `RQDF` ke tenant platform.
   - Ini perubahan data, bukan migration schema.
   - Harus dilakukan dengan backup dan approval manusia.
   - Pastikan akun `superadmin` tetap role `SUPER_ADMIN`.

4. Pastikan tidak ada user non-`SUPER_ADMIN` di platform tenant.
   - Jika ada, pindahkan atau tolak sebelum enforcement policy.

5. Baru setelah data siap, implementasikan helper policy:
   - `is_platform_tenant(tenant)`
   - `is_platform_admin(user)`
   - `is_customer_tenant_active(user)`

6. Baru setelah test pass, aktifkan enforcement:
   - web login;
   - web request guard;
   - tenant management guard agar platform tenant tidak bisa disuspend/archive;
   - mobile auth jika `SUPER_ADMIN` diizinkan memakai API mobile.

### Rekomendasi long-term dengan migration

1. Buat spec migration terpisah:
   - `specs/platform_tenant_type_migration.md`

2. Tambahkan field eksplisit:
   - `tenant_type = PLATFORM/CUSTOMER`

3. Backfill:
   - semua tenant existing menjadi `CUSTOMER`;
   - satu tenant platform menjadi `PLATFORM`.

4. Tambahkan guard application-level:
   - hanya satu platform tenant;
   - platform tenant wajib active;
   - platform tenant tidak bisa disuspend/archive/soft-delete melalui UI/admin route biasa.

5. Tambahkan test platform tenant policy sebelum migration production.

## 7. Recommended Sequencing

Urutan aman:

1. Freeze keputusan sentinel: `platform` / `PLATFORM`.
2. Buat atau identifikasi platform tenant dengan approval manusia.
3. Backup database.
4. Pindahkan akun `superadmin` ke platform tenant.
5. Verifikasi `superadmin` bisa login.
6. Verifikasi tenant platform hanya berisi `SUPER_ADMIN`.
7. Tambahkan test policy.
8. Implementasi policy helper.
9. Implementasi guard login/session/tenant-management.
10. Rencanakan migration `tenant_type` sebagai fase terpisah.

## 8. Human Decisions Required

1. Apakah sentinel final disetujui sebagai:
   - `slug = "platform"`
   - `code = "PLATFORM"`

2. Apakah platform tenant akan dibuat lewat UI `/platform/tenants`, script administratif, atau SQL manual dengan approval?

3. Apakah akun `superadmin` existing akan dipindahkan ke platform tenant atau dibuat akun platform super admin baru?

4. Apakah `SUPER_ADMIN` boleh login mobile?

5. Apakah tenant `RQDF/default/DEFAULT` tetap menjadi customer/default tenant setelah `SUPER_ADMIN` dipindahkan?

## 9. Inventory Query Evidence

Read-only query result summary:

```text
SUPER_ADMIN accounts: 1
Platform/system sentinel tenants: 0
SUPER_ADMIN tenant total users: 55
SUPER_ADMIN tenant non-super-admin users: 54
Deleted users in SUPER_ADMIN tenant: 0
```

No code, migration, tenant creation, data update, or login policy change was performed.
