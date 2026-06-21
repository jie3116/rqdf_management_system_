# Platform Tenant Script Review

Tanggal: 2026-06-21  
Mode: read-only review  
Agents: Security Reviewer Agent, Deployment & Release Agent  
Scope:

- `app/scripts/prepare_platform_tenant.py`
- `docs/agentic/platform_tenant_migration_runbook.md`
- `reviews/platform_tenant_inventory.md`

## 1. Executive Summary

Script `prepare_platform_tenant.py` sudah memiliki baseline safety yang baik:

- mendukung mode eksplisit `--dry-run` dan `--apply`;
- `--dry-run` tidak commit;
- `--apply` dibungkus transaction dengan rollback pada exception;
- menolak lebih dari satu `SUPER_ADMIN`;
- menolak konflik slug/code jika `slug = "platform"` dan `code = "PLATFORM"` dimiliki tenant berbeda;
- tidak memindahkan user lain selain target `superadmin`;
- mencetak summary sebelum dan sesudah;
- idempotent untuk happy path setelah platform tenant dan perpindahan user selesai.

Namun untuk production, saya belum merekomendasikan langsung menjalankan `--apply` sebelum beberapa hardening kecil dilakukan.

Temuan paling penting:

1. Script dapat menghidupkan kembali tenant platform yang soft-deleted karena `_find_platform_tenant()` memakai `include_deleted=True`, lalu `--apply` mengubah `platform_tenant.is_deleted = False`.
2. Script dapat mempromosikan user bernama `superadmin` menjadi `SUPER_ADMIN` jika belum ada `SUPER_ADMIN` existing.
3. Script belum mengunci target user berdasarkan ID hasil inventory (`user_id=61`), sehingga risiko salah user lebih besar jika ada environment/data berbeda.
4. Runbook rollback tersedia, tetapi sebaiknya menyimpan `original_tenant_id` dari dry-run output sebagai artefak wajib sebelum apply.

Keputusan review: **REQUEST CHANGES sebelum production apply**. Perubahan yang dibutuhkan kecil dan tidak memerlukan migration.

## 2. Security Findings

### MEDIUM-01 — Soft-deleted platform tenant dapat direaktivasi otomatis

**File terkait**

- `app/scripts/prepare_platform_tenant.py`
- Fungsi: `_find_platform_tenant()`
- Apply block: `platform_tenant.is_deleted = False`

**Evidence**

Script mencari tenant platform dengan:

```text
execution_options(include_deleted=True)
```

Jika tenant dengan slug/code platform ditemukan walaupun soft-deleted, apply block akan menjalankan:

```text
platform_tenant.status = TenantStatus.ACTIVE
platform_tenant.is_deleted = False
```

**Risiko**

Ini bisa menghidupkan kembali tenant yang sebelumnya sengaja dihapus/diarsipkan tanpa decision gate eksplisit. Untuk production, resurrect soft-deleted row adalah perubahan data sensitif dan bisa membawa data/relationship lama yang tidak diharapkan.

**Rekomendasi**

Fail closed jika platform tenant ditemukan dalam kondisi `is_deleted=True`, kecuali ada flag eksplisit seperti `--reuse-soft-deleted-platform-tenant` dan approval manusia.

Untuk tahap sekarang, rekomendasi paling aman:

```text
Jika tenant platform soft-deleted ditemukan, script harus berhenti dan meminta manual review.
```

### MEDIUM-02 — Script dapat mempromosikan username `superadmin` menjadi SUPER_ADMIN

**File terkait**

- `app/scripts/prepare_platform_tenant.py`
- Planned action: `set_user_primary_role_super_admin`
- Apply block: `target_user.role = UserRole.SUPER_ADMIN`

**Evidence**

Jika tidak ada `SUPER_ADMIN` existing, script tetap menerima user dengan username `superadmin`, lalu mengubah primary role menjadi `SUPER_ADMIN`.

**Risiko**

Pada environment yang salah atau data yang tidak sesuai inventory, user biasa bernama `superadmin` dapat dipromosikan menjadi platform super admin. Memang butuh akses menjalankan script `--apply`, tetapi untuk administrative production script, ini tetap terlalu permisif.

**Rekomendasi**

Untuk migration dari inventory saat ini, script sebaiknya fail closed jika target user belum memiliki role `SUPER_ADMIN`.

Alternatif jika promosi memang dibutuhkan:

- require flag eksplisit `--allow-promote-superadmin`;
- print warning;
- require target user ID;
- dokumentasikan approval.

