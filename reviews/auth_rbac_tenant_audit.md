# Audit Authentication, RBAC, Active Role, Tenant Isolation, dan Soft Delete

Tanggal: 2026-06-19  
Mode: read-only static review  
Agent: Architecture Agent, Security Reviewer Agent, Code Review Agent  
Keputusan: **REQUEST CHANGES sebelum boundary ini dianggap kuat untuk multi-tenant production**

## 1. Executive Summary

Audit menemukan fondasi yang sudah baik:

- password disimpan menggunakan hash Werkzeug;
- login web memeriksa status tenant saat login;
- role assignment divalidasi dan role aktif hanya dapat dipilih dari role milik user;
- mayoritas route sensitif memakai `login_required` dan `role_required`;
- mobile token ditandatangani, memiliki TTL, tenant claim, type claim, dan revocation list;
- banyak route baru telah melakukan tenant/object ownership check;
- global ORM filter menyembunyikan row `BaseModel` yang soft-deleted secara default;
- query finance dan beberapa domain baru sudah memakai `tenant_id` secara eksplisit.

Namun boundary masih tidak konsisten antara web, mobile API, active role, package tenant, dan model legacy. Empat temuan HIGH terkonfirmasi:

1. Mobile login, refresh, dan decorator tidak memeriksa status tenant.
2. Existing web session tidak dihentikan ketika tenant berubah menjadi suspended/archived.
3. Global package/module guard secara efektif tidak melindungi mobile API.
4. `AcademicYear` dan `Subject` masih global; admin tenant dapat mengubah state/data yang dipakai tenant lain.

Tidak ditemukan bukti vulnerability CRITICAL dalam scope statis ini. Risiko tertinggi adalah kegagalan tenant lifecycle/module isolation dan cross-tenant data integrity, bukan bypass password atau token forgery.

Audit ini tidak menjalankan exploit, test runtime, migration, atau pemeriksaan data production. Beberapa risiko tetap memerlukan test integrasi dua tenant untuk konfirmasi end-to-end.

## 2. Critical Findings

Tidak ada temuan CRITICAL yang terkonfirmasi dari kode dalam scope.

## 3. High Findings

### HIGH-01 — Mobile authentication menerima user dari tenant nonaktif

**File terkait**

- `app/routes/api/auth.py:30-53`
- `app/routes/api/auth.py:142-177`
- `app/routes/api/auth.py:193-217`
- `app/routes/api/common.py:159-186`
- Pembanding: `app/routes/auth.py:93-96`

**Evidence**

- Login web menolak user jika tenant bukan `TenantStatus.ACTIVE`.
- Login mobile memvalidasi password dan `must_change_password`, tetapi tidak memeriksa `user.tenant.status`.
- Tenant hint menerima tenant berdasarkan ID/code/slug tanpa memeriksa status tenant.
- Refresh token dan `mobile_auth_required` hanya memeriksa keberadaan user dan kecocokan `tenant_id`.

**Risiko**

User pada tenant `SUSPENDED` atau `ARCHIVED` masih dapat memperoleh token baru, me-refresh token, dan memakai endpoint mobile. Ini melemahkan kontrol platform untuk menonaktifkan tenant.

**Rekomendasi**

Buat satu policy autentikasi tenant yang digunakan oleh web login, mobile login, refresh, dan setiap request authenticated. Tentukan secara eksplisit apakah `SUPER_ADMIN` merupakan exception.

---

### HIGH-02 — Existing web session tetap aktif setelah tenant disuspensi

**File terkait**

- `app/routes/auth.py:93-98`
- `app/__init__.py:116-151`
- `app/__init__.py:96-99`

**Evidence**

- Status tenant hanya diperiksa saat login web.
- `_enforce_tenant_module_access()` memeriksa role/package, tetapi tidak memeriksa keberadaan tenant, `Tenant.status`, atau tenant soft-delete.
- User loader hanya memuat `User`; ia tidak menolak user yang tenant-nya sudah suspended/archived.

**Risiko**

Session atau remember-cookie yang sudah aktif sebelum suspension tetap dapat mengakses aplikasi sampai session berakhir atau user logout. Tindakan suspend tenant tidak memiliki efek segera dan dapat memberi ekspektasi operasional yang salah.

