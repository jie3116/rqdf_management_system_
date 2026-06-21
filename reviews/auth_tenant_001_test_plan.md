# Test Plan — AUTH-TENANT-001

Tanggal: 2026-06-19  
Finding: HIGH-01 — Mobile authentication menerima user dari tenant nonaktif  
Mode: test planning only; belum ada perubahan kode aplikasi atau test

## 1. Tujuan

Membuktikan bahwa mobile authentication hanya mengizinkan user dari tenant yang:

- tersedia;
- tidak soft-deleted;
- memiliki `TenantStatus.ACTIVE`.

Policy harus berlaku konsisten pada:

1. login dan penerbitan token;
2. refresh token;
3. penggunaan access token existing;
4. resolusi tenant hint berdasarkan ID, code, atau slug.

## 2. Kode yang dianalisis

### `app/routes/api/auth.py`

- `_resolve_tenant_hint()` mengambil tenant berdasarkan `tenant_id`, `tenant_code`, atau `tenant_slug`, tetapi belum memeriksa `Tenant.status`.
- `auth_login()` memeriksa credential dan `must_change_password`, tetapi belum memeriksa lifecycle tenant sebelum menerbitkan token.
- `auth_refresh()` memeriksa token, user, dan kesesuaian `tenant_id`, tetapi belum memeriksa lifecycle tenant.

### `app/routes/api/common.py`

- `mobile_auth_required()` memvalidasi bearer token, revocation, user, tenant claim, dan role.
- Decorator belum memeriksa apakah tenant user masih aktif pada saat request.
- Endpoint `/api/v1/auth/me` merupakan probe paling kecil untuk menguji access token existing tanpa bergantung pada profile domain.

### `app/utils/mobile_api_auth.py`

- Token membawa `uid`, `tid`, `typ`, dan `jti`.
- TTL access dan refresh berbeda.
- Decoder memeriksa signature, expiry, type, dan revocation.
- Helper ini sebaiknya tidak menjadi lokasi policy tenant karena tugasnya adalah token cryptography/state, bukan business authorization.

### Helper auth terkait

- Login web di `app/routes/auth.py` sudah memeriksa tenant aktif dan dapat menjadi reference behavior.
- `TenantStatus` berada di `app/models.py` dengan state `ACTIVE`, `SUSPENDED`, dan `ARCHIVED`.
- Global soft-delete filter di `app/__init__.py` membuat query `Tenant` dan `User` otomatis mengecualikan row `BaseModel.is_deleted=True`.

## 3. Scope

### In scope

- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `GET /api/v1/auth/me`
- Tenant hint dari JSON payload dan header.
- Tenant state `ACTIVE`, `SUSPENDED`, dan `ARCHIVED`.

### Out of scope

- Web session tenant suspension (`AUTH-TENANT-002`).
- Package/module enforcement (`AUTH-PACKAGE-003`).
- Rate limiting.
- Password reset/token-version invalidation.
- `SUPER_ADMIN`, sampai exception policy diputuskan manusia.
- PostgreSQL-specific behavior; test tahap ini dapat memakai SQLite in-memory karena tidak menguji enum migration atau locking.

## 4. Kontrak hasil yang perlu disetujui

Rekomendasi kontrak untuk tenant nonaktif:

- HTTP status: `403 Forbidden`
- `success`: `false`
- `code`: `tenant_inactive`
- `message`: pesan generik, misalnya tenant akun tidak aktif
- Response tidak mengembalikan token atau detail status `SUSPENDED`/`ARCHIVED`.

Kontrak yang sama sebaiknya dipakai pada login, refresh, dan protected endpoint. Jika tim memilih `401`, seluruh test expected response harus disesuaikan sebelum implementasi.

Untuk tenant hint nonaktif, rekomendasi:

- Hint tidak boleh membuat suspended/archived tenant menjadi kandidat autentikasi yang valid.
- Jika credential secara global ambigu dan hint mengarah ke tenant nonaktif, request ditolak tanpa token.
- Pilihan error dapat `tenant_inactive` atau error login generik. Rekomendasi `tenant_inactive` setelah password benar, tetapi keputusan ini perlu mempertimbangkan tenant enumeration.

## 5. File test yang akan dibuat

File baru yang disarankan:

`tests/test_mobile_auth_tenant_status.py`

Alasan:

- Scope cukup fokus untuk satu remediation.
- Memisahkan security boundary dari test finance/grade existing.
- Nama file mudah ditemukan ketika menjalankan regression:

```powershell
pytest tests/test_mobile_auth_tenant_status.py -q
```

Belum disarankan membuat `conftest.py` pada tahap pertama. Fixture lokal menjaga perubahan kecil. Fixture dapat dipindah ke `tests/conftest.py` setelah dipakai oleh AUTH-TENANT-002/003.

## 6. Konfigurasi test

Gunakan pola `TestConfig` existing:

- `SECRET_KEY = "test-secret"`
- `TESTING = True`
- `WTF_CSRF_ENABLED = False`
- `SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"`
- `SQLALCHEMY_TRACK_MODIFICATIONS = False`
- TTL token dapat dibuat eksplisit agar test deterministik:
  - `MOBILE_ACCESS_TOKEN_TTL_SECONDS = 3600`
  - `MOBILE_REFRESH_TOKEN_TTL_SECONDS = 86400`

Test menggunakan `create_app(TestConfig)`, `db.create_all()`, dan `db.drop_all()` dalam application context.

## 7. Fixture yang diperlukan

### `app`

Membuat Flask app test dan schema in-memory.

Lifecycle:

1. `create_app(TestConfig)`
2. masuk app context;
3. `db.create_all()`;
4. yield app;
5. `db.session.remove()`;
6. `db.drop_all()`.

### `client`

Mengembalikan `app.test_client()`.

### `tenant_factory`

Factory untuk membuat tenant dengan parameter:

- `name`
- `slug`
- `code`
- `status`
- `is_default=False`
- `is_deleted=False`

Default status: `TenantStatus.ACTIVE`.

### `user_factory`

Factory untuk membuat user dengan parameter:

- `tenant`
- `username`
- `email`
- `password`
- `role=UserRole.SISWA`
- `must_change_password=False`

Factory wajib memanggil `user.set_password(password)`.

Profile `Student` tidak diperlukan untuk login, refresh, dan `/auth/me`; `user_payload()` dapat fallback ke username.

### `tenant_auth_matrix`

Fixture utama berisi:

- tenant active;
- tenant suspended;
- tenant archived;
- masing-masing memiliki user dan password valid.

Gunakan identifier unik per tenant untuk test login status langsung.

Contoh struktur return:

```python
{
    "active": {"tenant": active_tenant, "user": active_user},
    "suspended": {"tenant": suspended_tenant, "user": suspended_user},
    "archived": {"tenant": archived_tenant, "user": archived_user},
    "password": "ValidPass123!",
}
```

### `ambiguous_tenant_hint_context`

Fixture khusus tenant hint:

- tenant active dan tenant suspended;
- kedua tenant memiliki user dengan identifier login yang sama;
- password dapat dibuat sama agar test fokus pada tenant status;
- username/email boleh sama karena uniqueness bersifat per tenant.

Tujuannya memastikan global `_resolve_user_for_login()` menghasilkan ambiguous result, sehingga tenant hint benar-benar menentukan tenant candidate.

### Helper `login_mobile`

Helper test lokal, bukan fixture wajib:

```python
def login_mobile(client, identifier, password, **tenant_hint):
    payload = {
        "identifier": identifier,
        "password": password,
        **tenant_hint,
    }
    return client.post("/api/v1/auth/login", json=payload)
```

### Helper `bearer_headers`

Menghasilkan:

```python
{"Authorization": f"Bearer {access_token}"}
```

## 8. Daftar test wajib

### TEST-001 — Login tenant active

Nama test:

`test_mobile_login_allows_active_tenant`

Setup:

- Buat tenant `ACTIVE`.
- Buat user dengan password valid dan `must_change_password=False`.

Action:

```http
POST /api/v1/auth/login
```

Body:

```json
{
  "identifier": "active-user",
  "password": "ValidPass123!"
}
```

Expected:

- HTTP `200`.
- `success is True`.
- `data.access_token` tersedia.
- `data.refresh_token` tersedia.
- `data.token_type == "Bearer"`.
- `data.user.id` dan `data.user.tenant_id` sesuai fixture.
- `last_login` terisi setelah request.
- Token dapat dipakai pada `GET /api/v1/auth/me`.

Tujuan regression:

Memastikan hardening tidak memblokir tenant active.

---

### TEST-002 — Login tenant suspended

Nama test:

`test_mobile_login_rejects_suspended_tenant`

Setup:

- Tenant `SUSPENDED`.
- User dan password valid.

Action:

`POST /api/v1/auth/login`

Expected:

- HTTP `403` sesuai kontrak yang disetujui.
- `success is False`.
- `code == "tenant_inactive"`.
- Tidak ada access/refresh token pada response.
- `user.last_login` tetap `None`.
- Tidak ada row token revocation baru sebagai side effect.

Current expected state:

Test ini seharusnya gagal sebelum remediation karena kode saat ini menerbitkan token.

---

### TEST-003 — Login tenant archived

Nama test:

`test_mobile_login_rejects_archived_tenant`

Setup:

- Tenant `ARCHIVED`.
- User dan password valid.

Action:

`POST /api/v1/auth/login`

Expected:

- HTTP `403`.
- `success is False`.
- `code == "tenant_inactive"`.
- Tidak ada token.
- `last_login` tidak berubah.

Current expected state:

Test ini seharusnya gagal sebelum remediation.

Implementasi test dapat diparameterisasi bersama TEST-002:

```python
@pytest.mark.parametrize(
    "tenant_status",
    [TenantStatus.SUSPENDED, TenantStatus.ARCHIVED],
)
```

Tetap gunakan test ID yang terbaca jelas pada output pytest.

---

### TEST-004 — Refresh token setelah tenant suspended

Nama test:

`test_mobile_refresh_rejects_token_after_tenant_is_suspended`

Setup:

1. Buat tenant `ACTIVE` dan user valid.
2. Login melalui API untuk memperoleh refresh token.
3. Ubah tenant menjadi `SUSPENDED` dan commit.

Action:

```http
POST /api/v1/auth/refresh
```

Body:

```json
{
  "refresh_token": "<token dari login active>"
}
```

Expected:

- HTTP `403`.
- `success is False`.
- `code == "tenant_inactive"`.
- Tidak ada token pair baru.
- Refresh token lama tidak perlu otomatis direvoke oleh test ini kecuali policy implementasi menyatakannya.

Current expected state:

Test ini seharusnya gagal sebelum remediation karena refresh saat ini hanya memeriksa user dan tenant claim.

Catatan:

Test memperoleh token saat tenant masih active agar kegagalan berasal dari lifecycle check pada refresh, bukan login.

---

### TEST-005 — Access token existing setelah tenant suspended

Nama test:

`test_mobile_access_token_is_rejected_after_tenant_is_suspended`

Setup:

1. Tenant awalnya `ACTIVE`.
2. Login dan ambil access token.
3. Verifikasi token bekerja pada `/api/v1/auth/me`.
4. Ubah tenant menjadi `SUSPENDED` dan commit.

Action:

```http
GET /api/v1/auth/me
Authorization: Bearer <access_token>
```

Expected:

- Sebelum suspension: HTTP `200`.
- Setelah suspension: HTTP `403`.
- `success is False`.
- `code == "tenant_inactive"`.
- Protected view tidak dijalankan dan user payload tidak dikembalikan.

Current expected state:

Assertion setelah suspension seharusnya gagal sebelum remediation karena decorator saat ini hanya memeriksa token dan kecocokan tenant ID.

Test tambahan yang disarankan:

Parametrisasikan final state dengan `SUSPENDED` dan `ARCHIVED` untuk membuktikan decorator memakai policy yang sama.

---

### TEST-006 — Tenant hint mengarah ke tenant suspended

Nama test utama:

`test_mobile_login_rejects_suspended_tenant_hint`

Setup:

- Tenant A berstatus `ACTIVE`.
- Tenant B berstatus `SUSPENDED`.
- User A dan B memiliki identifier yang sama sehingga lookup global ambiguous.
- Password valid untuk user tenant B.

Action:

Login dengan tenant hint tenant B.

Variant yang harus diparameterisasi:

1. JSON `tenant_id`
2. JSON `tenant_code`
3. JSON `tenant_slug`
4. Header `X-Tenant-Id`
5. Header `X-Tenant-Code`
6. Header `X-Tenant-Slug`

Expected:

- HTTP `403` atau kontrak generik yang disetujui.
- Tidak ada access/refresh token.
- User tenant suspended tidak memperoleh `last_login`.
- Hint tidak membuat tenant nonaktif menjadi candidate yang dapat diautentikasi.

Current expected state:

Test seharusnya gagal sebelum remediation karena `_resolve_tenant_hint()` saat ini menerima tenant nonaktif.

Catatan penting:

Identifier harus ambiguous lintas tenant. Jika identifier suspended user unik secara global, login path dapat menemukan user tersebut sebelum tenant hint dipakai sehingga test tidak secara spesifik membuktikan behavior `_resolve_tenant_hint()`.

## 9. Test tambahan yang direkomendasikan

Test berikut bukan enam acceptance test minimum, tetapi bernilai tinggi:

### Soft-deleted tenant

`test_mobile_login_rejects_soft_deleted_tenant`

Memastikan global soft-delete filter dan policy menghasilkan denial yang terkontrol, bukan token atau exception.

### Active tenant hint

`test_mobile_login_accepts_active_tenant_hint_for_ambiguous_identifier`

Control test untuk TEST-006: identifier ambiguous dengan hint active harus berhasil.

### Tenant claim mismatch

Pertahankan regression bahwa token dengan `tid` berbeda dari `user.tenant_id` tetap menghasilkan `401 unauthorized`.

### Invalid credential precedence

Pastikan password salah tidak mengungkap status tenant. Expected tetap `invalid_credentials`.

### Missing tenant

Jika kondisi dapat direpresentasikan tanpa melanggar schema test, pastikan policy fail closed. Karena `User.tenant_id` non-null, test ini kemungkinan lebih cocok sebagai unit test helper atau fixture dengan tenant soft-delete.

## 10. Assertion side effects

Untuk denied request, test tidak hanya memeriksa HTTP response:

- tidak ada access/refresh token pada response;
- `last_login` tidak berubah;
- tidak ada protected user data;
- tidak ada token pair baru yang dapat dipakai;
- tidak ada commit perubahan user yang tidak relevan.

Untuk refresh denial, hindari assertion terhadap internal token string kecuali diperlukan. Fokus pada tidak diterbitkannya token baru melalui response.

## 11. Urutan implementasi test

1. Buat fixture app/client/factory.
2. Buat TEST-001 sebagai positive control.
3. Buat TEST-002 dan TEST-003 sebagai login policy tests.
4. Buat TEST-004 untuk refresh.
5. Buat TEST-005 untuk decorator/protected endpoint.
6. Buat active-hint control test.
7. Buat TEST-006 dengan enam hint variants.
8. Tambahkan soft-deleted tenant dan invalid-password tests.
9. Jalankan file test secara terisolasi.
10. Setelah remediation, jalankan seluruh pytest suite.

## 12. Command verifikasi yang direncanakan

Sebelum kode diperbaiki, test security baru diharapkan merah pada kasus nonaktif:

```powershell
pytest tests/test_mobile_auth_tenant_status.py -q
```

Setelah remediation:

```powershell
pytest tests/test_mobile_auth_tenant_status.py -q
pytest tests -q
```

Tidak perlu menjalankan migration. Test memakai schema hasil `db.create_all()` pada SQLite in-memory.

## 13. Risiko dan batas test

- SQLite tidak membuktikan PostgreSQL enum/migration behavior.
- Test ini tidak membuktikan rate limiting atau package enforcement.
- Global soft-delete event listener terdaftar saat `create_app()`; fixture harus memastikan cleanup session konsisten.
- Exact status/error code harus disepakati sebelum test dijadikan kontrak.
- Exception `SUPER_ADMIN` belum ditentukan dan tidak boleh diasumsikan dalam implementasi test utama.
- Test tenant hint dapat memberi hasil keliru jika identifier tidak benar-benar ambiguous; fixture khusus wajib digunakan.

## 14. Definition of Done untuk fase test

- Enam test wajib tersedia dan memiliki nama yang jelas.
- Positive control tenant active lulus.
- Sebelum remediation, test suspended/archived/refresh/access/hint gagal karena gap yang tepat.
- Setelah remediation, seluruh test dalam file lulus.
- Full pytest suite tetap lulus.
- Tidak ada migration atau data production yang digunakan.
- Hasil test dan root cause setiap kegagalan dicatat pada review implementasi AUTH-TENANT-001.