### LOW-01 — Target user tidak dikunci ke user ID hasil inventory

**File terkait**

- `app/scripts/prepare_platform_tenant.py`
- Argument: `--superadmin-username`

**Evidence**

Script default mencari target berdasarkan username `superadmin`. Inventory menunjukkan user target:

```text
user_id = 61
username = superadmin
email = superadmin@local.test
tenant_id = 1
```

**Risiko**

Jika script dijalankan pada environment berbeda, database restore yang tidak sesuai, atau ada perubahan username/user, script bisa menarget user yang tidak sama dengan hasil inventory.

**Rekomendasi**

Tambahkan optional guard:

```text
--expected-user-id 61
```

Untuk production run pertama, gunakan guard tersebut agar script berhenti jika target user tidak sesuai inventory.

### LOW-02 — Summary mencetak email user

**File terkait**

- `_print_user_summary()`

**Risiko**

Email bukan secret, tetapi tetap PII. Output script kemungkinan masuk log terminal/deployment.

**Rekomendasi**

Masih acceptable untuk run administratif, tetapi runbook perlu menyatakan agar output disimpan sebagai artefak internal terbatas. Jika ingin lebih ketat, masking email bisa dipertimbangkan.

## 3. Deployment Findings

### MEDIUM-03 — Rollback plan ada, tetapi perlu capture artefak wajib sebelum apply

**File terkait**

- `docs/agentic/platform_tenant_migration_runbook.md`

**Evidence**

Runbook sudah mencantumkan rollback manual:

```sql
UPDATE users
SET tenant_id = 1
WHERE username = 'superadmin';
```

**Risiko**

Rollback bergantung pada asumsi inventory awal bahwa tenant lama ID `1`. Jika data berubah sebelum apply, operator bisa rollback ke tenant yang salah.

**Rekomendasi**

Sebelum `--apply`, wajib capture:

- output `--dry-run`;
- `user_id`;
- `original_tenant_id`;
- `original_tenant_slug`;
- `original_tenant_code`;
- timestamp backup.

Rollback SQL harus memakai `user_id`, bukan username saja:

```sql
UPDATE users
SET tenant_id = <original_tenant_id>
WHERE id = <superadmin_user_id>;
```

### LOW-03 — Script belum membuat AppConfig default untuk platform tenant

**File terkait**

- `app/scripts/prepare_platform_tenant.py`

**Evidence**

Script hanya membuat row `Tenant`. Tidak membuat `AppConfig` seperti module package atau branding.

**Risiko**

Untuk login/dashboard super admin saat ini kemungkinan aman karena banyak config fallback ke default. Namun jika halaman memakai branding/package current tenant, platform tenant tanpa config bisa menghasilkan tampilan default atau edge case minor.

**Rekomendasi**

Tidak wajib untuk migration awal. Setelah apply, smoke test harus memverifikasi:

- login superadmin;
- dashboard/platform tenants page;
- tidak ada error context processor.

Jika ada error, tambahkan AppConfig minimal pada patch terpisah atau follow-up script.

### LOW-04 — Tidak ada advisory lock/concurrency guard

**File terkait**

- `app/scripts/prepare_platform_tenant.py`

**Risiko**

Dua operator menjalankan `--apply` bersamaan dapat race saat membuat tenant platform. Unique constraint pada `slug`/`code` kemungkinan akan menggagalkan salah satu transaksi, tetapi error-nya mungkin tidak clean.

**Rekomendasi**

Operationally acceptable jika dijalankan manual satu kali dalam maintenance window. Untuk hardening, bisa ditambahkan lock database/advisory lock atau dokumentasi “single operator only”.

## 4. Idempotency Review

### Happy path idempotency

Jika script sudah pernah sukses:

- platform tenant sudah ada;
- `superadmin` sudah berada pada tenant platform;
- role primary sudah `SUPER_ADMIN`;
- tidak ada user non-`SUPER_ADMIN` di platform tenant.

Maka dry-run berikutnya akan menghasilkan planned actions:

```text
none
```

Ini memenuhi idempotency dasar.

### Edge cases

| Scenario | Behavior saat ini | Review |
|---|---|---|
| Platform tenant belum ada | Akan dibuat saat `--apply` | OK |
| Platform tenant sudah ada active | Dipakai ulang | OK |
| Platform tenant suspended/archived | Diubah ke ACTIVE | Perlu approval; acceptable jika tenant memang platform |
| Platform tenant soft-deleted | Diaktifkan kembali | Kurang aman; sebaiknya fail closed |
| `superadmin` sudah di platform tenant | No-op untuk move | OK |
| Lebih dari satu SUPER_ADMIN | Script berhenti | OK |
| User target belum SUPER_ADMIN | Dipromosikan | Kurang aman untuk production |
| Platform tenant berisi user non-SUPER_ADMIN | Script berhenti | OK |

