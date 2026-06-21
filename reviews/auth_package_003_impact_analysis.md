# AUTH-PACKAGE-003 Impact Analysis

Tanggal: 2026-06-21  
Mode: analysis + test plan only  
Scope: mobile API `/api/v1` package/module entitlement  
Tidak dilakukan: perubahan kode aplikasi, migration, deploy, atau eksekusi migration.

## 1. Current Behavior

Web request guard di `app/__init__.py` sudah menjalankan urutan dasar untuk user Flask-Login:

1. user authenticated;
2. `SUPER_ADMIN` dikecualikan;
3. tenant lifecycle aktif melalui `is_user_tenant_active()`;
4. role user cocok dengan package tenant melalui `role_allowed_for_package()`;
5. endpoint web cocok dengan package tenant melalui `endpoint_allowed_for_package()`.

Mobile API tidak melewati guard web tersebut karena autentikasi mobile memakai bearer token dan context `g.mobile_user`, bukan `current_user` Flask-Login. `mobile_auth_required()` di `app/routes/api/common.py` saat ini memvalidasi token, user, token tenant claim, tenant lifecycle aktif, dan role yang diminta decorator. Namun decorator belum memvalidasi entitlement package/module tenant.

Selain itu, `endpoint_allowed_for_package()` di `app/utils/tenant_modules.py` saat ini mengizinkan semua endpoint dengan prefix `api.`. Akibatnya, sekalipun web guard dipanggil untuk request API, package restriction API tetap fail-open.

## 2. Package/Module Matrix Existing

Sumber mapping existing: `app/utils/tenant_modules.py`.

| Package | Role yang diizinkan | Endpoint/module web yang diblokir eksplisit |
|---|---|---|
| `full` | semua role | tidak ada |
| `sekolah` | `ADMIN`, `PIMPINAN`, `TU`, `GURU`, `SISWA`, `WALI_MURID` | `staff.*`, `boarding.*`, `main.majlis_dashboard`, `parent.join_majlis`, `parent.majlis_dashboard`, `parent.majlis_activities` |
| `rumah_quran` | `ADMIN`, `PIMPINAN`, `TU`, `WALI_MURID`, `MAJLIS_PARTICIPANT` | `teacher.*`, `student.*`, `boarding.*`, `parent.dashboard`, beberapa admin akademik sekolah: `admin.manage_academic_years`, `admin.activate_academic_year`, `admin.manage_subjects`, `admin.edit_subject`, `admin.manage_extracurriculars` |

Catatan:

- `endpoint_allowed_for_package()` memperlakukan `static`, `auth.`, dan `api.` sebagai allow-list global.
- `get_tenant_package()` default ke `full` jika tenant tidak memiliki config `tenant.module_package`.
- Web juga punya pembatas tambahan di beberapa route admin/staff untuk kategori siswa dan data majlis, tetapi itu bukan policy reusable untuk semua endpoint.

## 3. Mobile API Endpoints Likely Bypassing Package Restriction

Semua endpoint berikut memakai blueprint endpoint `api.*`, sehingga saat ini kemungkinan bypass package restriction existing.

### Auth/Common

| Method/path | Role decorator | Capability | Rekomendasi package behavior |
|---|---|---|---|
| `POST /auth/login` | public | auth | Tetap tidak memakai module entitlement; tetap wajib tenant lifecycle active. |
| `POST /auth/refresh` | public refresh token | auth | Tetap tidak memakai module endpoint entitlement; tetap wajib tenant lifecycle active. |
| `GET /auth/me` | authenticated | common/auth | Boleh untuk semua package setelah token, user, tenant lifecycle, dan role/package valid. |
| `POST /auth/logout` | authenticated | auth | Boleh untuk semua package agar user selalu bisa logout. |
| `POST /auth/push-token` | authenticated | common/device | Boleh untuk semua package, atau minimal tidak terikat module domain. |

### Teacher / Student-School

