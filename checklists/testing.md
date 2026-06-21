# Testing & QA Checklist

## Traceability

- [ ] Setiap acceptance criterion dipetakan ke test.
- [ ] Out-of-scope tidak masuk tanpa keputusan baru.
- [ ] Test mencatat konfigurasi dan command yang digunakan.

## Functional

- [ ] Happy path.
- [ ] Invalid/missing input.
- [ ] Boundary value dan duplicate request.
- [ ] Invalid state transition.
- [ ] Transaction rollback atau partial failure.
- [ ] Idempotency bila operasi dapat diulang.

## Access control dan isolation

- [ ] Unauthenticated.
- [ ] Role allowed.
- [ ] Role forbidden.
- [ ] Wrong tenant.
- [ ] Wrong owner/object ID.
- [ ] Soft-deleted/inactive object.

## Web/API/database

- [ ] HTTP method, status, redirect, flash, dan payload.
- [ ] `/api/v1` contract dan error shape.
- [ ] Constraint, FK, unique, nullable, dan default.
- [ ] PostgreSQL-specific behavior ditest atau dinyatakan belum diverifikasi.

## Regression evidence

- [ ] Test baru lulus.
- [ ] Test modul terkait lulus.
- [ ] Full suite dijalankan bila proporsional terhadap risiko.
- [ ] Kegagalan memiliki root cause, bukan hanya patch symptom.
- [ ] Manual test dan residual risk dicatat.

