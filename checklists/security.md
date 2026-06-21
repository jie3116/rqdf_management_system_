# Security Review Checklist

Gunakan per fitur atau endpoint. Tandai `PASS`, `FAIL`, `N/A`, atau `NOT VERIFIED` dan sertakan bukti.

## Authentication dan session/token

- [ ] Endpoint sensitif mewajibkan authentication server-side.
- [ ] Session/token expiry, refresh, revoke, logout, dan replay dinilai.
- [ ] Password/credential tidak dicatat ke log atau response.
- [ ] Perubahan credential/session menangani invalidation yang diperlukan.

## Authorization dan tenant isolation

- [ ] Role yang diizinkan sesuai permission matrix.
- [ ] Active role tidak dapat menaikkan privilege.
- [ ] Object lookup memverifikasi tenant dan ownership, bukan hanya ID.
- [ ] List, detail, create, update, delete memiliki check yang konsisten.
- [ ] Soft-deleted object tidak dapat diakses tanpa tujuan eksplisit.
- [ ] Admin/super-admin exception terdokumentasi.

## Input dan output

- [ ] Input type, format, length, enum, range, dan state divalidasi.
- [ ] Query tidak dibangun dengan SQL string dari input user.
- [ ] Redirect target dibatasi.
- [ ] Output/error tidak membocorkan secret, PII, stack trace, atau object lintas tenant.
- [ ] API mass assignment dicegah.

## Web dan API

- [ ] Web state-changing request dilindungi CSRF.
- [ ] API yang CSRF-exempt memiliki token auth yang benar.
- [ ] CORS, content type, method, dan status code dinilai.
- [ ] Rate limit/brute-force protection dinilai untuk login, token, upload, search, dan endpoint mahal.

## File dan external integration

- [ ] Upload membatasi size, extension/MIME, filename/path, dan access.
- [ ] File tidak dapat dieksekusi atau diakses lintas tenant.
- [ ] URL/external request tidak membuka SSRF atau open redirect.
- [ ] Secret berasal dari environment/secret store.

## Output review

- [ ] Severity dan bukti untuk setiap temuan.
- [ ] Risiko bisnis dan teknis.
- [ ] Mitigasi minimal serta defense-in-depth dipisahkan.
- [ ] HIGH/CRITICAL memiliki keputusan release eksplisit.