**Rekomendasi**

Tambahkan fail-closed tenant lifecycle guard pada setiap authenticated request. Definisikan response web/API yang konsisten dan audit event ketika session dihentikan.

---

### HIGH-03 — Tenant package/module restriction tidak diterapkan pada mobile API

**File terkait**

- `app/__init__.py:127-149`
- `app/utils/tenant_modules.py:74-101`
- `app/routes/api/common.py:159-186`

**Evidence**

- Global request guard berhenti bila `current_user` Flask-Login tidak authenticated.
- Mobile API memakai bearer token dan `g.mobile_user`, bukan Flask-Login `current_user`.
- `endpoint_allowed_for_package()` secara eksplisit mengizinkan seluruh endpoint dengan prefix `api.`.
- `mobile_auth_required()` hanya memeriksa role yang dimiliki user dan tidak memeriksa package tenant.

**Skenario**

User mobile yang masih memiliki role `teacher` dapat melewati package restriction dan memanggil endpoint teacher API, meskipun package tenant seharusnya tidak mengaktifkan modul teacher. Request API tidak masuk enforcement berbasis `current_user`.

**Risiko**

Entitlement/package isolation dapat berbeda antara web dan mobile. Modul yang dinonaktifkan secara komersial atau operasional masih mungkin diakses melalui API.

**Rekomendasi**

Pindahkan policy package ke fungsi reusable yang menerima user/tenant/endpoint dan panggil dari web guard serta mobile decorator. Jangan mengandalkan prefix endpoint sebagai exception global.

---

### HIGH-04 — Master akademik global memungkinkan dampak lintas tenant

**File terkait**

- `app/models.py:857-891`
- `app/routes/admin.py:2276-2358`
- `app/routes/teacher.py:3785-3794`
- `app/routes/api/teacher.py:894-896`

**Evidence**

- `AcademicYear` dan `Subject` tidak memiliki `tenant_id`.
- Route admin hanya memerlukan role `ADMIN`; tidak ada tenant scoping untuk master ini.
- `activate_academic_year()` menjalankan `AcademicYear.query.update({is_active: False})`, yang menonaktifkan semua tahun ajaran secara global.
- Create/edit subject juga memodifikasi tabel global.
- Route teacher web/mobile mengambil tahun ajaran aktif secara global.

**Risiko**

Admin satu tenant dapat mengubah tahun ajaran aktif atau subject yang dipakai tenant lain. Ini merupakan cross-tenant data integrity issue. Dampaknya dapat menjalar ke nilai, jadwal, report, dan formula.

**Catatan**

Jika `AcademicYear` dan `Subject` memang sengaja menjadi platform-wide master, authority untuk mengubahnya seharusnya bukan tenant `ADMIN` biasa. Keputusan ownership diperlukan.

**Rekomendasi**

Putuskan apakah data tersebut tenant-owned atau platform-owned. Setelah keputusan, buat hardening plan terpisah; perubahan schema bukan quick fix dan memerlukan migration/backfill yang dirancang.

## 4. Medium Findings

### MEDIUM-01 — Active role bukan authorization boundary

**File terkait**

- `app/utils/roles.py:73-99`
- `app/decorators.py:6-18`
- `app/routes/api/common.py:180-181`
- `app/routes/main.py:217-249`

**Evidence**

- Active role dipakai untuk dashboard dispatch dan presentation.
- `role_required()` dan `mobile_auth_required()` mengizinkan akses jika role ada di `user.all_roles()`, tanpa memeriksa `get_active_role()`.
- User multi-role yang aktif sebagai role A tetap dapat membuka URL role B secara langsung selama ia memiliki role B.

**Risiko**

Jika active role dimaksudkan sebagai mode otorisasi atau separation-of-duty, kontrol tersebut dapat dilewati dengan direct URL/API call. Jika active role hanya preference UI, behavior ini mungkin benar tetapi harus dinyatakan eksplisit.

**Rekomendasi**

Manusia harus memutuskan semantics active role. Jika security boundary, decorator harus mendukung `active_role_required`; jika hanya UI context, ubah istilah/dokumentasi agar tidak memberi jaminan palsu.

