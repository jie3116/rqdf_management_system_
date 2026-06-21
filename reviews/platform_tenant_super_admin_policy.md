# Platform Tenant & SUPER_ADMIN Policy Design Note

Tanggal: 2026-06-21  
Mode: design note only  
Scope: `SUPER_ADMIN`, platform/internal tenant, customer tenant lifecycle  
Keputusan manusia: ada satu platform/internal tenant khusus untuk akun `SUPER_ADMIN`

## 1. Executive Summary

Model `Tenant` saat ini belum memiliki field eksplisit untuk membedakan platform/internal tenant dari customer tenant.

Field yang tersedia pada `Tenant`:

- `name`
- `slug`
- `code`
- `status`
- `timezone`
- `is_default`
- field lifecycle dari `BaseModel`, termasuk `is_deleted`

Tidak ditemukan field seperti:

- `tenant_type`
- `is_platform`
- `is_internal`
- `kind`
- `category`

Karena itu, implementasi penuh policy platform tenant sebaiknya tidak dilakukan sekarang tanpa migration. Short-term masih bisa dibuat tanpa migration dengan sentinel `Tenant.slug` atau `Tenant.code`, tetapi harus diperlakukan sebagai bridge sementara, bukan model final.

Rekomendasi:

1. Short term: gunakan platform tenant berdasarkan `slug == "platform"` atau `code == "PLATFORM"` dengan helper terpusat.
2. Long term: tambah field eksplisit `tenant_type = PLATFORM/CUSTOMER` melalui migration terencana.
3. Jangan lanjut implementasi penuh sampai nama sentinel short-term dan rencana long-term disetujui.

## 2. Policy Target

Policy yang disepakati:

- `SUPER_ADMIN` hanya boleh berada di platform/internal tenant.
- Platform tenant wajib `ACTIVE`.
- Platform tenant tidak boleh di-suspend, archive, atau soft-delete melalui UI/admin route biasa.
- `SUPER_ADMIN` boleh mengelola customer tenant yang `ACTIVE`, `SUSPENDED`, atau `ARCHIVED`.
- User non-`SUPER_ADMIN` wajib berada pada customer tenant `ACTIVE`.
- Jangan membuat migration dulu kecuali sudah ada field yang mendukung tenant type/platform flag.

## 3. Current Model Analysis

### Tenant model

Evidence:

- `app/models.py`: `Tenant` memiliki `name`, `slug`, `code`, `status`, `timezone`, dan `is_default`.
- `TenantStatus` hanya berisi `ACTIVE`, `SUSPENDED`, dan `ARCHIVED`.
- `Tenant` mewarisi `BaseModel`, sehingga memiliki soft-delete field seperti `is_deleted`.

Kesimpulan:

- Belum ada field yang secara semantik menyatakan tenant sebagai platform/internal.
- `is_default` tidak cukup aman untuk dipakai sebagai platform flag karena namanya menunjukkan default/fallback tenant, bukan identity boundary.
- `slug` dan `code` bisa dipakai sebagai sentinel short-term karena unique dan sudah indexed, tetapi ini convention-based.

### Tenant admin route

Evidence:

- `app/routes/admin.py` route `/platform/tenants` hanya untuk `SUPER_ADMIN`.
- Route tersebut bisa membuat customer tenant baru.
- Route tersebut bisa update `tenant.status` dari form.
- Belum terlihat guard yang mencegah platform tenant diubah menjadi `SUSPENDED` atau `ARCHIVED`.

Risiko current behavior terhadap policy baru:

- Jika platform tenant hanya ditandai lewat `slug/code`, route admin biasa masih bisa mengubah statusnya kecuali guard eksplisit ditambahkan.
- Jika `SUPER_ADMIN` berada di customer tenant, model saat ini tidak punya cara native untuk menolak tanpa convention.
- Jika `is_default` dipakai sebagai platform marker, ada risiko tabrakan dengan kebutuhan default tenant untuk public/bootstrap flow.

## 4. Implementation Option A — Short Term Tanpa Migration

### Ide

Gunakan sentinel tenant yang sudah bisa dibedakan dari field existing:

- `slug == "platform"`; dan/atau
- `code == "PLATFORM"` atau `code == "SYSTEM"`.

Rekomendasi sentinel:

```text
slug = "platform"
code = "PLATFORM"
status = ACTIVE
is_deleted = False
```

### Helper policy yang disarankan

Tambahkan helper terpusat, misalnya di `app/utils/tenant.py`:

```text
is_platform_tenant(tenant)
is_platform_admin(user)
is_customer_tenant_active(user)
```

Semantics:

- `is_platform_tenant(tenant)` true hanya jika tenant tidak soft-deleted, status `ACTIVE`, dan slug/code sesuai sentinel.
- `is_platform_admin(user)` true hanya jika user memiliki role `SUPER_ADMIN` dan tenant user adalah platform tenant active.
- `is_customer_tenant_active(user)` true hanya jika user bukan `SUPER_ADMIN`, tenant bukan platform tenant, status `ACTIVE`, dan tidak soft-deleted.

### Enforcement point

Short-term enforcement yang direkomendasikan:

1. Web login:
   - `SUPER_ADMIN` hanya login jika `is_platform_admin(user)` true.
   - Non-`SUPER_ADMIN` login hanya jika tenant customer active.

2. Web `before_request`:
   - `SUPER_ADMIN` boleh lanjut hanya jika platform tenant active.
   - Non-`SUPER_ADMIN` wajib customer tenant active.

3. Mobile auth:
   - Jika `SUPER_ADMIN` tidak dipakai untuk mobile, tolak login mobile `SUPER_ADMIN` secara eksplisit atau ikuti policy platform tenant yang sama.

4. Admin tenant management:
   - Jika target tenant adalah platform tenant, tolak perubahan status selain `ACTIVE`.
   - Tolak soft-delete platform tenant dari route biasa.
   - Tolak pembuatan admin tenant biasa pada platform tenant kecuali flow khusus platform-admin.

### Kelebihan

- Tidak butuh migration.
- Bisa ditest dengan fixture yang sederhana.
- Menutup risiko `SUPER_ADMIN` berada di customer tenant.
- Cocok sebagai hardening bridge.

### Kekurangan

- Convention-based; keamanan bergantung pada slug/code tidak berubah.
- Sentinel harus dilindungi di semua route yang bisa mengubah `slug`, `code`, `status`, dan soft-delete.
- Tidak self-documenting di database.
- Jika data production sudah punya tenant dengan slug/code tersebut, butuh cleanup manual.

### Guardrail minimum jika Option A dipakai

- Tetapkan satu canonical sentinel saja, idealnya `slug == "platform"` dan `code == "PLATFORM"`.
- Jangan pakai `is_default` sebagai platform marker.
- Tambahkan test untuk memastikan platform tenant tidak bisa di-suspend.
- Tambahkan checklist operasional: platform tenant tidak boleh diedit manual di DB kecuali emergency procedure.

## 5. Implementation Option B — Long Term Dengan Migration

### Ide

Tambahkan field eksplisit:

```text
Tenant.tenant_type = PLATFORM | CUSTOMER
```

Alternatif:

```text
Tenant.is_platform = True/False
```

Rekomendasi: gunakan enum/string `tenant_type`, bukan boolean, karena lebih mudah diperluas jika nanti ada tenant internal lain seperti demo, sandbox, atau partner.

### Desain schema awal

```text
tenant_type: enum/string, nullable=False, default=CUSTOMER, indexed
```

Constraint yang ideal:

- Hanya satu tenant `PLATFORM`.
- Platform tenant harus `ACTIVE`.
- Platform tenant tidak boleh soft-deleted.

Catatan: beberapa constraint seperti “tidak boleh soft-delete” mungkin lebih realistis ditegakkan di application/service layer, bukan database constraint penuh, tergantung DB dan migration policy.

### Rollout plan

1. Add column nullable/default-safe.
2. Backfill semua existing tenant ke `CUSTOMER`.
3. Tandai satu tenant sebagai `PLATFORM`.
4. Tambahkan application guard.
5. Tambahkan test.
6. Setelah stabil, pertimbangkan stricter DB constraint.

### Kelebihan

- Semantics jelas dan eksplisit.
- Tidak bergantung pada slug/code.
- Lebih aman untuk audit dan maintenance.
- Lebih cocok untuk production multi-tenant jangka panjang.

### Kekurangan

- Butuh migration dan rollout plan.
- Butuh keputusan data production: tenant mana yang menjadi platform tenant.
- Butuh backup dan approval manusia sebelum migration production.

## 6. Test Plan

### Authentication

1. `SUPER_ADMIN` di platform tenant `ACTIVE` boleh login.
   - Given tenant platform active.
   - Given user role `SUPER_ADMIN`.
   - When login web.
   - Then redirect ke dashboard/platform area berhasil.

2. `SUPER_ADMIN` di customer tenant ditolak atau flagged.
   - Given tenant customer active.
   - Given user role `SUPER_ADMIN`.
   - When login web.
   - Then login ditolak dengan pesan generik atau user dipaksa logout.

3. `SUPER_ADMIN` di platform tenant non-active ditolak.
   - Given tenant platform `SUSPENDED` atau `ARCHIVED`.
   - When login atau existing session request.
   - Then login/session ditolak.

