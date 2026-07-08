# AUTH-REFRESH-006 Design Decision

Tanggal: 2026-07-08

Status: `DESIGN DECISION APPROVED BY HUMAN - OPTION B`

## 1. Decision Summary

AUTH-REFRESH-006 Phase 1 akan memakai **server-side refresh token rotation** dengan migration baru.

Keputusan desain:

- Refresh token strict one-time use.
- Setiap mobile login membuat refresh token family baru.
- Setiap refresh sukses:
  - consume refresh token lama secara atomic;
  - issue access token baru;
  - issue refresh token baru;
  - simpan refresh token baru sebagai `ACTIVE`;
  - hubungkan token lama ke token baru melalui `replaced_by_jti`.
- Jika refresh token lama yang sudah `CONSUMED` atau `REVOKED` dipakai ulang:
  - return controlled `401 unauthorized`;
  - tandai `reuse_detected_at` jika memungkinkan;
  - revoke seluruh token family.
- Existing refresh token production yang belum punya server-side row akan ditolak setelah deploy.
- Strict cutover diterima; mobile users mungkin perlu login ulang.

Tidak berubah:

- Web session tidak diubah.
- `AUTH-TOKEN-005` token_version behavior tidak diubah.
- Tenant/package/rate-limit remediation lain tidak disentuh.

## 2. Why Option B

Option B dipilih karena:

- Lebih kuat daripada revoked-list-only hardening.
- Menyelesaikan one-time refresh token dengan model state eksplisit.
- Mendukung reuse detection secara jelas.
- Mendukung revoke seluruh token family saat reuse terdeteksi.
- Mendukung audit trail untuk issued/consumed/revoked/reused token.
- Cocok untuk kondisi saat ini karena jumlah tenant production masih satu, sehingga migration dan strict cutover lebih manageable.
- Memberi fondasi untuk device/session management jangka panjang tanpa mengubah behavior `AUTH-TOKEN-005`.

## 3. Rejected Alternatives

### Option A - Keep Stateless JWT + Harden Revoked-Token Consume

Ditolak sebagai solusi utama.

Alasan:

- Masih berbasis revoked list.
- Tidak punya token family/session state.
- Reuse detection terbatas pada token individual.
- Sulit melakukan revoke seluruh chain/family secara eksplisit.
- Audit trail refresh rotation tidak sekuat model server-side.

Option A tetap berguna sebagai referensi rollback desain kecil, tetapi bukan arah AUTH-REFRESH-006 setelah keputusan manusia terbaru.

### Option C - Shorter TTL + Existing Revocation Only

Ditolak.

Alasan:

- Shorter TTL tidak menyelesaikan race/reuse.
- Hanya mengurangi exposure window.
- Tidak memberikan strict one-time refresh token.
- Tidak mendukung reuse detection atau token family revocation.

## 4. Proposed Data Model

Usulan model/tabel baru: `MobileRefreshToken`

Usulan table name: `mobile_refresh_tokens`

Kolom minimal:

| Column | Type | Notes |
| --- | --- | --- |
| `id` | integer primary key | Internal row id |
| `user_id` | integer, not null | FK ke `users.id` jika migration gate menyetujui FK |
| `tenant_id` | integer, nullable atau not null sesuai user policy | FK ke `tenants.id` jika migration gate menyetujui FK |
| `family_id` | string/uuid, not null | Satu family per mobile login |
| `jti` | string, not null | Token identifier dari refresh token |
| `token_hash` | string(64), not null | SHA-256/HMAC hash dari refresh token string |
| `status` | string, not null | `ACTIVE`, `CONSUMED`, `REVOKED`, `REUSED` |
| `issued_at` | datetime, not null | Waktu token diterbitkan |
| `expires_at` | datetime, not null | Expiry refresh token |
| `consumed_at` | datetime, nullable | Diisi saat refresh sukses mengonsumsi token |
| `revoked_at` | datetime, nullable | Diisi saat logout/family revoke |
| `replaced_by_jti` | string, nullable | JTI refresh token baru hasil rotation |
| `reuse_detected_at` | datetime, nullable | Diisi saat reuse token terdeteksi |
| `created_at` | datetime, not null | Audit timestamp |
| `updated_at` | datetime, not null | Audit timestamp |

Constraint/index minimal:

- unique `jti`
- unique `token_hash`
- index `user_id`
- index `tenant_id`
- index `family_id`
- index `status`
- index `expires_at`
- optional composite index `(user_id, tenant_id, status)`

Catatan desain:

- `token_hash` tidak boleh menyimpan refresh token mentah.
- `family_id` dapat berupa UUID hex/string.
- `status` dapat memakai string enum DB atau string biasa. Pilihan final perlu diputuskan pada migration gate sesuai pola Alembic existing.

## 5. Status Semantics

Status refresh token:

- `ACTIVE`
  - Token belum dipakai, belum dicabut, dan belum expired.
  - Hanya status ini yang boleh dipakai untuk refresh sukses.

- `CONSUMED`
  - Token sudah berhasil dipakai untuk refresh.
  - `consumed_at` terisi.
  - `replaced_by_jti` menunjuk refresh token baru.
  - Reuse token ini harus ditolak dan memicu family revoke sesuai policy.

- `REVOKED`
  - Token dicabut karena logout, family revoke, admin/security event, atau cleanup policy.
  - `revoked_at` terisi.
  - Reuse token ini harus ditolak.

- `REUSED`
  - Token pernah dipakai ulang setelah tidak lagi active.
  - `reuse_detected_at` terisi.
  - Status ini dapat dipakai pada row token yang reused, atau reuse cukup ditandai dengan `reuse_detected_at` sambil family direvoke. Pilihan final perlu ditentukan di verification gate.

Expired token:

- Expiry dihitung dari `expires_at`.
- Tidak harus menjadi status tersendiri.
- Token dengan `expires_at <= now` ditolak meskipun status masih `ACTIVE`.

## 6. Token Claims

Refresh token tetap membawa claim:

- `uid`
- `tid`
- `typ`
- `jti`
- `ver`

Requirement:

- `typ` harus `refresh`.
- `jti` harus dipersist di `mobile_refresh_tokens`.
- Saat refresh, payload `jti` harus dicocokkan dengan row server-side.
- `token_hash` dari raw refresh token juga harus cocok dengan row server-side.
- `ver` tetap divalidasi terhadap `users.token_version` sesuai `AUTH-TOKEN-005`.

## 7. Flow Design

### Mobile Login

1. User login mobile berhasil.
2. Server membuat access token.
3. Server membuat refresh token dengan `jti` baru dan `ver = user.token_version`.
4. Server membuat `family_id` baru.
5. Server menyimpan row `mobile_refresh_tokens`:
   - `user_id`
   - `tenant_id`
   - `family_id`
   - `jti`
   - `token_hash`
   - `status = ACTIVE`
   - `issued_at`
   - `expires_at`
6. Response mengembalikan access token dan refresh token.

### Mobile Refresh Sukses

1. Decode refresh token.
2. Validasi signature, TTL, `typ`, `uid`, `tid`, dan `ver`.
3. Load user.
4. Validasi tenant claim.
5. Validasi tenant lifecycle.
6. Cari row server-side berdasarkan `jti` dan/atau `token_hash`.
7. Secara atomic consume row hanya jika:
   - `status = ACTIVE`;
   - `expires_at > now`;
   - `user_id` cocok;
   - `tenant_id` cocok;
   - `token_hash` cocok.
8. Jika consume berhasil:
   - set old row `status = CONSUMED`;
   - set `consumed_at = now`;
   - issue access token baru;
   - issue refresh token baru dengan `jti` baru;
   - insert row refresh token baru sebagai `ACTIVE` dengan family yang sama;
   - set old row `replaced_by_jti = new_jti`;
   - commit transaksi;
   - return token pair baru.
9. Jika consume gagal:
   - jangan issue/return token baru;
   - return controlled `401 unauthorized`.

### Refresh Token Reuse

Jika refresh token lama yang sudah `CONSUMED`, `REVOKED`, atau expired dipakai:

1. Decode token jika masih cryptographically valid.
2. Cari row server-side.
3. Jika row tidak `ACTIVE` atau expired:
   - set `reuse_detected_at` jika memungkinkan;
   - revoke seluruh token family;
   - return controlled `401 unauthorized`.

Family revoke:

- Semua row dengan `family_id` yang sama dan status `ACTIVE` diubah menjadi `REVOKED`.
- `revoked_at` diisi.
- Optional: row yang reused diberi status `REUSED` atau tetap status asal dengan `reuse_detected_at`.