| Method/path | Role decorator | Capability/module |
|---|---|---|
| `GET /teacher/dashboard` | `GURU` | `teacher`, `student`, `announcement` |
| `GET /teacher/input-grades` | `GURU` | `teacher`, `student` |
| `POST /teacher/input-grades` | `GURU` | `teacher`, `student` |
| `GET /teacher/input-attendance` | `GURU` | `teacher`, `student` |
| `POST /teacher/input-attendance` | `GURU` | `teacher`, `student` |
| `GET /teacher/input-tahfidz` | `GURU` | `teacher`, `student` or Quran learning |
| `POST /teacher/input-tahfidz` | `GURU` | `teacher`, `student` or Quran learning |
| `GET /teacher/input-recitation` | `GURU` | `teacher`, `student` or Quran learning |
| `POST /teacher/input-recitation` | `GURU` | `teacher`, `student` or Quran learning |
| `GET /teacher/input-evaluation` | `GURU` | `teacher`, `student` or Quran learning |
| `POST /teacher/input-evaluation` | `GURU` | `teacher`, `student` or Quran learning |
| `GET /teacher/input-behavior` | `GURU` | `teacher`, `student` |
| `POST /teacher/input-behavior` | `GURU` | `teacher`, `student` |
| `GET /teacher/grade-history` | `GURU` | `teacher`, `student` |
| `GET /teacher/attendance-history` | `GURU` | `teacher`, `student` |
| `GET /teacher/homeroom-students` | `GURU` | `teacher`, `student` |
| `GET /teacher/class-announcements` | `GURU` | `teacher`, `announcement` |
| `POST /teacher/class-announcements` | `GURU` | `teacher`, `announcement` |

Expected from existing package policy: blocked for `rumah_quran`, allowed for `full` and `sekolah`.

### Parent / Student / Finance / Announcement / Boarding-Adjacent

| Method/path | Role decorator | Capability/module |
|---|---|---|
| `GET /parent/children` | `WALI_MURID` | `parent`, `student` |
| `GET /parent/dashboard` | `WALI_MURID` | `parent`, mixed student/finance/announcement |
| `GET /parent/children/<child_id>/announcements` | `WALI_MURID` | `parent`, `announcement` |
| `GET /parent/children/<child_id>/finance` | `WALI_MURID` | `parent`, `finance` |
| `GET /parent/children/<child_id>/memorization-report` | `WALI_MURID` | `parent`, Quran learning |
| `GET /parent/children/<child_id>/savings` | `WALI_MURID` | `parent`, `finance`, `boarding`/pesantren savings |
| `POST /parent/children/<child_id>/savings/pin` | `WALI_MURID` | `parent`, `finance`, `boarding`/pesantren savings |
| `POST /parent/children/<child_id>/savings/topup` | `WALI_MURID` | `parent`, `finance`, `boarding`/pesantren savings |
| `GET /parent/children/<child_id>/weekly-schedule` | `WALI_MURID` | `parent`, `student` |
| `GET /parent/children/<child_id>/academic-grades` | `WALI_MURID` | `parent`, `student` |
| `GET /parent/children/<child_id>/attendance` | `WALI_MURID` | `parent`, `student`, includes `boarding` records if child is boarding |
| `GET /parent/children/<child_id>/behavior` | `WALI_MURID` | `parent`, `student` |

Expected from existing package policy needs human confirmation because web behavior is mixed:

- `sekolah`: parent role is allowed; majlis web endpoints are blocked; boarding module is blocked. Parent school/student endpoints should stay allowed, but boarding-specific data/actions such as savings and boarding attendance should likely be blocked or hidden.
- `rumah_quran`: parent role is allowed, but web `parent.dashboard` is blocked while majlis parent participation is allowed. School-only child academic endpoints should likely be blocked when school module is not active. Quran/majlis parent use cases should remain available if they are part of rumah_quran.

### Boarding

| Method/path | Role decorator | Capability/module |
|---|---|---|
| `GET /boarding/dashboard` | `WALI_ASRAMA` | `boarding` |
| `GET /boarding/attendance` | `WALI_ASRAMA` | `boarding` |
| `POST /boarding/attendance` | `WALI_ASRAMA` | `boarding` |
| `GET /boarding/savings` | `WALI_ASRAMA` | `boarding`, `finance` |
| `POST /boarding/savings/officer-pin` | `WALI_ASRAMA` | `boarding`, `finance` |
| `POST /boarding/savings/withdraw` | `WALI_ASRAMA` | `boarding`, `finance` |

Expected from existing package policy: allowed for `full`, blocked for `sekolah` and `rumah_quran`. Existing role policy already excludes `WALI_ASRAMA` from non-`full`, but mobile should still enforce module explicitly to avoid future role drift.

### Majlis

| Method/path | Role decorator | Capability/module |
|---|---|---|
| `GET /majlis/announcements` | `MAJLIS_PARTICIPANT`, `WALI_MURID` | `majlis`, `announcement` |
| `GET /majlis/dashboard` | `MAJLIS_PARTICIPANT`, `WALI_MURID` | `majlis`, may include parent finance summary |