---

### MEDIUM-02 — Tidak terlihat rate limiting pada login web/mobile

**File terkait**

- `app/routes/auth.py:80-119`
- `app/routes/api/auth.py:142-186`
- `app/models.py:561-571`

**Evidence**

- Tidak ada throttling/lockout pada login web atau mobile dalam route yang direview.
- Model `MobileRateLimitBucket` tersedia tetapi tidak ditemukan penggunaan dalam kode aplikasi.

**Risiko**

Endpoint password dapat menerima percobaan brute-force atau credential stuffing tanpa application-level throttle. Perlindungan eksternal Nginx/WAF belum diverifikasi dan tidak menggantikan seluruh account-aware control.

**Rekomendasi**

Definisikan rate limit berdasarkan kombinasi IP, identifier, tenant, dan waktu; hindari account enumeration serta denial-of-service melalui lockout permanen.

---

### MEDIUM-03 — Password change/reset tidak membatalkan mobile token existing

**File terkait**

- `app/routes/auth.py:123-149`
- `app/routes/admin.py:6399-6429`
- `app/utils/mobile_api_auth.py:34-56`
- `app/routes/api/common.py:159-186`

**Evidence**

- Token tidak membawa password/session version.
- Mobile decorator tidak membandingkan waktu perubahan password atau token version.
- Perubahan/reset password tidak memasukkan token existing ke revocation list.

**Risiko**

Access token yang dicuri tetap berlaku sampai TTL habis, dan refresh token tetap dapat dipakai setelah password diganti kecuali direvoke secara terpisah. Ini mengurangi efektivitas password reset sebagai incident response.

**Rekomendasi**

Rancang token/session invalidation version per user atau `credentials_changed_at`, lalu validasi pada access dan refresh.

---

### MEDIUM-04 — Refresh token rotation memiliki race window

**File terkait**

- `app/routes/api/auth.py:193-217`
- `app/utils/mobile_api_auth.py:59-77`
- `app/utils/mobile_api_auth.py:95-120`

**Evidence**

- Refresh token dicek terhadap revocation list, token baru diterbitkan, lalu token lama direvoke dan commit.
- Dua request concurrent dapat sama-sama melewati pemeriksaan sebelum salah satunya commit.

**Risiko**

Satu refresh token dapat menghasilkan lebih dari satu token pair dalam race condition. Unique hash mencegah duplicate revoke row, tetapi tidak menjamin single-use rotation secara atomik.

**Rekomendasi**

Gunakan server-side refresh session/JTI dengan consume operation atomik dan unique state transition.

---

### MEDIUM-05 — Tidak ada test khusus untuk boundary yang diaudit

**File terkait**

- `tests/test_finance_core.py`
- `tests/test_grade_formula_service.py`

**Evidence**

Test yang tersedia tidak mencakup login web/mobile, tenant suspension, role switching, cross-tenant object access, package restriction, token refresh/revocation, atau global soft-delete behavior.

**Risiko**

Regression pada authorization dan tenant isolation dapat lolos meskipun suite pytest hijau.

**Rekomendasi**

Buat test matrix dua tenant dan user multi-role sebelum remediation besar. Test harus mencakup web serta `/api/v1`.

## 5. Low Findings

### LOW-01 — Tenant resolution memiliki fallback default yang fail-open untuk caller tertentu

**File terkait**

- `app/utils/tenant.py:6-21`
- Contoh caller: `app/routes/admin.py:141-142`, `app/routes/staff.py:93-94`, `app/routes/boarding.py:115-116`

**Evidence**

`resolve_tenant_id()` secara default mengembalikan default tenant ketika user atau `tenant_id` tidak tersedia. Beberapa privileged helper memanggilnya tanpa `fallback_default=False`.

**Risiko**

Schema saat ini mewajibkan `User.tenant_id`, sehingga exploit langsung belum terkonfirmasi. Namun data rusak, fixture, script, atau future caller dapat diarahkan ke default tenant, bukan gagal tertutup.

**Rekomendasi**

Untuk authenticated/privileged flow, gunakan resolver fail-closed. Batasi fallback default untuk public/bootstrap flow yang memang memerlukannya.

---

