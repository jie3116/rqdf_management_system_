# AUTH-REFRESH-006 Impact Analysis

Tanggal: 2026-06-29

Status: `ANALYSIS COMPLETE - READY FOR HUMAN DESIGN DECISION`

## 1. Scope

Analysis ini mencakup:

- mobile refresh token flow;
- refresh token issuance;
- refresh token revocation;
- logout revocation;
- token claim dan `jti`;
- kemungkinan race saat dua refresh request memakai refresh token yang sama;
- interaksi refresh flow dengan `users.token_version` dari `AUTH-TOKEN-005`.

Out of scope:

- implementasi;
- migration;
- deploy;
- perubahan web session;
- tenant/package/rate-limit remediation lain;
- `TENANT-DATA-006`.

## 2. Current Flow Inventory

File yang diaudit:

- `app/routes/api/auth.py`
- `app/routes/api/common.py`
- `app/utils/mobile_api_auth.py`
- `app/models.py`
- `migrations/versions/m3b4c5d6e7f8_add_mobile_auth_state_tables.py`
- `tests/test_mobile_auth_tenant_status.py`
- `tests/test_mobile_token_version_invalidation.py`

Catatan helper:

- Tidak ada source file `app/utils/mobile_security.py` saat audit ini. Hanya ada artefak `__pycache__` lama, sehingga flow aktif yang terbaca memakai `app/utils/mobile_api_auth.py`.

### Mobile Login

Flow:

1. `POST /api/v1/auth/login` membaca identifier, password, dan tenant hint.
2. Login rate limit dicek melalui `check_auth_rate_limit("mobile_login", ...)`.
3. User di-resolve melalui `_resolve_user_for_login()` dan tenant-aware fallback.
4. Password dicek dengan `user.check_password(password)`.
5. Tenant lifecycle dicek dengan `is_user_tenant_active(user)`.
6. `must_change_password` ditolak.
7. `issue_mobile_token_pair(user)` menerbitkan access token dan refresh token.
8. `user.last_login` diupdate, lalu `db.session.commit()`.

Token issuance:

- `issue_mobile_token(user, token_type)` menambahkan claim:
  - `uid`
  - `tid`
  - `typ`
  - `jti`
  - `ver`
- `jti` dibuat dengan `uuid.uuid4().hex`.
- `ver` berasal dari `int(user.token_version or 0)`.

### Mobile Refresh

Flow:

1. `POST /api/v1/auth/refresh` menerima `refresh_token`.
2. `decode_mobile_token(refresh_token, TOKEN_TYPE_REFRESH)` dipanggil.
3. `decode_mobile_token()` membersihkan revoked token expired, mengecek revoked token by token hash, memvalidasi signature, TTL, `typ`, dan `uid`.
4. User dimuat dari `payload.uid`.
5. Tenant claim `payload.tid` dicocokkan dengan `user.tenant_id`.
6. `validate_mobile_token_version(refresh_payload, user)` mengecek claim `ver`.
7. Tenant lifecycle dicek dengan `is_user_tenant_active(user)`.
8. Token pair baru diterbitkan dengan `issue_mobile_token_pair(user)`.
9. Old refresh token direvoke dengan `revoke_mobile_token(refresh_token, TOKEN_TYPE_REFRESH, expires_at=tokens["refresh_expires_at"])`.
10. `db.session.commit()`.
11. Response sukses berisi access token baru, refresh token baru, dan user payload.

### Mobile Logout

Flow:

1. `POST /api/v1/auth/logout` memakai `@mobile_auth_required()`, sehingga access token divalidasi lebih dulu.
2. Access token saat ini direvoke dengan `revoke_mobile_token(g.mobile_access_token, TOKEN_TYPE_ACCESS)`.
3. Jika request body membawa `refresh_token`, token itu direvoke dengan `revoke_mobile_token(refresh_token, TOKEN_TYPE_REFRESH)`.
4. `db.session.commit()`.

Catatan:

- Logout tidak decode refresh token sebelum revocation.
- Revocation menyimpan hash token penuh, bukan `jti`.
- Test `test_logout_still_uses_mobile_revoked_tokens` membuktikan logout membuat dua row revoked token dan access token lama ditolak.

### Protected Mobile Access

Flow:

1. `mobile_auth_required()` mengambil Bearer access token.
2. `decode_mobile_token(access_token, TOKEN_TYPE_ACCESS)` memvalidasi token dan revoked list.
3. User dimuat dari `payload.uid`.
4. Tenant claim dicocokkan.
5. `validate_mobile_token_version(payload, user)` mengecek `ver`.
6. Tenant lifecycle dicek.
7. Role/capability check dijalankan sesuai decorator.

### Password Change Invalidation dari AUTH-TOKEN-005

`AUTH-TOKEN-005` menambahkan:

- `users.token_version`;
- claim `ver` pada mobile token;
- validation `payload.ver == user.token_version`;
- bump token version pada password change/reset existing user.

Efek pada refresh:

- Refresh token lama sebelum password change memiliki `ver` lama.
- Setelah password change, `validate_mobile_token_version()` menolak refresh token lama dengan controlled `401`.
- Ini tidak menyelesaikan race antar dua refresh request yang sama-sama memakai refresh token valid dengan `ver` yang masih current.

## 3. Current Refresh Behavior

### Apakah refresh token punya `jti`?

Ya.

`issue_mobile_token()` memasukkan `jti = uuid.uuid4().hex` untuk access dan refresh token.

Namun:

- `jti` tidak dipersist;
- `jti` tidak dipakai dalam revocation lookup;
- `jti` tidak punya unique constraint di database;
- revocation memakai SHA-256 hash dari token string penuh.

### Apakah refresh token lama direvoke saat refresh?

Ya.

`auth_refresh()` memanggil:

```python
revoke_mobile_token(
    refresh_token,
    TOKEN_TYPE_REFRESH,
    expires_at=tokens["refresh_expires_at"],
)
```

### Kapan revoke dilakukan?

Revoke dilakukan setelah token pair baru diterbitkan, sebelum `db.session.commit()`.

Urutan saat ini:

1. old refresh token didecode dan dinyatakan valid;
2. user, tenant claim, token version, dan tenant lifecycle valid;
3. token pair baru dibuat;
4. old refresh token ditambahkan ke revoked list;
5. transaksi di-commit;
6. response sukses dikirim.

### Apakah revoke operation atomic?

Belum cukup atomic untuk refresh-token consume.

`revoke_mobile_token()` melakukan pola check-then-insert:

1. hitung `token_hash`;
2. query existing row berdasarkan `token_hash`;
3. jika ada, return `False`;
4. jika tidak ada, `db.session.add(MobileRevokedToken(...))`;
5. caller melakukan commit.

Dalam request paralel, dua transaksi dapat sama-sama tidak melihat row existing, lalu sama-sama mencoba insert hash yang sama.

### Apakah ada unique constraint untuk revoked token/JTI?

Ada unique constraint untuk `mobile_revoked_tokens.token_hash`.

Evidence:

- Model `MobileRevokedToken.token_hash` adalah `unique=True, index=True`.
- Migration `m3b4c5d6e7f8_add_mobile_auth_state_tables.py` membuat `sa.UniqueConstraint("token_hash")` dan unique index `ix_mobile_revoked_tokens_token_hash`.

Tidak ada constraint untuk `jti` karena `jti` tidak dipersist.

### Apa yang terjadi jika dua refresh request paralel memakai refresh token sama?

Kemungkinan behavior saat ini:

1. Jika request kedua mulai setelah request pertama commit, `decode_mobile_token()` melihat old refresh token sudah revoked dan mengembalikan controlled `401`.
2. Jika dua request berjalan paralel dan sama-sama melewati `decode_mobile_token()` sebelum revoked row commit:
   - keduanya dapat menerbitkan token pair baru di memory;
   - keduanya memanggil `revoke_mobile_token()` dan sama-sama tidak menemukan row existing;
   - keduanya mencoba insert `token_hash` yang sama;
   - karena unique constraint, hanya satu commit yang seharusnya sukses di PostgreSQL;
   - request lain berisiko mendapat `IntegrityError` pada commit jika tidak ditangani, sehingga bisa menjadi `500` alih-alih controlled `401`.

