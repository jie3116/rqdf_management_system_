# Runbook Koreksi Data PPDB dan Nomor HP Orang Tua

Runbook ini dipakai ketika pendaftar salah memasukkan nomor HP orang tua, nomor WhatsApp peserta Majelis Ta'lim, atau data lain saat registrasi PPDB.

## Target

- Aplikasi: `rq_app`
- Entry point Flask: `run.py`
- Jalur registrasi publik: `app/routes/main.py`
- Model utama pendaftar: `StudentCandidate`
- Model akun login: `User`
- Profil wali: `Parent`
- Profil Majelis Ta'lim: `MajlisParticipant`

Nomor HP penting karena aplikasi memakai nomor tersebut sebagai identifier login:

- Pendaftar siswa: `StudentCandidate.parent_phone`
- Peserta Majelis Ta'lim: `StudentCandidate.personal_phone`, fallback ke `parent_phone`
- Setelah siswa diterima: `User.username` wali dan `Parent.phone`
- Setelah peserta Majelis diterima: `User.username` peserta dan `MajlisParticipant.phone`

## 1. Tentukan Status Kasus

Cari pendaftar dari menu PPDB terlebih dahulu:

- Admin: `/admin/ppdb/pendaftar`
- TU: `/staff/ppdb/list`

Gunakan nomor pendaftaran, nama, nomor orang tua, atau nomor peserta karena daftar PPDB mendukung pencarian pada `registration_no`, `full_name`, `parent_phone`, dan `personal_phone`.

Catat data ini sebelum koreksi:

- `registration_no`
- `tenant_id` atau tenant aktif
- status pendaftaran: `PENDING`, `INTERVIEW`, `ACCEPTED`, atau `REJECTED`
- nomor lama
- nomor baru
- data lain yang perlu diubah

Jika status belum `ACCEPTED`, cukup ubah data di `StudentCandidate`. Jika sudah `ACCEPTED`, sinkronkan juga akun login dan profil terkait.

## 2. Jalur Utama Lewat Admin UI

Untuk orang tua/peserta yang sudah memiliki akun aktif, gunakan UI agar perubahan tervalidasi dan tercatat di audit log:

1. Login sebagai Admin.
2. Buka `Manajemen User`.
3. Cari akun berdasarkan nomor lama, nama wali, nama peserta, atau role.
4. Pada akun `Wali Murid`, `Peserta Majelis`, atau `Wali Asrama`, klik `Ganti Nomor Login`.
5. Isi nomor baru dan alasan perubahan.
6. Centang opsi reset password hanya jika password juga perlu dijadikan nomor baru.
7. Simpan, lalu minta user login dengan nomor baru.

Fitur ini memperbarui `User.username` dan profil terkait dalam satu transaksi:

- `Parent.phone` untuk Wali Murid
- `MajlisParticipant.phone` untuk Peserta Majelis
- `BoardingGuardian.phone` untuk Wali Asrama

Untuk Wali Murid dan Peserta Majelis, sistem juga menyinkronkan data PPDB berstatus `ACCEPTED` yang masih memakai nomor lama. Jika pendaftar belum diterima, gunakan prosedur manual di bawah karena akun user biasanya belum dibuat.

## 3. Backup Sebelum Perubahan

Untuk production, lakukan backup database lebih dulu. Ikuti [db_backup_runbook.md](db_backup_runbook.md).

Minimal pastikan:

```bash
export FLASK_APP=run.py
flask db current
```

Jangan membuka, menyalin, atau membagikan isi `.env`. Pastikan environment aplikasi sudah tersedia dari service/shell server.

## 4. Pre-check di Flask Shell

Masuk ke folder aplikasi dan aktifkan virtualenv jika diperlukan:

```bash
cd ~/rqdf_management_system
source .venv/bin/activate
export FLASK_APP=run.py
flask shell
```

Import model yang diperlukan:

```python
from app import db
from app.models import (
    StudentCandidate, RegistrationStatus, ProgramType,
    User, UserRole, Parent, Student, MajlisParticipant
)
```

Cari pendaftar:

```python
registration_no = "REG202600001"
candidate = StudentCandidate.query.filter_by(
    registration_no=registration_no,
    is_deleted=False,
).first()

candidate.id, candidate.tenant_id, candidate.full_name, candidate.status, candidate.parent_phone, candidate.personal_phone
```