### LOW-02 — Soft-delete bypass adalah execution option global tanpa policy wrapper

**File terkait**

- `app/__init__.py:102-114`
- `app/scripts/*` yang memakai `include_deleted=True`

**Evidence**

Setiap query dapat menonaktifkan filter dengan `execution_options(include_deleted=True)`. Saat ini penggunaan yang ditemukan berada pada maintenance scripts, bukan route.

**Risiko**

Future route/service dapat memakai bypass tanpa review boundary yang jelas.

**Rekomendasi**

Dokumentasikan bypass sebagai privileged maintenance operation dan pertimbangkan helper bernama eksplisit. Tambahkan static review rule/test agar route tidak memakai option tersebut.

---

### LOW-03 — Soft-delete contract tidak mencakup seluruh model

**File terkait**

- `app/models.py:12-43`
- `app/models.py:337-344`
- `app/models.py:551-571`
- `app/__init__.py:102-114`

**Evidence**

Filter hanya menargetkan subclass `BaseModel`. `AuditLog`, `MobileRevokedToken`, dan `MobileRateLimitBucket` memakai `db.Model` langsung.

**Risiko**

Untuk token/rate-limit table hal ini kemungkinan disengaja. Namun contract “global soft-delete” tidak benar-benar global dan perlu dokumentasi agar developer tidak mengasumsikan semua model memiliki lifecycle yang sama.

---

### LOW-04 — Decorator authentication web mengembalikan 401 langsung, tidak memakai login flow

**File terkait**

- `app/decorators.py:13-17`

**Evidence**

`role_required()` sendiri melakukan `abort(401)` jika unauthenticated, sedangkan route biasanya juga memakai `login_required`.

**Risiko**

Urutan atau kelalaian decorator dapat menghasilkan behavior berbeda: redirect login vs response 401. Ini terutama masalah consistency dan testability.

## 6. Files Reviewed

Core files:

- `AGENTS.md`
- `agents/architecture.md`
- `agents/security_reviewer.md`
- `agents/code_reviewer.md`
- `checklists/security.md`
- `checklists/code_review.md`
- `app/__init__.py`
- `app/extensions.py`
- `app/models.py`
- `app/decorators.py`
- `app/utils/decorators.py`
- `app/utils/roles.py`
- `app/utils/tenant.py`
- `app/utils/tenant_modules.py`
- `app/utils/mobile_api_auth.py`
- `app/utils/security.py`
- `app/routes/auth.py`
- `app/routes/api/__init__.py`
- `app/routes/api/auth.py`
- `app/routes/api/common.py`

Route files reviewed through decorator inventory, targeted search, and representative code sections:

- `app/routes/main.py`
- `app/routes/admin.py`
- `app/routes/staff.py`
- `app/routes/teacher.py`
- `app/routes/student.py`
- `app/routes/parent.py`
- `app/routes/boarding.py`
- `app/routes/api/teacher.py`
- `app/routes/api/parent.py`
- `app/routes/api/boarding.py`
- `app/routes/api/majlis.py`

Tests inspected:

- `tests/test_finance_core.py`
- `tests/test_grade_formula_service.py`

## 7. Evidence from Code

| Boundary | Positive evidence | Gap evidence |
|---|---|---|
| Web login | `auth.py:93-96` checks active tenant | Check only happens at login |
| Mobile login | Password, forced-change, signed token | No tenant status/package check |
| RBAC | `User.all_roles()` and `has_role()` centralize role ownership | Decorators ignore active-role context |
| Active role | Session value validated against owned roles | Used mainly for dashboard/UI, not authorization |
| Tenant claim | Mobile token embeds `tid`; decorator compares it with current user | Does not validate tenant lifecycle or entitlement |
| Tenant query scoping | Finance/newer route sections explicitly filter tenant | Legacy master models remain global |
| Package guard | Web request guard checks package and endpoint | API bypasses Flask-Login guard and all `api.*` endpoints are allowed |
| Soft delete | ORM listener applies `with_loader_criteria(BaseModel, is_deleted=False)` | Bypass option is global; non-BaseModel tables are outside contract |
| Object ownership | Teacher/parent/boarding flows frequently validate class/child/dormitory membership | Enforcement is distributed and not backed by cross-tenant regression tests |

