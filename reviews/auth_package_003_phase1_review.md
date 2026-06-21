# AUTH-PACKAGE-003 Phase 1 Review Gate

Tanggal: 2026-06-21  
Mode: Security Reviewer Agent, Code Review Agent, Testing & QA Agent  
Scope: file berubah pada AUTH-PACKAGE-003 Phase 1, helper capability baru, mobile capability enforcement, dan test baru.  
Keputusan akhir: **REQUEST CHANGES**

## Findings

### MEDIUM - `tenant_has_capability()` belum fail-closed untuk `tenant_id=None`

File:

- `app/utils/tenant_modules.py`

Evidence:

- `tenant_has_capability(tenant_id, capability)` memanggil `get_tenant_package(tenant_id)`.
- `get_tenant_package(None)` mengembalikan `PACKAGE_FULL`.
- Karena `PACKAGE_FULL` dipetakan ke `ALL_CAPABILITIES`, maka caller yang tidak sengaja mengirim `tenant_id=None` akan mendapat semua capability.

Impact:

- Pada mobile path saat ini, risiko langsung tertahan karena `mobile_auth_required()` sudah memvalidasi user, token tenant claim, dan `is_user_tenant_active(user)` sebelum capability check. Model `User.tenant_id` juga non-null.
- Namun helper ini dirancang reusable untuk authorization jangka panjang. Kontrak `tenant_has_capability(tenant, capability)` seharusnya fail-closed untuk tenant yang tidak resolved.

Recommendation:

- Ubah helper agar `tenant_id is None` mengembalikan `False` bila `capability` diisi.
- Tambahkan characterization test: `tenant_has_capability(None, CAPABILITY_TEACHER) is False`.
- Pertahankan compatibility "tenant tanpa config default ke full" hanya untuk tenant_id valid yang row config-nya tidak ada, bukan untuk missing tenant context.

### LOW - Allowed-case tests belum membuktikan endpoint berhasil secara domain-level

File:

- `tests/test_mobile_package_capabilities.py`

Evidence:

- Allowed tests memakai `assert_not_capability_disabled(response)`.
- Dengan fixture minimal tanpa profile guru/asrama/majlis, endpoint allowed bisa tetap `404 not_found`, tetapi test tetap lulus selama bukan `403 capability_disabled`.

Impact:

- Test sudah cukup membuktikan package gate tidak memblokir allowed package.
- Test belum membuktikan endpoint benar-benar usable setelah gate karena domain fixture tidak dibuat.

Recommendation:

- Untuk Phase 1, ini acceptable sebagai characterization package gate.
- Untuk hardening berikutnya, tambahkan fixture domain minimal atau test helper/decorator level agar allowed case bisa assert status yang lebih kuat.

### LOW - SUPER_ADMIN bypass capability belum punya regression test eksplisit

File:

- `app/routes/api/common.py`
- `tests/test_mobile_package_capabilities.py`

Evidence:

- Implementasi: capability check dilewati jika `user.has_role("super_admin")`.
- Tenant lifecycle check tetap berjalan sebelum bypass.
- Tidak ada test yang membuktikan super admin dengan tenant aktif melewati capability check, dan tenant nonaktif tetap ditolak.

Impact:

- Behavior implementasi sesuai keputusan bisnis sejauh dibaca dari kode.
- Tanpa test, regression pada bypass ordering bisa lolos.

Recommendation:

- Tambahkan test kecil untuk user `SUPER_ADMIN` pada tenant aktif/nonaktif jika super admin mobile memang didukung.
- Jika super admin mobile tidak dipakai, dokumentasikan sebagai residual risk dan jangan perluas scope sekarang.

## Review Checklist

1. `tenant_has_capability()` fail-closed: **REQUEST CHANGES**. Unknown capability fail-closed, tetapi `tenant_id=None` fail-open ke `full`.
2. Legacy adapter sesuai matrix v2: **OK**. `full -> all capabilities`, `sekolah -> school capabilities`, `rumah_quran -> quran capabilities`.
3. SUPER_ADMIN bypass: **OK with test gap**. Bypass hanya capability check; token/user/tenant lifecycle dan role check tetap berjalan.
4. Auth/common endpoint: **OK**. Auth routes tidak diberi capability; `mobile_auth_required()` default `capability=None` menjaga behavior common/auth.
5. Teacher/boarding/majlis mobile enforcement: **OK**. Semua route pada tiga file diberi capability eksplisit.
6. Endpoint tertinggal: **OK** berdasarkan scan `@api_bp` dan `@mobile_auth_required`; tidak ada teacher/boarding/majlis endpoint tanpa capability.
7. Response API: **OK**. Disabled capability memakai `403` dan code `capability_disabled`; konsisten dalam patch ini.
8. Test denied/allowed: **PARTIAL**. Denied cases kuat; allowed cases hanya membuktikan tidak diblokir capability gate.
9. Risiko web guard existing: **LOW**. Web behavior tidak diubah; helper baru belum dipakai web guard.
10. Perubahan di luar scope: **OK**. Tidak ada enforcement parent, finance, PPDB, online class, AI assistant, analytics, atau announcement.

## Test Evidence

Command:

```powershell
$env:PYTHONPATH='.'; .\.venv\Scripts\pytest.exe tests/test_mobile_package_capabilities.py -q
```

Result:

```text
12 passed
```

Command:

```powershell
$env:PYTHONPATH='.'; .\.venv\Scripts\pytest.exe tests/test_mobile_auth_tenant_status.py -q
```

Result:

```text
11 passed
```

Command:

```powershell
$env:PYTHONPATH='.'; .\.venv\Scripts\pytest.exe -q
```

Result:

```text
36 passed, 1 failed
```

Full-suite failure:

- `tests/test_finance_core.py::test_reverse_journal_creates_opposite_lines_and_voids_cash_bank_source`
- Root cause observed: `reverse_journal()` uses `date.today()` for posting context. Current date is 2026-06-21, while the finance fixture does not create an accounting period for that date, causing `ValueError: Periode akuntansi belum dibuat.`
- This appears unrelated to AUTH-PACKAGE-003, but the full suite is not green.

## Security Reviewer Decision

**REQUEST CHANGES**

Reason:

- The helper intended as reusable authorization policy is not fail-closed for missing tenant context.

## Code Review Decision

**REQUEST CHANGES**

Reason:

- Implementation is scoped and clean, but helper contract should be tightened before commit/deploy.

## Testing & QA Decision

**REQUEST CHANGES**

Reason:

- Relevant AUTH-PACKAGE-003 tests pass.
- Add at least one regression test for `tenant_has_capability(None, capability)`.
- Full suite has one unrelated finance failure that must be tracked before release.

## Final Decision

**REQUEST CHANGES**

Minimum requested fix before approval:

1. Make `tenant_has_capability(None, <capability>)` return `False`.
2. Add a regression test for missing tenant context.
3. Re-run:
   - `tests/test_mobile_package_capabilities.py`
   - `tests/test_mobile_auth_tenant_status.py`

Full-suite finance failure can be tracked separately if human owner accepts it as unrelated to AUTH-PACKAGE-003.