Pastikan hasilnya satu orang yang benar. Jika `candidate` bernilai `None`, hentikan dan cek ulang nomor pendaftaran.

## 5. Koreksi Nomor HP Sebelum Diterima

Gunakan jalur ini untuk status `PENDING`, `INTERVIEW`, atau `REJECTED`.

### Siswa / Program Non-Majelis

```python
new_phone = "08xxxxxxxxxx"

conflict = User.query.filter_by(
    tenant_id=candidate.tenant_id,
    username=new_phone,
    is_deleted=False,
).first()
conflict
```

Jika `conflict` berisi akun lain yang tidak terkait kasus ini, jangan lanjut sebelum dipastikan nomor tersebut memang milik wali yang benar.

Jika aman:

```python
candidate.parent_phone = new_phone
db.session.commit()
```

### Peserta Majelis Ta'lim

```python
new_phone = "08xxxxxxxxxx"

candidate.personal_phone = new_phone
candidate.parent_phone = new_phone
db.session.commit()
```

Catatan: saat diterima, kode memakai `personal_phone` lebih dulu, lalu fallback ke `parent_phone`.

## 6. Koreksi Nomor HP Setelah Diterima

Status `ACCEPTED` berarti akun sudah atau seharusnya sudah dibuat. Jangan hanya mengubah `StudentCandidate`, karena login tetap membaca `users.username` dan/atau profil `parents.phone` / `majlis_participants.phone`.

### Siswa yang Sudah Diterima

Pre-check:

```python
old_phone = (candidate.parent_phone or "").strip()
new_phone = "08xxxxxxxxxx"

old_user = User.query.filter_by(
    tenant_id=candidate.tenant_id,
    username=old_phone,
    is_deleted=False,
).first()

new_user = User.query.filter_by(
    tenant_id=candidate.tenant_id,
    username=new_phone,
    is_deleted=False,
).first()

old_user, new_user
```

Aturan aman:

- Jika `new_user` ada dan bukan akun wali yang sama, hentikan dan investigasi.
- Jika `old_user` tidak ditemukan, cari wali lewat `Parent.phone == old_phone`; jangan membuat akun baru tanpa memastikan relasi siswa.
- Jika wali memiliki beberapa anak, perubahan username berlaku untuk login wali semua anak tersebut.

Eksekusi standar jika nomor lama memang milik akun wali yang harus diganti:

```python
if new_user and old_user and new_user.id != old_user.id:
    raise ValueError("Nomor baru sudah dipakai akun lain di tenant ini.")

parent_profile = old_user.parent_profile if old_user else None
if not parent_profile:
    parent_profile = Parent.query.filter_by(phone=old_phone, is_deleted=False).first()
    old_user = parent_profile.user if parent_profile else None

if not old_user or not parent_profile:
    raise ValueError("Akun/profil wali lama tidak ditemukan. Hentikan dan cek manual.")

candidate.parent_phone = new_phone
old_user.username = new_phone
parent_profile.phone = new_phone
db.session.commit()
```

Jika wali lupa password setelah nomor diganti, reset password dari UI admin atau jalankan:

```python
old_user.set_password(new_phone)
old_user.must_change_password = True
db.session.commit()
```

### Peserta Majelis yang Sudah Diterima

Pre-check:

```python
old_phone = (candidate.personal_phone or candidate.parent_phone or "").strip()
new_phone = "08xxxxxxxxxx"

old_user = User.query.filter_by(
    tenant_id=candidate.tenant_id,
    username=old_phone,
    is_deleted=False,
).first()

new_user = User.query.filter_by(
    tenant_id=candidate.tenant_id,
    username=new_phone,
    is_deleted=False,
).first()

old_user, new_user
```

Eksekusi:

```python
if new_user and old_user and new_user.id != old_user.id:
    raise ValueError("Nomor baru sudah dipakai akun lain di tenant ini.")

profile = old_user.majlis_profile if old_user else None
if not profile:
    profile = MajlisParticipant.query.filter_by(phone=old_phone, is_deleted=False).first()
    old_user = profile.user if profile else None

if not old_user or not profile:
    raise ValueError("Akun/profil Majelis lama tidak ditemukan. Hentikan dan cek manual.")

candidate.personal_phone = new_phone
candidate.parent_phone = new_phone
old_user.username = new_phone
profile.phone = new_phone
db.session.commit()
```

