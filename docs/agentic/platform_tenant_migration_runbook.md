# Platform Tenant Migration Runbook

Tanggal: 2026-06-21  
Scope: menyiapkan tenant platform/internal dan memindahkan akun `superadmin`  
Script: `app/scripts/prepare_platform_tenant.py`  
Mode wajib: mulai dari `--dry-run`, catat `target user_id`, lalu `--apply --expected-user-id <id>` hanya setelah approval manusia

## 1. Tujuan

Runbook ini menyiapkan desain short-term tanpa migration:

```text
PLATFORM_TENANT_SLUG = "platform"
PLATFORM_TENANT_CODE = "PLATFORM"
```

Target hasil:

- tenant platform tersedia dengan status `ACTIVE`;
- akun `superadmin` berada di tenant platform;
- role `superadmin` adalah `SUPER_ADMIN`;
- user lain tidak dipindahkan;
- tenant customer/default existing tetap berisi user operasional;
- login policy dan `before_request` belum diubah.

## 2. Safety Rules

Jangan lanjut jika salah satu kondisi ini terjadi:

- belum ada backup database;
- dry-run menunjukkan lebih dari satu `SUPER_ADMIN`;
- dry-run menunjukkan konflik `slug = "platform"` dan `code = "PLATFORM"`;
- dry-run menunjukkan platform tenant existing berisi user non-`SUPER_ADMIN`;
- belum ada approval manusia untuk `--apply`;
- `--apply` tidak memakai `--expected-user-id` dari output dry-run;
- environment database tidak jelas.

Script ini tidak menjalankan migration dan tidak mengubah schema.

## 3. Backup Database

Sebelum `--apply`, ambil backup database production.

Contoh PostgreSQL:

```powershell
pg_dump --format=custom --file rqdf_before_platform_tenant.dump "<DATABASE_URL>"
```

Jika backup dilakukan dari server production, gunakan mekanisme backup standar environment tersebut. Simpan informasi berikut:

- waktu backup;
- database host/name;
- operator;
- lokasi file backup;
- ukuran file backup;
- hasil verifikasi backup dapat dibaca.

Jangan lanjut ke `--apply` jika backup belum tervalidasi.

## 4. Dry Run

Jalankan dari root repository:

```powershell
.\.venv\Scripts\python.exe app\scripts\prepare_platform_tenant.py --dry-run
```

Opsional jika username berbeda:

```powershell
.\.venv\Scripts\python.exe app\scripts\prepare_platform_tenant.py --dry-run --superadmin-username superadmin
```

Expected output untuk state saat ini:

- mode `DRY-RUN`;
- target platform tenant `slug='platform'`, `code='PLATFORM'`;
- target user `superadmin`;
- target user summary menampilkan `user_id`, `username`, `email`, tenant lama, dan planned actions;
- before summary menunjukkan `superadmin` masih di tenant customer/default;
- planned actions berisi:
  - `create_platform_tenant`;
  - `move_superadmin_to_platform_tenant`;
- tidak ada commit.

Simpan output dry-run sebagai artefak deployment. Minimal catat:

- `target_user.user_id`;
- `target_user.username`;
- `target_user.email`;
- `target_user.tenant_id` sebelum apply;
- `current_user_tenant.slug`;
- `current_user_tenant.code`;
- planned actions.

Jika dry-run gagal, jangan jalankan `--apply`. Selesaikan penyebabnya secara manual dan dokumentasikan di `reviews/`.

## 5. Execute Apply

Hanya jalankan setelah:

- dry-run sudah dicek;
- target `user_id` dari dry-run sudah dicatat;
- backup sudah tersedia;
- approval manusia eksplisit diberikan;
- maintenance window atau waktu aman sudah disepakati.

Command:

```powershell
.\.venv\Scripts\python.exe app\scripts\prepare_platform_tenant.py --apply --expected-user-id <id-dari-dry-run>
```

Untuk inventory saat dokumen ini dibuat, `user_id` hasil inventory adalah `61`. Tetap gunakan ID dari dry-run terbaru jika data berubah sebelum execution.

Script akan menolak `--apply` tanpa `--expected-user-id`. Ini disengaja agar operator tidak memindahkan akun yang salah pada environment yang salah.

Script akan:

1. mencari tenant platform berdasarkan slug/code;
2. menolak konflik slug/code;
3. membuat tenant platform `ACTIVE` jika belum ada;
4. mencari user `superadmin`;
5. menolak jika ada lebih dari satu `SUPER_ADMIN`;
6. memastikan `superadmin` memiliki role `SUPER_ADMIN`;
7. memindahkan hanya user `superadmin` ke tenant platform;
8. mencetak summary sebelum dan sesudah;
9. commit hanya pada mode `--apply`.

## 6. Verification

Setelah `--apply`, jalankan dry-run ulang:

```powershell
.\.venv\Scripts\python.exe app\scripts\prepare_platform_tenant.py --dry-run
```

Expected:

- platform tenant ditemukan;
- `superadmin` berada pada tenant `platform` / `PLATFORM`;
- planned actions `none`;
- tenant platform tidak berisi user non-`SUPER_ADMIN`.

