# Baseline Arsitektur RQDF

Dokumen ini mencatat hasil pemetaan read-only tahap pertama. Ini bukan audit keamanan, performa, atau kualitas mendalam.

## Pola yang teridentifikasi

### Application factory

`run.py` membuat aplikasi melalui `create_app()`. `app/__init__.py` menginisialisasi Flask, extension, context processor, login loader, soft-delete criteria, tenant/module guard, dan blueprint.

### Modular monolith dengan blueprint

Route web berada di `app/routes/` dan dipisahkan menurut area/peran seperti admin, teacher, parent, student, staff, boarding, dan auth. Mobile API memakai satu blueprint dengan registrar per domain di `app/routes/api/`, lalu dipasang pada `/api/v1`.

### Service layer

Aturan bisnis reusable telah dipisahkan ke `app/services/`, termasuk finance posting, enrollment, admission, report, dan domain lain. Penerapan service layer belum sepenuhnya seragam; kode baru harus memperkuat pola ini tanpa refactor besar.

### Persistence dan migration

SQLAlchemy digunakan melalui extension `db`. Model saat ini terpusat di `app/models.py`. Flask-Migrate/Alembic digunakan melalui `migrations/`, dengan riwayat migration yang cukup panjang. Perubahan schema harus memperhitungkan kompatibilitas data existing dan urutan rollout.

### Authentication dan authorization

- Web: Flask-Login dan session.
- RBAC: `UserRole`, role decorator, active role, dan kombinasi role.
- Mobile API: signed access/refresh token dan revocation storage.
- Tenant/module access: guard global dan helper tenant/package.
- API blueprint dikecualikan dari CSRF; endpoint API harus bergantung pada token auth dan validasi request yang benar.

### Data isolation

Repository menunjukkan multi-tenant scoping dan global filter untuk soft delete. Fitur baru harus memverifikasi tenant ownership pada setiap read/write, bukan hanya berdasarkan ID objek.

### Presentation

Server-rendered Jinja templates berada di `app/templates/`; static assets berada di `app/static/`. Route web dan API berbagi model serta sebagian service.

### Testing

Test menggunakan pytest, application factory, dan SQLite in-memory. Coverage yang terlihat saat pemetaan awal terutama berada pada finance core dan grade formula service. PostgreSQL-specific behavior tetap perlu diuji secara khusus bila fitur bergantung padanya.

### Runtime dan deployment

Docker Compose menjalankan Gunicorn dan PostgreSQL 15. Container web hanya diekspos ke localhost port 8000, sesuai pola reverse proxy eksternal. `Procfile` juga menggunakan Gunicorn. Konfigurasi Nginx tidak berada pada tree yang dipetakan.

## Konsekuensi untuk agent

- Jangan mengubah struktur menjadi microservices atau repository pattern tanpa kebutuhan yang disetujui.
- Jangan memecah `app/models.py` sebagai bagian sampingan fitur.
- Gunakan service layer untuk aturan bisnis dan batas transaksi.
- Pastikan route tipis dan konsisten dengan blueprint existing.
- Review tenant isolation, role permission, soft-delete behavior, dan web/API parity untuk setiap fitur.
- Migration dan deployment wajib dianggap berisiko production, meskipun perubahan schema terlihat kecil.

## Area yang belum dinilai

Tahap ini belum menilai secara mendalam:

- kerentanan endpoint tertentu;
- kualitas seluruh migration chain;
- N+1 dan query plan;
- coverage test keseluruhan;
- konfigurasi server production aktual;
- integritas file upload dan data existing;
- correctness seluruh business flow.

Semua area tersebut memerlukan audit terpisah setelah approval manusia.