Opsional reset password:

```python
old_user.set_password(new_phone)
old_user.must_change_password = True
db.session.commit()
```

## 7. Koreksi Data Lain di Pendaftar

Untuk data yang masih berada di tabel PPDB, ubah field `StudentCandidate`.

Contoh:

```python
candidate.full_name = "Nama Lengkap Benar"
candidate.father_name = "Nama Ayah Benar"
candidate.mother_name = "Nama Ibu Benar"
candidate.father_job = "Pekerjaan Ayah Benar"
candidate.mother_job = "Pekerjaan Ibu Benar"
candidate.address = "Alamat Benar"
db.session.commit()
```

Field umum yang tersedia:

- Data calon: `full_name`, `nickname`, `nik`, `kk_number`, `gender`, `place_of_birth`, `date_of_birth`, `age`, `address`
- Sekolah asal: `previous_school`, `previous_school_class`
- Orang tua: `father_name`, `father_job`, `father_income_range`, `mother_name`, `mother_job`, `mother_income_range`, `parent_phone`
- Majelis: `personal_phone`, `personal_job`
- RQDF: `tahfidz_schedule`, `uniform_size`, `initial_pledge_amount`

Jika pendaftar sudah `ACCEPTED`, data tertentu mungkin sudah disalin ke tabel operasional:

- Nama, jenis kelamin, TTL, alamat siswa: `Student`
- Nama, HP, pekerjaan, alamat wali: `Parent`
- Nama, HP, pekerjaan, alamat peserta Majelis: `MajlisParticipant`

Sinkronkan tabel operasional sesuai kebutuhan, bukan hanya `StudentCandidate`.

## 8. Verifikasi Setelah Koreksi

Di Flask shell:

```python
db.session.refresh(candidate)
candidate.registration_no, candidate.full_name, candidate.parent_phone, candidate.personal_phone, candidate.status
```

Untuk wali murid:

```python
user = User.query.filter_by(
    tenant_id=candidate.tenant_id,
    username=new_phone,
    is_deleted=False,
).first()

user.id, user.username, user.parent_profile.phone if user and user.parent_profile else None
```

Untuk Majelis:

```python
user = User.query.filter_by(
    tenant_id=candidate.tenant_id,
    username=new_phone,
    is_deleted=False,
).first()

user.id, user.username, user.majlis_profile.phone if user and user.majlis_profile else None
```

Lalu verifikasi dari UI:

- Cari pendaftar di daftar PPDB dengan nomor baru.
- Buka detail pendaftar dan pastikan data sudah benar.
- Jika sudah diterima, coba login dengan nomor baru di staging atau minta user mencoba login.
- Jika password direset, informasikan password sementara sesuai prosedur internal.

## 9. Rollback Manual

Jika perubahan salah dan belum ada perubahan lain, kembalikan nilai lama:

```python
candidate.parent_phone = old_phone
old_user.username = old_phone
parent_profile.phone = old_phone
db.session.commit()
```

Untuk Majelis:

```python
candidate.personal_phone = old_phone
candidate.parent_phone = old_phone
old_user.username = old_phone
profile.phone = old_phone
db.session.commit()
```

Jika terjadi error sebelum commit:

```python
db.session.rollback()
```

## 10. Catatan Risiko

- `users` memiliki unique constraint per tenant untuk `username` dan `email`; nomor baru tidak boleh sudah dipakai akun lain di tenant yang sama.
- Login menerima `username`, `email`, NIS/NIP, dan nomor profil. Nomor yang duplikat di beberapa profil dapat membuat login ambigu.
- Untuk siswa yang sudah diterima, tidak ada foreign key langsung dari `StudentCandidate` ke `Student`; jangan menebak relasi hanya dari nama jika ada nama mirip. Cocokkan juga tanggal lahir, alamat, wali, dan waktu penerimaan.
- Jangan mengubah `.env` atau membagikan kredensial database saat menjalankan runbook ini.