### Mobile Logout

1. Access token tetap direvoke melalui `MobileRevokedToken` existing atau mekanisme existing yang sudah berjalan.
2. Jika request menyertakan refresh token:
   - cari row refresh token berdasarkan `jti`/`token_hash`;
   - revoke token atau seluruh family sesuai keputusan implementation gate.
3. Rekomendasi desain:
   - logout device saat ini merevoke refresh token/family yang terkait dengan refresh token yang dikirim;
   - tanpa refresh token, server hanya bisa revoke access token existing kecuali ada device/session identifier lain.

### Password Change / token_version Bump

`AUTH-TOKEN-005` tetap berlaku:

- Password change/reset bump `users.token_version`.
- Refresh token lama dengan `ver` lama ditolak.
- Tidak wajib mengubah seluruh row refresh token menjadi `REVOKED` pada Phase 1, tetapi dapat dipertimbangkan sebagai hardening tambahan.
- Jika token lama dipakai setelah bump, response controlled `401`.

### Tenant Inactive

Tenant lifecycle tetap divalidasi:

- Jika tenant suspended/archived/inactive, refresh ditolak.
- Response mengikuti policy existing, misalnya `403 tenant_inactive`.
- Server-side refresh session tidak menggantikan tenant lifecycle guard.

## 8. Atomicity Requirements

Refresh harus memakai atomic database update/transaction.

Requirement:

- Hanya token dengan `status = ACTIVE` yang boleh dikonsumsi.
- Request parallel dengan refresh token yang sama tidak boleh dua-duanya sukses.
- Jika atomic update affected rows = 0, return controlled `401 unauthorized`.
- Jangan issue atau return token baru jika consume token lama gagal.
- Jika reuse terdeteksi, revoke family dalam transaksi aman.
- Insert refresh token baru dan update old token `replaced_by_jti` harus terjadi dalam satu transaksi.
- Jika commit gagal, tidak boleh ada token baru yang dikembalikan sebagai sukses.

Implementation design direction:

- Prefer database-level conditional update:
  - `UPDATE mobile_refresh_tokens SET status='CONSUMED', consumed_at=..., replaced_by_jti=... WHERE jti=:old_jti AND token_hash=:old_hash AND status='ACTIVE' AND expires_at > now`
  - lanjut hanya jika affected rows = 1.
- Atau gunakan row-level lock:
  - `SELECT ... FOR UPDATE`
  - validasi status;
  - update status;
  - insert replacement.
- Gunakan PostgreSQL behavior sebagai target production. SQLite test boleh menutupi unit path, tetapi concurrency confidence harus dibuktikan dengan strategi yang sesuai.

## 9. Strict Cutover

Strict cutover diterima.

Konsekuensi:

- Existing refresh token production yang tidak punya row server-side akan ditolak controlled `401 unauthorized`.
- Mobile users mungkin perlu login ulang setelah deploy.
- Login baru setelah deploy membuat refresh token family dan row server-side baru.
- Tidak ada backfill untuk refresh token lama.

Response requirement:

- Missing server-side row tidak boleh menjadi `500`.
- Missing server-side row harus menjadi controlled `401 unauthorized`.
- Message sebaiknya generik, misalnya `Sesi sudah tidak berlaku. Silakan login ulang.`

## 10. Migration Impact

Migration baru dibutuhkan.

Expected migration:

- create table `mobile_refresh_tokens`;
- add columns sesuai proposed data model;
- add unique constraints:
  - `jti`
  - `token_hash`
- add indexes:
  - `user_id`
  - `tenant_id`
  - `family_id`
  - `status`
  - `expires_at`
  - optional `(user_id, tenant_id, status)`
- add foreign keys jika disetujui pada verification/migration gate:
  - `user_id -> users.id`
  - `tenant_id -> tenants.id`
- downgrade drops table.

Status representation:

- Option 1: string column with application constants.
- Option 2: database enum.

Recommendation awal:

- Gunakan string column untuk Phase 1 agar migration lebih sederhana dan rollback lebih mudah, kecuali repo sudah punya pola enum DB yang konsisten.

Jangan membuat migration pada tahap design decision ini.

## 11. Test Plan Update

Test plan untuk Option B:

1. Login creates ACTIVE refresh token row.
   - Mobile login sukses.
   - Assert satu row `mobile_refresh_tokens` untuk refresh token.
   - Assert `status = ACTIVE`, `family_id`, `jti`, `token_hash`, `expires_at`, `user_id`, dan `tenant_id` benar.

