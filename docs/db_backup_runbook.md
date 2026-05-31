# Runbook Backup Database PostgreSQL

Runbook ini dipakai sebelum deploy, sebelum `flask db upgrade`, dan sebelum perubahan data massal.

## Target

- Aplikasi: `rq_app`
- Entry point Flask: `run.py`
- Database dibaca dari environment `DATABASE_URL`
- Engine database: PostgreSQL
- Format backup utama: `pg_dump` custom format (`.dump`)

## 1. Pre-check

Masuk ke server production dan pindah ke folder aplikasi:

```bash
cd ~/rqdf_management_system
```

Aktifkan virtualenv jika tersedia:

```bash
source .venv/bin/activate
```

Pastikan environment aplikasi terbaca:

```bash
export FLASK_APP=run.py
flask db current
flask db heads
```

Sebelum deploy saat ini, `flask db heads` harus hanya menampilkan satu head. Jika ada lebih dari satu head, hentikan deploy dan rapikan migration dulu.

## 2. Siapkan Folder Backup

```bash
mkdir -p backups
chmod 700 backups
```

Gunakan timestamp agar nama file unik:

```bash
TS=$(date +%Y%m%d_%H%M%S)
```

## 3. Ambil DATABASE_URL

Jika `DATABASE_URL` sudah ada di environment:

```bash
echo "$DATABASE_URL" | sed 's#://.*:.*@#://USER:***@#'
```

Jika server memakai file `.env`, load variabelnya:

```bash
set -a
source .env
set +a
echo "$DATABASE_URL" | sed 's#://.*:.*@#://USER:***@#'
```

Jangan paste password database ke chat, tiket, atau commit.

## 4. Backup Utama (.dump)

Gunakan custom format karena paling aman untuk restore terkontrol dengan `pg_restore`:

```bash
pg_dump "$DATABASE_URL" \
  --format=custom \
  --blobs \
  --verbose \
  --file="backups/prod_backup_${TS}.dump"
```

Jika database ada di Docker container bernama `db`, alternatifnya:

```bash
docker compose exec -T db pg_dump \
  -U "$POSTGRES_USER" \
  -d "$POSTGRES_DB" \
  --format=custom \
  --blobs \
  --verbose \
  > "backups/prod_backup_${TS}.dump"
```

## 5. Backup SQL Tambahan

Opsional, tapi berguna untuk inspeksi manual:

```bash
pg_dump "$DATABASE_URL" \
  --format=plain \
  --no-owner \
  --no-privileges \
  --file="backups/prod_backup_${TS}.sql"
```

## 6. Verifikasi Backup

Cek ukuran file:

```bash
ls -lh "backups/prod_backup_${TS}.dump"
```

File backup harus berukuran lebih dari 0 byte.

Cek daftar isi backup:

```bash
pg_restore --list "backups/prod_backup_${TS}.dump" | head -30
```

Buat checksum:

```bash
sha256sum "backups/prod_backup_${TS}.dump" > "backups/prod_backup_${TS}.dump.sha256"
cat "backups/prod_backup_${TS}.dump.sha256"
```

## 7. Copy Backup Keluar Server

Minimal simpan satu salinan di luar server production:

```bash
scp "backups/prod_backup_${TS}.dump" user@backup-host:/path/to/backups/
scp "backups/prod_backup_${TS}.dump.sha256" user@backup-host:/path/to/backups/
```

Jika memakai object storage, upload file `.dump` dan `.sha256` ke bucket backup.

## 8. Jalankan Deploy dan Migration

Setelah backup valid:

```bash
git pull
pip install -r requirements.txt
flask db upgrade
flask db current
```

Pastikan `flask db current` berada di revision target terbaru.

Restart service aplikasi sesuai setup server:

```bash
sudo systemctl restart rq_app
```

Jika memakai Docker:

```bash
docker compose up -d --build
```

## 9. Smoke Test Setelah Deploy

Cek halaman utama/admin:

```bash
curl -I http://127.0.0.1:8000/
```

Cek fitur yang baru diubah:

- Login admin.
- Buka `Adjustment Nilai Raport`.
- Download template Excel.
- Upload file kecil berisi 1 baris valid di staging atau production hanya jika memang dibutuhkan.
- Buka halaman evaluasi tahfidz dan pastikan dropdown jenis evaluasi muncul.

## 10. Restore Darurat

Restore sebaiknya dilakukan ke database kosong atau database baru terlebih dahulu.

Contoh restore ke database baru:

```bash
createdb rq_restore_test
pg_restore \
  --dbname=rq_restore_test \
  --clean \
  --if-exists \
  --no-owner \
  --verbose \
  "backups/prod_backup_${TS}.dump"
```

Jika perlu restore production, hentikan aplikasi dulu:

```bash
sudo systemctl stop rq_app
```

Restore ke database production hanya setelah backup target benar-benar dipastikan:

```bash
pg_restore \
  --dbname="$DATABASE_URL" \
  --clean \
  --if-exists \
  --no-owner \
  --verbose \
  "backups/prod_backup_${TS}.dump"
```

Lalu jalankan:

```bash
flask db current
sudo systemctl start rq_app
```

## 11. Kriteria Aman Lanjut Deploy

Deploy boleh lanjut jika semua kondisi ini terpenuhi:

- `flask db heads` hanya menampilkan satu head.
- File `.dump` berhasil dibuat.
- `pg_restore --list` bisa membaca backup.
- Checksum `.sha256` dibuat.
- Salinan backup sudah keluar dari server production.
- Ada akses untuk restore jika migration gagal.

## 12. Catatan Penting

- Jangan menyimpan backup database di Git.
- Jangan commit `.env`.
- Jangan membagikan `DATABASE_URL` mentah karena berisi password.
- Simpan minimal 3 backup terakhir sebelum deploy besar.
- Lakukan restore drill berkala ke database test agar backup terbukti bisa dipakai.