## 8. Recommended Remediation Plan

### Phase 1 — Define policy before patching

1. Decide whether active role is UI context or authorization boundary.
2. Decide whether `AcademicYear` and `Subject` are platform-owned or tenant-owned.
3. Define expected behavior for `SUSPENDED`, `ARCHIVED`, soft-deleted tenant, and `SUPER_ADMIN`.
4. Define which package entitlements apply equally to web and mobile.

### Phase 2 — Add characterization and security tests

Build a two-tenant test fixture covering:

- active vs suspended tenant;
- web existing session after suspension;
- mobile login, refresh, and existing access token after suspension;
- mobile endpoint against disabled package;
- multi-role user with active-role mismatch;
- cross-tenant admin updates;
- soft-deleted user/profile/object;
- refresh-token concurrent reuse where feasible.

### Phase 3 — Centralize authentication context

Create a single policy layer that resolves:

- authenticated user;
- current tenant;
- tenant lifecycle;
- owned roles;
- active role where applicable;
- package entitlement;
- object ownership.

Web and mobile decorators should call the same policy, with transport-specific responses only.

### Phase 4 — Fix tenant lifecycle and API entitlement

Prioritize:

1. mobile tenant status checks;
2. per-request web tenant status checks;
3. mobile package/module enforcement;
4. token invalidation after credential/security changes.

### Phase 5 — Resolve legacy global data ownership

After the human decision:

- If platform-owned: restrict mutation to platform authority and define read-only tenant access.
- If tenant-owned: write a separate specification for schema expansion, data ownership mapping, backfill, unique constraints, compatibility, and staged migration.

Do not combine this work with unrelated refactoring.

### Phase 6 — Formalize soft-delete contract

- Document which models support soft delete.
- Restrict/document `include_deleted`.
- Add tests for direct query, relationship loading, user loader, and explicit maintenance bypass.

## 9. Quick Wins

Quick wins are recommendations only; no code was changed.

1. Add tests proving mobile login/refresh reject suspended tenants.
2. Add tests proving existing web sessions are terminated or blocked after suspension.
3. Add tests proving disabled tenant packages cannot call corresponding mobile API modules.
4. Add explicit `fallback_default=False` to authenticated privileged tenant helpers.
5. Add a lint/review rule forbidding `include_deleted=True` in `app/routes/`.
6. Document active-role semantics in `AGENTS.md` and permission matrices.
7. Add login rate limiting design and operational monitoring before exposing authentication endpoints more broadly.
8. Add audit logging for login success/failure, role changes, password reset, tenant suspension, and denied cross-tenant access without logging credentials.

## 10. Things Requiring Human Decision

1. **Active role semantics:** Apakah active role hanya menentukan UI/dashboard, atau harus membatasi seluruh authorization selama session?
2. **Master data ownership:** Apakah `AcademicYear`, `Subject`, `MajlisSubject`, dan master legacy lain global atau per tenant?
3. **Super Admin policy:** Apakah super admin boleh login saat tenant terkait suspended, atau harus memakai tenant/platform identity khusus?
4. **Tenant suspension semantics:** Haruskah suspension memutus session/token seketika, atau hanya mencegah login baru?
5. **Package enforcement:** Apakah package merupakan kontrol keamanan/komersial yang wajib identik pada web dan mobile?
6. **Token invalidation:** Apakah password reset, role change, tenant suspension, dan user soft-delete wajib membatalkan semua token aktif?
7. **Rate limiting authority:** Apakah rate limit utama berada di aplikasi, Nginx/WAF, atau keduanya? Konfigurasi production aktual belum direview.
8. **Legacy identifiers:** Username/email/NIP/phone/NIS bersifat tenant-local atau global? Login ambiguity saat ini menunjukkan kedua model masih bercampur.
9. **Soft-delete policy:** Model mana yang wajib soft-delete, mana yang immutable, dan siapa yang boleh membaca deleted rows?
10. **Remediation sequencing:** Apakah prioritas pertama tenant lifecycle/API entitlement atau pemisahan master akademik? Rekomendasi audit: tenant lifecycle/API entitlement terlebih dahulu.