Expected from existing package policy: allowed for `full` and `rumah_quran`, blocked for `sekolah`.

## 4. Recommended Design

Jangan menambahkan pengecekan ad hoc berdasarkan prefix `api.` sebagai allow-all. Design yang lebih aman:

1. Buat policy reusable di `app/utils/tenant_modules.py` atau helper policy terpisah yang menerima context eksplisit: `tenant_id`/tenant package, user role(s), endpoint, dan capability/module.
2. Policy harus punya konsep capability yang eksplisit, misalnya `auth`, `common`, `teacher`, `student`, `parent`, `boarding`, `finance`, `majlis`, `announcement`.
3. Web guard tetap bisa memakai policy yang sama lewat mapping endpoint web ke capability, dengan compatibility mode untuk endpoint mapping existing.
4. Mobile decorator menerima capability/module eksplisit, misalnya `@mobile_auth_required(UserRole.GURU, capability="teacher")`, atau wrapper seperti `@mobile_module_required("teacher", UserRole.GURU)`.
5. Urutan validasi mobile harus fail-closed:
   - bearer token ada dan valid;
   - user ditemukan;
   - tenant claim cocok;
   - tenant lifecycle active;
   - role decorator valid;
   - role user tersedia untuk package tenant;
   - capability/module endpoint tersedia untuk package tenant.
6. Auth endpoints login/refresh/logout harus tetap punya policy khusus agar logout dan refresh lifecycle tidak rusak. `login` dan `refresh` bukan module entitlement, tetapi tetap harus menolak tenant nonaktif.
7. Common endpoint seperti `/auth/me` dan `/auth/push-token` boleh global setelah role/package user valid, tetapi tidak boleh membuka module domain.

Policy capability awal yang paling konsisten dengan mapping existing:

| Capability | `full` | `sekolah` | `rumah_quran` | Catatan |
|---|---:|---:|---:|---|
| `auth` | yes | yes | yes | login/refresh/logout |
| `common` | yes | yes | yes | `/auth/me`, push token |
| `teacher` | yes | yes | no | sesuai block `teacher.*` untuk rumah_quran |
| `student` | yes | yes | no untuk school-only | perlu keputusan untuk Quran learner vs school student |
| `parent` | yes | yes | partial | web `parent.dashboard` diblokir untuk rumah_quran, majlis parent masih allowed |
| `boarding` | yes | no | no | sesuai block `boarding.*` |
| `finance` | yes | yes | partial | invoice parent mungkin school; savings terkait pesantren/boarding |
| `majlis` | yes | no | yes | sesuai block majlis endpoints untuk sekolah |
| `announcement` | yes | yes | yes/conditional | class announcement mengikuti module asal; majlis announcement mengikuti majlis |

## 5. Regression Risks

1. Mobile clients mungkin bergantung pada endpoint yang sebelumnya terbuka meski package tenant tidak mengaktifkan modulnya.
2. Endpoint parent bersifat campuran. Jika satu endpoint mengembalikan student, finance, announcement, Quran, dan boarding data sekaligus, policy tunggal per endpoint dapat terlalu ketat atau terlalu longgar.
3. Role check dan capability check bisa berbeda keputusan jika multi-role user memiliki role yang allowed tetapi mencoba capability dari role/module lain.
4. Web mapping existing berbasis endpoint prefix dan exception list; jika langsung diganti tanpa characterization test, route web bisa berubah behavior.
5. `get_tenant_package()` default ke `full`; tenant tanpa config akan tetap mendapat semua modul. Itu existing behavior dan sebaiknya tidak diubah di AUTH-PACKAGE-003 tanpa approval.
6. `SUPER_ADMIN` exception web ada di request guard. Mobile policy perlu keputusan apakah super admin mobile boleh bypass package/module atau tidak.

## 6. Test Plan

Test harus dibuat sebelum implementasi sebagai characterization dan setelah implementasi sebagai regression suite.

### Fixtures minimal

- Tenant `full`, `sekolah`, dan `rumah_quran`, semuanya `ACTIVE`.
- Config `AppConfig` dengan key `tenant.module_package`.
- User role `GURU`, `WALI_MURID`, `WALI_ASRAMA`, `MAJLIS_PARTICIPANT`, dan user multi-role.
- Token mobile valid dari `/api/v1/auth/login`.
- Minimal profile/domain rows agar endpoint target melewati lookup awal atau setidaknya mencapai authorization gate dengan deterministik.

