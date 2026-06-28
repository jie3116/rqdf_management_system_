# Remediation Backlog — Authentication, RBAC, dan Tenant Isolation

Tanggal: 2026-06-19  
Sumber: `reviews/auth-rbac-tenant/auth_rbac_tenant_audit.md`  
Mode: planning only, tidak ada perubahan kode

## Dasar pengurutan

Backlog mengikuti prioritas yang ditetapkan, lalu mempertimbangkan:

1. risiko keamanan;
2. ukuran perubahan;
3. tidak membutuhkan migration;
4. kemudahan membuat automated test.

Item 1–3 merupakan hardening boundary utama dan sebaiknya dikerjakan sebagai rangkaian kecil dengan shared tenant-policy helper. Item 4 dapat berjalan setelah tenant lifecycle stabil. Item 5 dan 6 memerlukan keputusan desain lebih besar.

## Item 1

- **ID:** AUTH-TENANT-001
- **Finding asal:** HIGH-01 — Mobile authentication menerima user dari tenant nonaktif
- **Severity:** HIGH
- **Risiko:** User tenant `SUSPENDED`, `ARCHIVED`, atau tenant yang tidak valid masih dapat login, memperoleh token baru, me-refresh token, dan mengakses endpoint mobile.
- **File terdampak:**
  - `app/routes/api/auth.py`
  - `app/routes/api/common.py`
  - Kemungkinan helper policy baru di `app/utils/`
  - `tests/` untuk test authentication/tenant baru
- **Perubahan yang disarankan:**
  - Buat policy/helper kecil untuk memvalidasi tenant user: tenant tersedia, tidak soft-deleted, dan berstatus `ACTIVE`.
  - Terapkan pada mobile login sebelum token diterbitkan.
  - Terapkan pada refresh sebelum token pair baru diterbitkan.
  - Terapkan pada `mobile_auth_required()` agar access token existing langsung ditolak setelah tenant dinonaktifkan.
  - Terapkan status filter pada tenant hint berdasarkan ID, code, dan slug.
  - Tentukan exception `SUPER_ADMIN` sebelum implementasi.
  - Gunakan error code API yang konsisten dan tidak membocorkan informasi tenant berlebihan.
- **Apakah butuh migration:** Tidak.
- **Apakah butuh test baru:** Ya.
  - Login mobile tenant aktif berhasil.
  - Login mobile tenant suspended/archived ditolak.
  - Refresh tenant suspended ditolak.
  - Access token yang diterbitkan sebelum suspension ditolak setelah status berubah.
  - Tenant hint nonaktif tidak dapat dipakai untuk login.
  - Perilaku `SUPER_ADMIN` sesuai keputusan manusia.
- **Risiko regression:** Sedang. Mobile client dapat menerima error baru ketika tenant tidak aktif. Risiko terbatas karena behavior tersebut memang target keamanan; API error contract perlu dibuat stabil.
- **Urutan pengerjaan:** 1. Implementasikan lebih dahulu sebagai patch kecil tanpa refactor luas. Helper yang dibuat menjadi dependency untuk item 2 dan 3.

## Item 2

- **ID:** AUTH-TENANT-002
- **Finding asal:** HIGH-02 — Existing web session tetap aktif setelah tenant disuspensi
- **Severity:** HIGH
- **Risiko:** Session dan remember-cookie yang sudah aktif dapat terus memakai aplikasi setelah tenant disuspensi atau diarsipkan.
- **File terdampak:**
  - `app/__init__.py`
  - `app/routes/auth.py`
  - Shared tenant-policy helper dari `AUTH-TENANT-001`
  - `tests/` untuk test session lifecycle
- **Perubahan yang disarankan:**
  - Gunakan shared tenant lifecycle policy pada setiap authenticated web request.
  - Fail closed jika tenant tidak ditemukan, soft-deleted, suspended, atau archived.
  - Hapus `active_role`, logout user, dan arahkan ke login dengan pesan generik.
  - Pastikan endpoint logout dan static tidak menyebabkan redirect loop.
  - Pertahankan behavior web login existing dengan memanggil policy yang sama agar aturan tidak terduplikasi.
  - Tentukan exception dan landing page `SUPER_ADMIN`.