2. Refresh consumes old row and creates new ACTIVE row.
   - Login mobile.
   - Refresh dengan token awal.
   - Assert response `200`.
   - Assert old row `status = CONSUMED`.
   - Assert old row `consumed_at` terisi.
   - Assert old row `replaced_by_jti` sama dengan jti token baru.
   - Assert row token baru `status = ACTIVE`.
   - Assert family sama.

3. Old row status becomes CONSUMED.
   - Characterization terpisah untuk memastikan old token tidak tetap `ACTIVE` setelah refresh sukses.

4. `replaced_by_jti` is set.
   - Decode refresh token baru.
   - Cocokkan `old_row.replaced_by_jti == new_payload.jti`.

5. Reused old token returns controlled `401`.
   - Refresh token awal sukses sekali.
   - Pakai refresh token awal lagi.
   - Expected `401 unauthorized`, no `500`.

6. Reuse revokes token family.
   - Setelah reuse detected, assert semua row `family_id` yang sama tidak lagi `ACTIVE`.
   - Assert `reuse_detected_at` terisi pada row yang reused jika desain final memilih field tersebut.

7. Two parallel refresh requests cannot both succeed.
   - Dua request memakai refresh token yang sama.
   - Expected maksimal satu `200`.
   - Request lain controlled `401`.
   - Tidak ada dua row replacement active dari old token yang sama.

8. Refresh token without server-side row returns controlled `401`.
   - Buat token valid secara cryptographic tapi tanpa row DB.
   - Expected `401 unauthorized`.
   - Ini menutup strict cutover legacy token.

9. Logout revokes refresh row.
   - Login mobile.
   - Logout dengan refresh token.
   - Assert row refresh token menjadi `REVOKED`, atau family revoked sesuai desain final.
   - Refresh dengan token itu ditolak `401`.

10. Password change/token_version bump rejects old refresh token.
    - Login mobile.
    - Password change/reset bump `token_version`.
    - Refresh dengan token lama.
    - Expected controlled `401`.
    - Assert behavior `AUTH-TOKEN-005` tidak berubah.

11. Tenant inactive still rejected.
    - Login saat tenant active.
    - Suspend tenant.
    - Refresh token.
    - Expected tenant inactive response sesuai policy existing.

12. Malformed token rejected.
    - Random string, bad signature, expired token.
    - Expected controlled `401`.

13. Wrong type token rejected.
    - Kirim access token ke refresh endpoint.
    - Expected controlled `401`.

14. Migration/model constraints tested.
    - Unique `jti`.
    - Unique `token_hash`.
    - Index/foreign key existence jika feasible.
    - Duplicate row insert menghasilkan constraint error yang ditangani di service path.

15. Missing/stale/non-integer `ver` tetap ditolak.
    - Pastikan strict cutover `AUTH-TOKEN-005` tidak regression.

16. Missing user / tenant mismatch tetap ditolak.
    - Token payload valid tetapi user tidak ada atau tenant claim mismatch.
    - Expected controlled `401`.

17. Expired row rejected even if token signature max_age path berbeda.
    - Server-side `expires_at <= now` harus menolak token.

18. Family isolation.
    - Dua login mobile membuat dua family berbeda.
    - Reuse pada family A tidak merevoke family B kecuali human memilih revoke all devices.

## 12. Implementation Gate Needed

Langkah berikutnya sebelum coding:

1. Verification + migration gate.
2. Audit detail:
   - existing migration chain;
   - model naming/pattern;
   - timestamp helper;
   - transaction pattern;
   - PostgreSQL compatibility;
   - test fixture impact.
3. Finalisasi:
   - table/model name;
   - status representation;
   - FK behavior;
   - whether reuse revokes current family only or all user devices;
   - logout revokes token only or family;
   - response contract.
4. Baru setelah gate approved, lanjut implementation.

## 13. Final Decision

`OPTION B SELECTED FOR AUTH-REFRESH-006`

`SERVER-SIDE REFRESH TOKEN ROTATION APPROVED FOR DESIGN`

`MIGRATION ACCEPTED IN PRINCIPLE`

`NOT YET APPROVED FOR IMPLEMENTATION`

`NOT YET APPROVED FOR DEPLOY`
