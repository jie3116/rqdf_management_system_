# Deployment & Release Checklist

Semua tindakan production memerlukan approval manusia.

## Identitas release

- [ ] Nama/versi release:
- [ ] Commit/image tag:
- [ ] Owner:
- [ ] Window:
- [ ] Scope dan out-of-scope:

## Pre-deploy

- [ ] Feature spec dan review gate selesai.
- [ ] Test evidence tersedia.
- [ ] Tidak ada HIGH/CRITICAL unresolved tanpa sign-off.
- [ ] Env/config changes terdaftar tanpa secret.
- [ ] Docker image berhasil dibangun dan diidentifikasi secara immutable.
- [ ] Capacity/disk/database connection dinilai.

## Database

- [ ] Backup dijadwalkan dan lokasi/retention diketahui.
- [ ] Prosedur restore telah diverifikasi sesuai runbook.
- [ ] Migration direview; head/dependency jelas.
- [ ] Lock/downtime/backfill/compatibility dinilai.
- [ ] Aplikasi old/new compatible selama rollout.
- [ ] Approval manusia diperoleh sebelum menjalankan migration.

## Deploy sequence

- [ ] Urutan langkah tertulis.
- [ ] Health check dan startup log diperiksa.
- [ ] Worker/restart strategy jelas.
- [ ] Tidak ada config production diubah di luar scope.
- [ ] Approval manusia diperoleh sebelum deploy.

## Smoke test

- [ ] Login/logout web.
- [ ] Login/refresh/logout `/api/v1` bila relevan.
- [ ] Role allowed dan forbidden.
- [ ] Tenant isolation sanity check.
- [ ] Flow utama fitur.
- [ ] Flow kritis existing yang terdampak.
- [ ] Error log dan response time diperiksa.

## Monitoring dan rollback

- [ ] Metric/log/error yang dipantau.
- [ ] Durasi observasi dan owner.
- [ ] Rollback trigger terukur.
- [ ] App rollback steps.
- [ ] Schema/data rollback consideration.
- [ ] Komunikasi incident/release.