- **Apakah butuh migration:** Tidak.
- **Apakah butuh test baru:** Ya.
  - Existing session tenant aktif tetap dapat mengakses route.
  - Existing session tenant suspended diputus atau diblok.
  - Remember session mengikuti policy yang sama.
  - Tenant soft-deleted dan missing ditolak.
  - Tidak terjadi redirect loop pada login/logout/change-password.
  - `SUPER_ADMIN` mengikuti policy yang disetujui.
- **Risiko regression:** Sedang. Salah urutan `before_request` dapat menyebabkan redirect loop atau menghalangi flow ganti password/logout. Test request lifecycle wajib dibuat sebelum patch dinyatakan selesai.
- **Urutan pengerjaan:** 2. Kerjakan setelah helper dan semantics tenant pada item 1 disetujui.

## Item 3

- **ID:** AUTH-PACKAGE-003
- **Finding asal:** HIGH-03 — Tenant package/module restriction tidak diterapkan pada mobile API
- **Severity:** HIGH
- **Risiko:** User dapat mengakses modul mobile yang tidak termasuk package tenant, sehingga entitlement web dan API berbeda.
- **File terdampak:**
  - `app/routes/api/common.py`
  - `app/utils/tenant_modules.py`
  - `app/__init__.py`
  - Kemungkinan registrar/decorator pada `app/routes/api/`
  - `tests/` untuk matrix package dan endpoint
- **Perubahan yang disarankan:**
  - Ekstrak policy package menjadi fungsi reusable yang menerima tenant, role, dan capability/module.
  - Terapkan policy tersebut dari `mobile_auth_required()` setelah tenant lifecycle tervalidasi.
  - Hindari hanya memetakan berdasarkan prefix endpoint; gunakan capability/module eksplisit seperti `teacher`, `student`, `boarding`, `finance`, atau `majlis`.
  - Pertahankan web guard dengan policy yang sama untuk mencegah drift.
  - Definisikan response API `403` yang konsisten.
  - Jangan mengubah package mapping bisnis sebelum mendapat approval.
- **Apakah butuh migration:** Tidak.
- **Apakah butuh test baru:** Ya.
  - Matrix package × role × endpoint untuk package `full`, `sekolah`, dan `rumah_quran`.
  - Endpoint mobile yang diizinkan tetap berhasil.
  - Endpoint mobile modul nonaktif menghasilkan `403`.
  - Web dan API menghasilkan keputusan authorization yang sama.
  - Multi-role user tidak mendapat akses melalui role yang tidak valid untuk package.
- **Risiko regression:** Sedang–tinggi. Package mapping existing dapat memiliki pengecualian bisnis yang belum terdokumentasi. Implementasi harus dimulai dari characterization test terhadap behavior web saat ini.
- **Urutan pengerjaan:** 3. Kerjakan setelah tenant lifecycle enforcement stabil karena decorator API akan memakai context yang sama.

## Item 4

- **ID:** AUTH-RATE-004
- **Finding asal:** MEDIUM-02 — Tidak terlihat rate limiting pada login web/mobile
- **Severity:** MEDIUM
- **Risiko:** Login web dan mobile rentan terhadap brute-force dan credential stuffing; logging atau proteksi reverse proxy belum diverifikasi.
- **File terdampak:**
  - `app/routes/auth.py`
  - `app/routes/api/auth.py`
  - `app/models.py` pada `MobileRateLimitBucket`
  - Kemungkinan service/helper rate limit baru di `app/services/` atau `app/utils/`
  - Konfigurasi aplikasi non-secret
  - `tests/` untuk window dan bucket behavior