### Mobile package tests

| Case | Expected |
|---|---|
| Tenant package `full` + role `GURU` akses `GET /api/v1/teacher/dashboard` | allowed atau domain-level response non-403 package |
| Tenant package `full` + role `WALI_ASRAMA` akses `GET /api/v1/boarding/dashboard` | allowed atau domain-level response non-403 package |
| Tenant package `full` + role `MAJLIS_PARTICIPANT` akses `GET /api/v1/majlis/dashboard` | allowed atau domain-level response non-403 package |
| Tenant package `sekolah` + role `WALI_ASRAMA` akses `/api/v1/boarding/*` | `403 module_disabled` atau error code setara |
| Tenant package `sekolah` + role `MAJLIS_PARTICIPANT` akses `/api/v1/majlis/dashboard` | `403 module_disabled` atau role/package forbidden |
| Tenant package `rumah_quran` + role `GURU` akses `/api/v1/teacher/dashboard` | `403 module_disabled` atau role/package forbidden |
| Tenant package `rumah_quran` + school-only parent endpoint `academic-grades` | `403 module_disabled`, jika manusia menyetujui school-only mapping |
| Auth `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout` | tetap tidak rusak |
| Common `/auth/me`, `/auth/push-token` | tetap allowed untuk package valid |
| Multi-role user pada `rumah_quran` dengan `WALI_MURID` + `GURU` akses teacher API | denied karena role/module `GURU` tidak tersedia untuk package |
| Multi-role user pada `sekolah` dengan `WALI_MURID` + `MAJLIS_PARTICIPANT` akses majlis API | denied karena role/module majlis tidak tersedia |

### Web/mobile consistency tests

Untuk setiap capability utama, buat pasangan test yang membandingkan keputusan web guard dan mobile policy:

- `teacher`: web `teacher.dashboard` vs mobile `/teacher/dashboard`;
- `boarding`: web `boarding.*` route representatif vs mobile `/boarding/dashboard`;
- `majlis`: web `main.majlis_dashboard` atau `parent.majlis_dashboard` vs mobile `/majlis/dashboard`;
- `parent/student`: web `parent.dashboard` atau student route representatif vs mobile parent child endpoint;
- `auth/common`: pastikan endpoint auth tetap tidak terikat module domain.

Assertion tidak perlu response body identik, tetapi keputusan authorization harus konsisten: allowed vs denied karena package/module.

## 7. Implementation Sequence

1. Tambahkan characterization tests untuk `endpoint_allowed_for_package()`, `role_allowed_for_package()`, dan endpoint mobile representatif tanpa mengubah policy.
2. Definisikan capability mapping eksplisit untuk web dan mobile. Mulai dari endpoint yang jelas: `teacher`, `boarding`, `majlis`, `auth`, `common`.
3. Tambahkan reusable policy function, misalnya `package_allows_capability(package, capability)` dan helper context seperti `user_allowed_for_package_capability(user, package, capability, roles=None)`.
4. Ubah web guard agar memakai policy baru tetapi tetap menjaga compatibility exception existing.
5. Ubah mobile decorator atau buat decorator baru yang menerima capability eksplisit.
6. Pasang capability pada endpoint mobile secara bertahap: auth/common, teacher, boarding, majlis, parent.
7. Jalankan test package matrix dan test tenant lifecycle existing.
8. Buat security/code review terpisah setelah patch implementasi. Tidak ada migration.

## 8. Things Requiring Human Decision

1. Apakah `SUPER_ADMIN` mobile boleh bypass package/module seperti web guard, atau mobile super admin tidak didukung?
2. Apakah `parent` pada package `rumah_quran` boleh mengakses endpoint child school-only, atau hanya majlis/Quran parent endpoints?
3. Apakah `finance` merupakan capability mandiri yang tersedia untuk semua package, atau harus mengikuti module asal: school invoice, majlis finance, boarding savings?
4. Apakah `announcement` global, atau harus mengikuti target domain: class announcement mengikuti `teacher/student`, majlis announcement mengikuti `majlis`?
5. Apakah endpoint campuran seperti `/parent/dashboard` perlu dipecah responsenya berdasarkan package, atau cukup diblokir penuh untuk package tertentu mengikuti web behavior existing?
6. Error contract API final: gunakan `403 module_disabled`, `403 forbidden`, atau code lain yang sudah disepakati client mobile?