Kesimpulan:

- Tidak ada bukti kuat bahwa dua request paralel akan dua-duanya sukses di PostgreSQL karena unique constraint pada `token_hash`.
- Namun operation belum didesain sebagai atomic consume dengan error handling yang mengubah duplicate consume menjadi controlled unauthorized response.
- Race window tetap ada pada level application flow: validasi revoked dilakukan sebelum insert revoke old refresh token dipastikan committed.

### Apakah ada window di mana keduanya bisa lolos sebelum token lama masuk revoked list?

Ya, ada window antara:

- `decode_mobile_token()` memutuskan token belum revoked; dan
- insert revoke old refresh token berhasil commit.

Dalam window itu, request paralel dapat melewati validation awal. Unique constraint membantu mencegah duplicate revoked row, tetapi current route belum memastikan second request gagal secara terkontrol.

### Apakah `users.token_version` membantu case ini?

Tidak untuk race refresh token valid yang sama.

`users.token_version` membantu:

- replay after password change;
- strict cutover token lama tanpa `ver`;
- stale token setelah credential mutation.

`users.token_version` tidak berubah pada normal refresh. Dua request paralel dengan refresh token yang sama dan `ver` yang masih current akan sama-sama lolos token-version check sampai old refresh token berhasil dikonsumsi/revoked secara atomic.

## 4. Risk Analysis

| Risk | Severity | Analysis |
| --- | --- | --- |
| Refresh token reuse setelah refresh sukses | MEDIUM | Sequential reuse kemungkinan ditolak karena old token masuk revoked list. Namun perlu test eksplisit untuk memastikan response controlled `401`. |
| Refresh token race condition | MEDIUM | Parallel requests dapat sama-sama melewati pre-check. Unique constraint mencegah duplicate revoked row, tetapi second request dapat menjadi `IntegrityError`/500 jika tidak ditangani. |
| Replay after logout | LOW | Logout merevoke access token dan optional refresh token. Replay setelah logout ditolak jika refresh token dikirim saat logout. Jika client tidak mengirim refresh token saat logout, refresh token tetap hidup. |
| Replay after password change | LOW | AUTH-TOKEN-005 menolak refresh token stale via `ver`, termasuk refresh token lama setelah password change. |
| DB uniqueness/integrity issue | MEDIUM | Unique `token_hash` ada, tetapi current check-then-insert tidak menangani duplicate insert race sebagai expected unauthorized result. |
| User experience impact | LOW-MEDIUM | Hardening one-time refresh bisa membuat retry jaringan dengan refresh token yang sama menerima `401`, memaksa client memakai token baru atau login ulang. Perlu response contract stabil. |
| Compatibility mobile client existing | MEDIUM | Jika client saat ini melakukan duplicate refresh/retry otomatis, one-time refresh strict dapat memunculkan logout lebih sering. Desain perlu mempertimbangkan idempotency window atau controlled error. |

## 5. Design Options

### Option A - Keep Stateless JWT + Harden Revoked-Token Consume

Desain:

- Tetap memakai JWT/itsdangerous refresh token seperti sekarang.
- Refresh token tetap one-time use secara efektif.
- Saat refresh, old refresh token harus di-consume/revoke secara atomic sebelum atau bersamaan dengan issuance token baru.
- Pakai `mobile_revoked_tokens.token_hash` existing sebagai consume marker.
- Tangani duplicate insert / unique violation sebagai controlled `401 unauthorized`.
- Pertimbangkan helper baru, misalnya `consume_refresh_token_once(refresh_token, expires_at)`:
  - insert revoked row;
  - flush/commit dalam transaksi caller;
  - jika duplicate key, rollback bagian aman dan return consumed/reused;
  - jangan menerbitkan token baru untuk request yang gagal consume.