- **Perubahan yang disarankan:**
  - Verifikasi terlebih dahulu bahwa tabel `mobile_rate_limit_buckets` tersedia pada semua environment production.
  - Gunakan service rate-limit bersama untuk web dan mobile, bukan implementasi terpisah.
  - Gunakan kombinasi action, normalized identifier, tenant hint, dan IP-derived scope.
  - Simpan hash identifier bila bucket disimpan di database agar PII tidak menjadi key mentah.
  - Terapkan fixed/sliding window dengan expiry dan response generik.
  - Jangan membuat permanent account lockout yang dapat dipakai untuk denial-of-service.
  - Tentukan interaksi dengan Nginx/WAF dan observability.
- **Apakah butuh migration:** Diperkirakan tidak, **jika** tabel `mobile_rate_limit_buckets` sudah terpasang dan kolom existing mencukupi. Jika tabel belum ada pada migration history production atau desain membutuhkan kolom tambahan, migration terpisah diperlukan.
- **Apakah butuh test baru:** Ya.
  - Percobaan di bawah limit tetap diproses.
  - Percobaan melebihi limit ditolak.
  - Bucket reset setelah window berakhir.
  - Login berhasil mereset atau menurunkan counter sesuai policy.
  - Web dan mobile memakai policy setara.
  - Identifier/IP berbeda tidak salah berbagi bucket.
  - Response tidak mengungkap apakah akun ada.
- **Risiko regression:** Sedang–tinggi. Policy terlalu agresif dapat memblokir user sah di jaringan NAT bersama atau membuat database bottleneck. Nilai limit harus configurable dan dimonitor.
- **Urutan pengerjaan:** 4. Kerjakan setelah item 1–3 agar semua jalur auth memakai tenant/package context yang stabil.

## Item 5

- **ID:** AUTH-TOKEN-005
- **Finding asal:** MEDIUM-03 — Password change/reset tidak membatalkan mobile token existing
- **Severity:** MEDIUM
- **Risiko:** Access/refresh token yang dicuri tetap valid setelah password diganti atau di-reset, sehingga password reset tidak cukup sebagai respons insiden.
- **File terdampak:**
  - `app/models.py`
  - `app/utils/mobile_api_auth.py`
  - `app/routes/api/common.py`
  - `app/routes/api/auth.py`
  - `app/routes/auth.py`
  - Seluruh route admin yang mengubah/reset password
  - Kemungkinan route perubahan role, tenant suspension, dan user deletion
  - `tests/` untuk token invalidation
- **Perubahan yang disarankan:**
  - Pilih satu mekanisme authoritative:
    - `token_version` per user yang dimasukkan ke token; atau
    - `credentials_changed_at` yang dibandingkan dengan waktu penerbitan token.
  - Naikkan version/timestamp pada password change dan reset.
  - Putuskan apakah role change, tenant suspension, user soft-delete, dan security-sensitive profile change juga membatalkan token.
  - Validasi version/timestamp pada access dan refresh.
  - Pertahankan revocation list untuk logout/token-specific revoke.
- **Apakah butuh migration:** Ya untuk solusi penuh yang robust, karena membutuhkan state invalidation per user. Alternatif tanpa migration seperti memperpendek TTL hanya mengurangi risiko dan tidak menyelesaikan finding.
- **Apakah butuh test baru:** Ya.
  - Token lama ditolak setelah password change.
  - Token lama ditolak setelah admin reset.
  - Token baru setelah perubahan tetap valid.
  - Logout individual token tetap bekerja.
  - Perilaku role change/suspension sesuai keputusan manusia.
  - Web session invalidation diuji jika dimasukkan dalam scope.
- **Risiko regression:** Tinggi. Perubahan token format memengaruhi seluruh mobile client dan sesi aktif. Rollout harus backward-compatible atau secara eksplisit memaksa login ulang.
- **Urutan pengerjaan:** 5. Buat feature spec dan migration plan terpisah setelah policy invalidation diputuskan. Jangan digabung dengan rate limiting.

## Item 6