### Tenant lifecycle

4. Platform tenant tidak bisa disuspend dari UI/admin route biasa.
   - Given platform tenant active.
   - When POST `/platform/tenants` mencoba set status `SUSPENDED`.
   - Then request ditolak atau status tetap `ACTIVE`.

5. Platform tenant tidak bisa diarchive dari UI/admin route biasa.
   - Given platform tenant active.
   - When POST `/platform/tenants` mencoba set status `ARCHIVED`.
   - Then request ditolak atau status tetap `ACTIVE`.

6. Platform tenant tidak bisa soft-delete dari UI/admin route biasa.
   - Given platform tenant active.
   - When route delete/archive soft-delete dijalankan, jika route tersedia.
   - Then request ditolak atau `is_deleted` tetap false.

7. Customer tenant bisa disuspend.
   - Given customer tenant active.
   - When `SUPER_ADMIN` update status ke `SUSPENDED`.
   - Then status berubah menjadi `SUSPENDED`.

8. Customer tenant bisa diarchive.
   - Given customer tenant active/suspended.
   - When `SUPER_ADMIN` update status ke `ARCHIVED`.
   - Then status berubah menjadi `ARCHIVED`.

### Non-super-admin customer access

9. User customer tenant active boleh login.
   - Given user non-`SUPER_ADMIN` pada customer tenant `ACTIVE`.
   - Then login berhasil.

10. User customer tenant suspended ditolak.
    - Given user non-`SUPER_ADMIN` pada customer tenant `SUSPENDED`.
    - Then login ditolak.

11. Existing session customer tenant suspended diputus.
    - Given user non-`SUPER_ADMIN` sudah login.
    - When tenant berubah menjadi `SUSPENDED`.
    - Then request berikutnya logout dan redirect ke login.

### Regression guard

12. `SUPER_ADMIN` tetap bisa melihat dan mengelola customer tenant `SUSPENDED` dan `ARCHIVED`.
    - Given platform admin active.
    - Given customer tenant suspended/archived.
    - Then tenant tetap muncul di platform tenant management dan bisa diedit sesuai policy.

13. Non-`SUPER_ADMIN` tidak boleh berada di platform tenant.
    - Given user role `ADMIN`/`SISWA` pada platform tenant.
    - Then login ditolak atau flagged.

## 7. Recommended Implementation Sequence

### Step 1 — Approve short-term sentinel

Putuskan nilai final:

```text
PLATFORM_TENANT_SLUG = "platform"
PLATFORM_TENANT_CODE = "PLATFORM"
```

Jika production sudah memiliki tenant dengan slug/code tersebut, lakukan keputusan data manual dulu.

### Step 2 — Add policy helper tanpa migration

Buat helper terpusat agar tidak menyebar logic string sentinel:

```text
is_platform_tenant(tenant)
is_platform_admin(user)
is_customer_tenant_active(user)
```

### Step 3 — Add tests first

Tambahkan test di file terpisah, misalnya:

```text
tests/test_platform_tenant_super_admin_policy.py
```

### Step 4 — Patch minimal

Patch hanya area:

- web login;
- web request guard;
- tenant management status update;
- mobile auth jika `SUPER_ADMIN` bisa memakai API mobile.

### Step 5 — Long-term spec untuk migration

Buat spec terpisah sebelum migration:

```text
specs/platform_tenant_type_migration.md
```

Jangan gabungkan migration tenant type dengan remediation auth lain.

## 8. Recommendation

Rekomendasi engineering:

1. Jangan implementasi penuh sekarang karena model belum punya platform/internal tenant field eksplisit.
2. Jika hardening diperlukan segera, ambil Option A dengan sentinel `slug/code`, tetapi buat helper policy terpusat dan test dulu.
3. Treat Option A sebagai temporary compatibility layer.
4. Target final tetap Option B: `tenant_type = PLATFORM/CUSTOMER` dengan migration terencana.
5. Jangan pakai `is_default` sebagai platform marker.

## 9. Human Decisions Still Required

1. Nama final platform tenant:
   - `slug = "platform"` atau `slug = "system"`?
   - `code = "PLATFORM"` atau `code = "SYSTEM"`?

2. Apakah `SUPER_ADMIN` boleh login mobile?
   - Jika tidak, tolak eksplisit.
   - Jika ya, pakai policy platform tenant yang sama.

3. Bagaimana menangani existing `SUPER_ADMIN` yang sekarang berada di customer tenant?
   - Tolak login langsung?
   - Flag audit dulu?
   - Migrasikan manual ke platform tenant?

4. Apakah platform tenant dibuat/ditandai manual di production sebelum patch?

5. Kapan migration long-term `tenant_type` akan dijadwalkan?