Kelebihan:

- Scope kecil.
- Bisa memakai tabel existing.
- Kemungkinan tidak perlu migration karena `token_hash` sudah unique.
- Compatible dengan token format existing.
- Cocok sebagai Phase 1 hardening.

Kekurangan:

- Tidak punya token family/session state.
- Reuse detection hanya tahu token ini sudah consumed/revoked, bukan device/family mana yang harus dicabut.
- Sulit menerapkan "revoke all descendants" jika refresh token hasil race sudah sempat diterbitkan.
- Perlu desain transaksi hati-hati agar tidak commit side-effect lain secara tidak sengaja.

Migration impact:

- Tidak perlu migration jika cukup memakai `mobile_revoked_tokens.token_hash`.
- Perlu verifikasi production constraint/index tetap ada.

### Option B - Server-Side Refresh Session Table

Desain:

- Buat tabel refresh session/token family.
- Refresh token membawa `jti`/session id yang dipersist.
- Setiap refresh token adalah one-time use.
- Atomic update status dari `active` ke `consumed`.
- Jika reuse terdeteksi, revoke token family dan optional logout semua device pada family itu.
- Bisa menyimpan metadata aman:
  - user id;
  - tenant id;
  - token family id;
  - refresh token hash/JTI;
  - issued_at;
  - expires_at;
  - consumed_at;
  - revoked_at;
  - replaced_by_jti;
  - reuse_detected_at;
  - device id jika tersedia.

Kelebihan:

- Model paling kuat untuk refresh rotation.
- Reuse detection jelas.
- Bisa revoke seluruh token family.
- Lebih mudah audit security event.
- Cocok untuk policy multi-device jangka panjang.

Kekurangan:

- Butuh migration baru.
- Implementasi lebih besar.
- Perlu rollout dan rollback plan.
- Perlu compatibility strategy untuk refresh token yang sudah beredar.
- Menambah state per refresh token dan cleanup job/retention policy.

Migration impact:

- Perlu tabel baru, index, unique constraint, dan kemungkinan backfill/strict cutover.

### Option C - Shorter TTL + Existing Revocation Only

Desain:

- Pertahankan flow sekarang.
- Perpendek refresh token TTL.
- Mungkin tambahkan monitoring/logging untuk reuse.

Kelebihan:

- Paling kecil.
- Tidak butuh migration.
- Risiko kompatibilitas rendah.

Kekurangan:

- Tidak menyelesaikan race.
- Tidak menjamin one-time use secara terkontrol.
- Tidak mencegah `IntegrityError` pada duplicate insert race.
- Hanya mengurangi durasi exposure.

Assessment:

- Tidak cukup sebagai security hardening utama untuk `AUTH-REFRESH-006`.
- Bisa menjadi mitigasi operasional tambahan, bukan remediation final.

## 6. Recommended Direction

Rekomendasi awal: **Option A untuk Phase 1**, dengan desain yang membuka jalan ke Option B jika kebutuhan audit/session family meningkat.

Alasan:

- Codebase sudah memiliki `MobileRevokedToken` dan unique constraint `token_hash`.
- Token format existing sudah memiliki `jti`, tetapi current revocation berbasis token hash sudah cukup untuk one-time consume Phase 1.
- Tidak perlu langsung menambah migration jika tujuan Phase 1 adalah menutup uncontrolled duplicate refresh/reuse.
- Bisa dibuat testable:
  - sequential reuse;
  - simulated duplicate consume;
  - IntegrityError handling;
  - concurrency test pada PostgreSQL/integration environment.
- Lebih rendah risiko rollout dibanding server-side refresh session.
- Compatible dengan `AUTH-TOKEN-005` karena tetap validasi `ver` sebelum token baru dianggap sah.

Catatan desain penting untuk Option A:

- Consume old refresh token harus terjadi sebelum token pair baru dikembalikan sebagai sukses.
- Jika consume gagal karena token sudah revoked/duplicate key, response harus controlled `401 unauthorized`.
- Jangan membuat dua token pair sukses dari satu refresh token.
- Perlu mempertimbangkan transaction ordering agar token baru tidak dikembalikan jika consume old token gagal.
- Jika duplicate key terjadi saat flush/commit, rollback harus aman dan response tidak boleh `500`.

Kapan pilih Option B:

- Jika human decision mengharuskan token family, device-level session management, reuse detection yang memutus seluruh family, atau audit trail refresh yang lebih kuat.
- Jika production incident model membutuhkan kemampuan "logout all devices on reuse detected".

Option C tidak direkomendasikan sebagai remediation utama.

## 7. Human Decisions Needed

Sebelum implementation gate, keputusan manusia yang dibutuhkan:

1. Apakah refresh token harus one-time use secara ketat.
2. Apakah Phase 1 cukup memakai `MobileRevokedToken` existing untuk atomic consume.
3. Apakah reuse detection harus revoke seluruh token family.
4. Apakah perlu server-side refresh session table.
5. Apakah migration baru diterima untuk Phase 1, atau Phase 1 harus no-migration.
6. TTL access token target.
7. TTL refresh token target.
8. Response contract untuk refresh token reuse/race:
   - `401 unauthorized` dengan message generik;
   - apakah code tetap `unauthorized` atau code baru seperti `token_reused`.
9. Apakah semua device user ikut logout jika reuse terdeteksi.
10. Apakah client mobile dapat menangani strict one-time refresh dan retry failure.
11. Apakah token family/session audit diperlukan untuk compliance/forensics.

## 8. Test Plan

Test plan tanpa implementasi.

### Existing Behavior Characterization

1. Valid refresh token menghasilkan token pair baru.
   - Login mobile.
   - POST `/api/v1/auth/refresh` dengan refresh token.
   - Assert `200`, access token baru, refresh token baru.

2. Refresh token lama tidak bisa dipakai ulang setelah refresh sukses.
   - Login mobile.
   - Refresh sekali dan simpan response sukses.
   - Refresh lagi dengan refresh token lama.
   - Expected: controlled `401 unauthorized`.
   - Assert tidak ada `500`.

3. Refresh token baru dari refresh pertama tetap bisa dipakai.
   - Refresh dengan token baru.
   - Expected: `200`, kecuali policy human memutuskan additional restrictions.

### Race / Concurrency Tests

4. Dua refresh request dengan token sama tidak boleh dua-duanya sukses.
   - Gunakan dua client/session atau thread test.
   - Jalankan dua POST `/api/v1/auth/refresh` hampir bersamaan dengan refresh token yang sama.
   - Expected:
     - maksimal satu response `200`;
     - response lain controlled `401 unauthorized`;
     - tidak ada `500`;
     - tidak ada dua token pair sukses.

5. Duplicate consume database behavior.
   - Simulasikan insert duplicate `MobileRevokedToken.token_hash`.
   - Jika Option A dipilih, helper consume harus mengubah duplicate key menjadi failure terkontrol.
   - Expected: no unhandled `IntegrityError`.

6. PostgreSQL-specific concurrency strategy.
   - SQLite in-memory test mungkin tidak cukup untuk race.
   - Tambahkan integration/concurrency test yang bisa dijalankan pada PostgreSQL CI/dev container bila tersedia.
   - Minimal unit test dapat mock/force `IntegrityError` untuk memastikan response path controlled.

### Revocation Tests

7. Refresh token yang sudah logout/revoked ditolak.
   - Login mobile.
   - Logout dengan access token dan refresh token.
   - POST refresh dengan token lama.
   - Expected: `401 unauthorized`.

8. Logout tanpa refresh token tidak merevoke refresh token.
   - Karakterisasi current behavior jika diperlukan.
   - Human decision needed apakah mobile logout wajib menyertakan refresh token atau server harus mampu revoke all current refresh sessions.

### AUTH-TOKEN-005 Compatibility Tests