- **ID:** TENANT-DATA-006
- **Finding asal:** HIGH-04 — Master akademik global memungkinkan dampak lintas tenant
- **Severity:** HIGH
- **Risiko:** Admin satu tenant dapat mengubah tahun ajaran aktif dan subject global yang digunakan tenant lain, menyebabkan cross-tenant data integrity failure.
- **File terdampak:**
  - `app/models.py`
  - `app/routes/admin.py`
  - `app/routes/teacher.py`
  - `app/routes/api/teacher.py`
  - Service akademik, grade, schedule, report, dan form terkait
  - Migration Alembic baru jika data menjadi tenant-owned
  - `tests/` untuk isolation dua tenant
- **Perubahan yang disarankan:**
  - Lakukan human decision terlebih dahulu:
    - **Platform-owned:** pertahankan schema, batasi create/edit/activate ke `SUPER_ADMIN`, dan buat tenant admin read-only; atau
    - **Tenant-owned:** tambahkan `tenant_id`, tenant-scoped unique/index, backfill ownership, dan ubah seluruh query/relationship.
  - Inventarisasi seluruh foreign key dan penggunaan `AcademicYear`, `Subject`, serta `MajlisSubject` sebelum desain.
  - Jika tenant-owned, gunakan staged expand/backfill/switch/contract rollout.
  - Jangan memperbaiki hanya route `activate_academic_year`; ownership harus konsisten pada read dan write path.
- **Apakah butuh migration:** 
  - Tidak, jika keputusan akhirnya platform-owned dan remediation hanya membatasi authority.
  - Ya, dan kemungkinan kompleks, jika data harus tenant-owned.
- **Apakah butuh test baru:** Ya.
  - Platform-owned: tenant admin tidak dapat mutasi; super admin dapat mutasi.
  - Tenant-owned: admin tenant A tidak dapat melihat/mengubah data tenant B.
  - Hanya satu academic year aktif per tenant.
  - Subject code/name uniqueness sesuai tenant.
  - Teacher web/mobile hanya memakai master tenant sendiri.
  - Report, schedule, grade, dan formula tidak mengalami regression.
- **Risiko regression:** Sangat tinggi untuk opsi tenant-owned karena master akademik dipakai luas dan memiliki banyak foreign key. Sedang untuk opsi platform-owned karena permission/UI admin berubah.
- **Urutan pengerjaan:** 6. Kerjakan terakhir setelah keputusan ownership, dependency inventory, feature spec, migration review, dan characterization tests tersedia. Walaupun severity HIGH, perubahan ini ditempatkan terakhir karena scope besar dan berpotensi membutuhkan migration.

## Ringkasan Urutan

| Urutan | ID | Severity | Migration | Testability | Alasan posisi |
|---|---|---|---|---|---|
| 1 | AUTH-TENANT-001 | HIGH | Tidak | Tinggi | Menutup mobile tenant lifecycle dengan patch kecil |
| 2 | AUTH-TENANT-002 | HIGH | Tidak | Tinggi | Menutup existing web session menggunakan policy yang sama |
| 3 | AUTH-PACKAGE-003 | HIGH | Tidak | Tinggi | Menyamakan entitlement web dan mobile |
| 4 | AUTH-RATE-004 | MEDIUM | Kemungkinan tidak | Tinggi | Hardening login, perlu policy operasional |
| 5 | AUTH-TOKEN-005 | MEDIUM | Ya | Tinggi | Dampak seluruh token/client dan perlu rollout |
| 6 | TENANT-DATA-006 | HIGH | Kondisional | Sedang | Risiko tinggi tetapi scope dan migration paling besar |

## Dependency dan Approval Gates

- Item 1 dan 2 memerlukan keputusan tentang exception `SUPER_ADMIN` dan semantics tenant suspension.
- Item 3 memerlukan approval matrix package/module.
- Item 4 memerlukan verifikasi migration/table existing dan keputusan limit operasional.
- Item 5 memerlukan keputusan event apa saja yang membatalkan token serta strategi forced re-login.
- Item 6 tidak boleh dimulai sebelum ownership master akademik diputuskan.
- Setiap item harus melewati Testing & QA, Security Review, dan Code Review secara terpisah.
- Migration dan deployment tetap memerlukan approval manusia.

