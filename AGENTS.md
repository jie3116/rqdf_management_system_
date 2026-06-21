# Agentic Engineering Guide — RQDF

Dokumen ini adalah kontrak kerja untuk manusia dan agent yang mengerjakan repository RQDF. Tujuannya adalah membuat perubahan production secara terencana, dapat ditinjau, dapat diuji, dan dapat dibatalkan.

## Prinsip utama

1. Mulai dari spesifikasi, bukan langsung dari perubahan kode.
2. Pertahankan pola yang sudah ada: application factory, Flask blueprint, service layer, SQLAlchemy, Flask-Migrate/Alembic, RBAC, multi-tenant scoping, dan API `/api/v1`.
3. Lakukan perubahan kecil, terisolasi, dan mudah di-review.
4. Route menangani transport HTTP; aturan bisnis dan transaksi ditempatkan di service.
5. Setiap akses data tenant wajib memiliki scoping tenant yang eksplisit atau mekanisme existing yang terverifikasi.
6. Setiap perubahan schema wajib memiliki migration, analisis kompatibilitas, rollout, dan rollback consideration.
7. Verifikasi authorization, edge case, error handling, logging, testing, keamanan, dan performa sebelum release.
8. Temuan reviewer dicatat di `reviews/`; keputusan fitur dicatat di `specs/`.
9. Jangan menyatakan pekerjaan selesai tanpa bukti verifikasi.
10. Human approval adalah gate wajib untuk migration production, perubahan konfigurasi production, deploy, rollback, penghapusan data, dan operasi destruktif.

## Larangan global

- Jangan menjalankan `flask db upgrade`, `alembic upgrade`, downgrade, seed, backfill, atau script maintenance tanpa approval manusia.
- Jangan mengubah `.env`, credential, secret, Docker production, Gunicorn, Nginx, database production, atau pipeline deploy tanpa scope dan approval eksplisit.
- Jangan menghapus file, tabel, kolom, data, endpoint, atau behavior existing tanpa deprecation/rollback plan dan approval.
- Jangan melakukan refactor besar bersamaan dengan perubahan fitur.
- Jangan menaruh query baru di route jika logika tersebut merupakan aturan bisnis atau dipakai ulang.
- Jangan mengandalkan UI untuk authorization; pemeriksaan akses wajib dilakukan di server.
- Jangan mengabaikan test gagal. Dokumentasikan root cause sebelum memperbaiki.
- Jangan memperluas scope diam-diam.

## Baseline arsitektur repository

- Entrypoint: `run.py`, memanggil `create_app()`.
- Application factory dan registrasi extension/blueprint: `app/__init__.py`.
- Extension: `app/extensions.py`.
- Model SQLAlchemy saat ini terpusat di `app/models.py`.
- Route web: `app/routes/`, dipisahkan menurut domain/peran.
- Mobile API: blueprint `app/routes/api/`, terdaftar pada prefix `/api/v1`.
- Service layer: `app/services/`; penggunaannya sudah ada tetapi perlu dipertahankan dan dibuat konsisten untuk kode baru.
- Authorization: Flask-Login, decorator role, active-role handling, tenant/package enforcement, dan mobile token auth.
- Data boundaries: multi-tenant, role-based access, dan global soft-delete criteria.
- Migration: Flask-Migrate/Alembic di `migrations/`.
- Test: pytest di `tests/`; test yang ada menggunakan app factory dan database SQLite in-memory.
- Runtime: Docker, Gunicorn, PostgreSQL; reverse proxy Nginx berada di lingkungan deployment.

Rincian baseline ada di `docs/agentic/project_architecture_baseline.md`.

## Artefak wajib per fitur

Untuk fitur yang berdampak pada production, buat atau perbarui:

1. `specs/<feature>.md`
2. Architecture impact di dalam spec
3. Implementation plan dengan daftar file
4. Database/migration plan jika schema berubah
5. Test evidence
6. Review security, performance, dan code review yang relevan di `reviews/<feature>/`
7. Release checklist dan rollback plan
8. Dokumentasi/API/runbook/ADR bila relevan

## Urutan agent default

1. Requirement Analyst
2. Architecture
3. Backend Implementation
4. Database & Migration, jika ada dampak data
5. Testing & QA
6. Security Reviewer
7. Performance Reviewer
8. Code Review
9. Documentation
10. Deployment & Release
11. Maintenance & Refactoring dijalankan terpisah dari delivery fitur, kecuali refactor kecil diperlukan agar perubahan aman.

## Quality gates

Sebuah tahap tidak boleh diteruskan jika gate sebelumnya belum jelas:

- **Requirement gate:** acceptance criteria, role matrix, edge case, dan ambiguity terselesaikan.
- **Architecture gate:** dampak modul, data flow, compatibility, dan risiko disetujui.
- **Implementation gate:** perubahan sesuai spec dan scope.
- **Database gate:** migration direview; belum dijalankan tanpa approval.
- **Verification gate:** test relevan lulus atau kegagalan dijelaskan.
- **Review gate:** tidak ada temuan HIGH/CRITICAL yang belum diputuskan.
- **Release gate:** backup, migration sequence, smoke test, monitoring, dan rollback siap; deploy tetap memerlukan approval manusia.

## Format handoff antar-agent

Setiap handoff minimal berisi:

- Tujuan dan scope
- Input/artefak yang dibaca
- Keputusan yang dibuat
- File yang terdampak
- Risiko dan asumsi
- Verifikasi yang dilakukan
- Open questions
- Rekomendasi agent berikutnya

## Aturan review

- Reviewer bersifat read-only kecuali diminta membuat patch.
- Temuan harus spesifik, dapat direproduksi, dan menunjuk file/lokasi terkait.
- Bedakan fakta, inferensi, dan rekomendasi.
- Security severity: `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`.
- Temuan tanpa bukti tidak boleh dipresentasikan sebagai kerentanan pasti.
- Jangan memulai audit mendalam seluruh aplikasi tanpa approval manusia.

## Referensi agent dan checklist

- Definisi agent: `agents/`
- Template spesifikasi: `specs/feature_spec_template.md`
- Output review: `reviews/`
- Checklist: `checklists/`
- Workflow: `docs/agentic/sdlc_workflow.md`
- Panduan Codex: `docs/agentic/codex_usage.md`