9. Refresh token setelah password change/token_version bump ditolak.
   - Login mobile.
   - Bump token version melalui password change helper.
   - POST refresh dengan token lama.
   - Expected: controlled `401` dengan message session expired.

10. Refresh token missing `ver` ditolak.
    - Buat legacy refresh token tanpa `ver`.
    - Expected: controlled `401`, bukan `500`.

11. Refresh token stale `ver` ditolak.
    - Buat token dengan `ver` lebih rendah dari user current.
    - Expected: controlled `401`.

12. Refresh token non-integer `ver` ditolak.
    - Buat token dengan `ver = "abc"`.
    - Expected: controlled `401`.

### Error Contract Tests

13. Invalid/malformed refresh token ditolak controlled `401`.
    - Missing signature, random string, wrong serializer payload.
    - Expected: `401`, no traceback.

14. Refresh token dengan wrong `typ` ditolak.
    - Kirim access token ke refresh endpoint.
    - Expected: `401`.

15. Refresh token untuk missing user ditolak.
    - Token payload uid tidak ada di DB.
    - Expected: `401`.

16. Refresh token dengan tenant mismatch ditolak.
    - Payload `tid` tidak sama dengan `user.tenant_id`.
    - Expected: `401`.

17. Tenant inactive tetap ditolak.
    - Login saat tenant active.
    - Suspend tenant.
    - Refresh token.
    - Expected: `403 tenant_inactive`.

### DB Integrity / Cleanup Tests

18. Revoked token unique constraint tetap ada.
    - Test model/migration characterization jika feasible.
    - Assert duplicate `token_hash` tidak menghasilkan dua row.

19. Expired revoked token cleanup tidak membuka token valid yang belum expired.
    - Pastikan cleanup hanya menghapus row `expires_at < now`.
    - Catatan: token expired sendiri tetap ditolak oleh serializer max_age.

20. Revocation `expires_at` behavior.
    - Characterize current refresh revoke memakai expiry token baru, bukan expiry token lama.
    - Decide apakah perlu diperbaiki di implementation phase.

## 9. Migration Impact

### Jika Memakai Existing `MobileRevokedToken`

Kemungkinan tidak perlu migration.

Alasan:

- Tabel `mobile_revoked_tokens` sudah ada dari migration `m3b4c5d6e7f8`.
- `token_hash` sudah `NOT NULL`, unique, dan indexed.
- `token_type`, `expires_at`, dan `created_at` sudah tersedia.

Tetap perlu verification gate:

- Pastikan production schema punya unique constraint/index pada `token_hash`.
- Pastikan duplicate insert behavior PostgreSQL dipahami dan ditangani.
- Pastikan implementation tidak bergantung pada SQLite-only behavior.

### Jika Memakai Server-Side Refresh Session

Perlu migration baru.

Kemungkinan tabel:

- `mobile_refresh_sessions` atau `mobile_refresh_tokens`

Kemungkinan kolom:

- `id`
- `user_id`
- `tenant_id`
- `family_id`
- `jti`
- `token_hash`
- `status`
- `issued_at`
- `expires_at`
- `consumed_at`
- `revoked_at`
- `replaced_by_jti`
- `reuse_detected_at`
- `device_token_id` atau device metadata opsional
- `created_at`
- `updated_at`

Kemungkinan constraint/index:

- unique `jti`
- unique `token_hash`
- index `user_id`
- index `family_id`
- index `expires_at`
- index `(user_id, status)`

Migration risk:

- Perlu rollout/cutover strategy untuk refresh token existing.
- Perlu cleanup/retention policy.
- Perlu rollback plan.
- Perlu production backup dan lock assessment.

## 10. Final Status

`ANALYSIS COMPLETE - READY FOR HUMAN DESIGN DECISION`

Recommended option for Phase 1:

- **Option A - Keep stateless JWT + harden revoked-token consume**

Human decision required before implementation:

- Confirm whether AUTH-REFRESH-006 Phase 1 must be no-migration with `MobileRevokedToken`, or whether server-side refresh session table is approved.