Kesimpulan: script idempotent untuk happy path, tetapi edge case soft-deleted platform tenant dan role promotion perlu diperketat.

## 5. Production Safety Review

### Hal yang sudah aman

- Tidak ada schema migration.
- Tidak ada perubahan login policy.
- Tidak ada perubahan `before_request`.
- Tidak memindahkan user lain.
- Menolak multiple `SUPER_ADMIN`.
- Menolak slug/code conflict.
- Menggunakan transaction commit/rollback.
- Runbook mewajibkan backup dan dry-run.

### Hal yang belum cukup aman

- Bisa revive soft-deleted tenant.
- Bisa promote user menjadi `SUPER_ADMIN`.
- Belum ada `expected-user-id` guard.
- Rollback masih memakai contoh username, lebih baik memakai immutable `user_id`.

## 6. Bisa Mengunci SUPER_ADMIN?

### Risiko lockout saat ini

Rendah sampai sedang.

Alasan risiko rendah:

- Current login policy masih memberi bypass untuk `SUPER_ADMIN`.
- Script membuat platform tenant `ACTIVE`.
- Enforcement platform tenant belum diaktifkan.
- Jika migration gagal di tengah transaction, rollback dilakukan.

Alasan risiko tetap ada:

- Setelah `superadmin` dipindahkan, ada kemungkinan route/context tertentu mengasumsikan tenant memiliki config/data tertentu.
- Jika environment salah dan user target salah, akses admin bisa terganggu.
- Jika operator menjalankan apply sebelum backup/smoke test plan, rollback bisa lambat.

### Mitigasi wajib

- Dry-run dan simpan output.
- Backup DB.
- Apply hanya di maintenance window.
- Smoke test login langsung setelah apply.
- Siapkan rollback SQL berbasis `user_id` dan `original_tenant_id`.

## 7. Perubahan Data Tak Disengaja

Script saat ini berpotensi mengubah:

1. Membuat tenant baru `Platform`.
2. Mengubah status tenant platform existing menjadi `ACTIVE`.
3. Mengubah `is_deleted` tenant platform existing menjadi `False`.
4. Mengubah `target_user.role` menjadi `SUPER_ADMIN`.
5. Mengubah `target_user.tenant_id` ke tenant platform.

Nomor 1 dan 5 sesuai tujuan. Nomor 2 bisa diterima jika tenant platform existing memang valid. Nomor 3 dan 4 perlu guard tambahan sebelum production apply.

## 8. Recommended Changes Before Apply

Prioritas perubahan kecil:

1. Fail closed jika platform tenant sentinel ditemukan tetapi `is_deleted=True`.
2. Fail closed jika target user belum memiliki role `SUPER_ADMIN`, kecuali flag approval eksplisit.
3. Tambahkan `--expected-user-id` dan gunakan `61` untuk production run berdasarkan inventory.
4. Update rollback runbook agar memakai `WHERE id = <user_id>`, bukan username.
5. Tambahkan requirement menyimpan output dry-run sebagai artefak deployment.

Semua perubahan ini tidak membutuhkan migration.

## 9. Deployment Gate

Sebelum menjalankan `--apply`, gate minimum:

- [ ] Patch hardening kecil di atas selesai.
- [ ] `python -m py_compile app/scripts/prepare_platform_tenant.py` berhasil.
- [ ] `--dry-run` dijalankan dan output disimpan.
- [ ] Backup database dibuat dan tervalidasi.
- [ ] `user_id`, `original_tenant_id`, dan planned actions dikonfirmasi manusia.
- [ ] Maintenance window disepakati.
- [ ] Rollback SQL siap.
- [ ] Smoke test login `superadmin` siap dilakukan segera.

## 10. Final Recommendation

Jangan jalankan `--apply` dulu.

Script sudah mendekati aman, tetapi untuk production administrative script, saya merekomendasikan patch hardening kecil sebelum execution. Fokus patch berikutnya:

- jangan revive soft-deleted platform tenant otomatis;
- jangan promote user menjadi `SUPER_ADMIN` otomatis;
- kunci target user dengan expected ID;
- perkuat rollback instruction.