Verifikasi SQL read-only:

```sql
SELECT id, name, slug, code, status, is_default, is_deleted
FROM tenants
WHERE slug = 'platform' OR code = 'PLATFORM';
```

```sql
SELECT u.id, u.username, u.email, u.role, u.tenant_id, t.slug, t.code, t.status
FROM users u
JOIN tenants t ON t.id = u.tenant_id
WHERE u.username = 'superadmin';
```

```sql
SELECT t.id, t.slug, t.code, COUNT(*) AS total_users
FROM tenants t
JOIN users u ON u.tenant_id = t.id
WHERE t.slug = 'platform' OR t.code = 'PLATFORM'
GROUP BY t.id, t.slug, t.code;
```

Expected:

- satu tenant `platform` / `PLATFORM`;
- status tenant platform `ACTIVE`;
- `superadmin.tenant_id` mengarah ke tenant platform;
- jumlah user pada tenant platform sesuai jumlah akun `SUPER_ADMIN` yang disetujui, idealnya 1.

## 7. Smoke Test Login Superadmin

Setelah verifikasi data:

1. Buka halaman login web.
2. Login sebagai `superadmin`.
3. Pastikan login berhasil.
4. Pastikan diarahkan ke dashboard/platform tenant management.
5. Buka menu tenant management.
6. Pastikan customer tenant existing masih terlihat, termasuk tenant `RQDF/default/DEFAULT`.
7. Logout.
8. Login ulang untuk memastikan session normal.

Catatan:

- Karena enforcement platform tenant belum diimplementasikan, smoke test ini hanya memastikan perpindahan tenant tidak memutus akses `superadmin`.
- Jangan suspend/archive platform tenant.

## 8. Rollback Manual

Rollback hanya dilakukan jika smoke test gagal atau ada masalah operasional.

Manual rollback concept:

1. Identifikasi tenant lama `superadmin` dari backup/dry-run sebelum apply.
   - Pada inventory awal: tenant lama adalah `RQDF/default/DEFAULT`, ID `1`.

2. Pindahkan `superadmin` kembali ke tenant lama.

Contoh SQL manual, sesuaikan `user_id` dan `tenant_id` dengan hasil dry-run/backup:

```sql
UPDATE users
SET tenant_id = <original_tenant_id>
WHERE id = <superadmin_user_id>;
```

3. Jika tenant platform baru tidak dibutuhkan dan belum dipakai, keputusan hapus/soft-delete harus melalui approval manusia terpisah.

4. Verifikasi login ulang.

5. Dokumentasikan rollback:
   - waktu;
   - alasan;
   - query yang dijalankan;
   - operator;
   - hasil verifikasi.

Catatan penting:

- Jangan drop table.
- Jangan hapus tenant platform tanpa approval eksplisit.
- Jika sudah ada data lain terkait tenant platform, rollback perlu analisis tambahan.

## 9. Risks

### Risiko akses admin terkunci

Jika `superadmin` dipindahkan ke tenant platform tetapi login gagal karena asumsi kode lain, akses admin bisa terganggu.

Mitigasi:

- backup;
- dry-run;
- smoke test segera;
- rollback manual siap.

### Risiko konflik sentinel

Jika `slug = "platform"` atau `code = "PLATFORM"` sudah dipakai tenant lain, script akan menolak.

Mitigasi:

- jangan override otomatis;
- review data;
- putuskan manual.

### Risiko lebih dari satu SUPER_ADMIN

Jika ada lebih dari satu `SUPER_ADMIN`, script menolak tanpa approval.

Mitigasi:

- inventory akun;
- putuskan apakah semua super admin harus dipindahkan atau hanya satu akun bootstrap;
- update script/plan setelah approval.

### Risiko platform tenant berisi user non-SUPER_ADMIN

Jika platform tenant existing sudah berisi user non-`SUPER_ADMIN`, script menolak.

Mitigasi:

- audit user tenant tersebut;
- pindahkan user non-platform secara manual setelah approval;
- rerun dry-run.

### Risiko belum ada enforcement

Setelah script berhasil, policy belum otomatis ditegakkan.

Mitigasi:

- lanjut ke tahap test policy;
- implement helper policy;
- implement enforcement login/session/tenant-management dalam PR terpisah.

## 10. Post-Migration Next Steps

Setelah platform tenant siap:

1. Jalankan `--dry-run`.
2. Catat target `user_id`, tenant lama, dan planned actions dari output dry-run.
3. Backup database.
4. Jalankan `--apply --expected-user-id <id-dari-dry-run>`.
5. Verifikasi `superadmin` bisa login.
6. Verifikasi tenant platform hanya berisi `SUPER_ADMIN`.
7. Buat test platform tenant policy.
8. Implement helper:
   - `is_platform_tenant`;
   - `is_platform_admin`;
   - `is_customer_tenant_active`.
9. Patch web login dan request guard secara kecil.
10. Patch admin tenant management agar platform tenant tidak bisa disuspend/archive melalui UI.
11. Buat spec long-term migration `tenant_type = PLATFORM/CUSTOMER`.
