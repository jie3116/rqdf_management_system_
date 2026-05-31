# Modul Konfigurasi Dashboard Admin

Dokumen ini menjelaskan cara melakukan konfigurasi dari Dashboard Admin, variabel yang tersedia, dan nilai yang bisa dibedakan antar tenant. Fokus utama konfigurasi tenant disimpan di tabel `app_configs` melalui model `AppConfig` dengan kombinasi unik `tenant_id + key`.

## 1) Hak Akses

Gunakan akun sesuai area kerja berikut:

- `SUPER_ADMIN`: mengelola tenant di `/admin/platform/tenants`.
- `ADMIN`: mengelola dashboard admin tenant, master akademik, kelas, guru, PPDB, siswa, dan konfigurasi sistem di `/admin/pengaturan/sistem`.
- `TU`: mengelola pengaturan finance di `/admin/keuangan/settings`.

Setiap user operasional berada pada satu `tenant_id`. Data admin tenant difilter berdasarkan `tenant_id`, sedangkan `SUPER_ADMIN` bisa melihat dan membuat tenant.

## 2) Konfigurasi Tenant oleh Super Admin

Buka menu `Manajemen Tenant` atau URL:

```text
/admin/platform/tenants
```

Field yang bisa diatur:

| Field | Sumber Data | Value | Dampak |
| --- | --- | --- | --- |
| `name` | `Tenant.name` dan `AppConfig.institution_name` | Teks nama lembaga | Dipakai sebagai nama tenant dan nama lembaga pada dokumen resmi. |
| `code` | `Tenant.code` | Huruf/angka/underscore/dash, unik global | Identitas tenant. Tidak diubah dari form update tenant. |
| `slug` | `Tenant.slug` | Slug URL-friendly, unik global | Identitas singkat tenant. Diisi saat membuat tenant. |
| `timezone` | `Tenant.timezone` | Contoh `Asia/Jakarta` | Referensi zona waktu tenant. Default aplikasi saat ini tetap banyak memakai helper lokal Asia/Jakarta. |
| `status` | `Tenant.status` | `ACTIVE`, `SUSPENDED`, `ARCHIVED` | Status administratif tenant. |
| `module_package` | `AppConfig.tenant.module_package` | `full`, `rumah_quran`, `sekolah` | Mengaktifkan/membatasi modul, role, dan endpoint. |
| `institution_address` | `AppConfig.institution_address` | Teks alamat | Dipakai untuk dokumen/resi/laporan tenant. |
| `institution_phone` | `AppConfig.institution_phone` | Teks nomor telepon | Dipakai untuk dokumen/resi/laporan tenant. |

Setelah tenant dibuat, buat minimal satu admin tenant melalui form `Tambah Admin Tenant`. Username dan email harus unik global.

## 3) Paket Modul Tenant

Key utama:

```text
tenant.module_package
```

Value yang valid:

| Value | Modul yang Dibuka | Pembatasan Utama |
| --- | --- | --- |
| `full` | Sekolah, Rumah Qur'an, Majlis, Boarding, Finance, PPDB | Tidak ada pembatasan paket khusus. |
| `sekolah` | Modul sekolah formal, admin, pimpinan, TU, guru, siswa, wali murid | Endpoint `staff.*`, `boarding.*`, dan beberapa halaman majlis diblokir. |
| `rumah_quran` | Modul admin/pimpinan/TU/wali murid/majlis sesuai paket RQ | Endpoint `teacher.*`, `student.*`, `boarding.*`, dashboard wali murid umum, dan beberapa master akademik formal diblokir. |

Catatan penting: `teacher.py` hanya dapat diakses oleh role `GURU`. Jika paket tenant adalah `rumah_quran`, fungsi `endpoint_allowed_for_package()` memblokir endpoint `teacher.*`, sehingga dashboard guru tidak terbuka untuk tenant tersebut meskipun user memiliki role guru.

## 4) Konfigurasi Sistem Per Tenant

Buka:

```text
/admin/pengaturan/sistem
```

Form ini melakukan upsert ke `AppConfig` untuk tenant aktif. Jika `key` sudah ada maka `value` dan `description` diperbarui. Jika belum ada maka dibuat baru.

Aturan penulisan key:

- Gunakan huruf kecil, angka, titik, atau underscore.
- Jangan gunakan spasi.
- Pilih nama yang stabil karena key dipakai oleh service aplikasi.

## 5) Key AppConfig yang Dipakai Aplikasi

| Key | Value yang Disarankan | Dipakai Oleh | Efek |
| --- | --- | --- | --- |
| `tenant.module_package` | `full`, `rumah_quran`, `sekolah` | `app/utils/tenant_modules.py` | Menentukan paket modul tenant. |
| `institution_name` | Nama lembaga | Tenant/doc output | Nama lembaga pada dokumen tenant. |
| `institution_address` | Alamat lembaga | Tenant/doc output | Alamat lembaga pada dokumen tenant. |
| `institution_phone` | Nomor telepon | Tenant/doc output | Kontak lembaga pada dokumen tenant. |
| `ppdb_public_domain` | Domain tunggal atau comma-separated, contoh `ppdb.rqdf.co.id,daftar.rqdf.id` | PPDB publik | Domain publik yang dianggap milik tenant untuk PPDB. |
| `grade_formula_weights` | JSON bobot nilai | `grade_formula_service`, `teacher.py` | Mengubah rumus nilai akhir pada laporan guru/wali kelas. |
| `assignment_label.formal_homeroom` | Contoh `Wali Kelas` | Assignment guru | Label wali kelas formal. |
| `assignment_label.nonformal_homeroom` | Contoh `Pembimbing Kelas` | Assignment guru | Label pembimbing kelas non-formal. |
| `assignment_label.subject_teacher` | Contoh `Guru Mapel` | Assignment guru | Label guru pengampu mata pelajaran. |
| `assignment_label.program_companion` | Contoh `Pendamping Program` | Assignment guru | Label pendamping program. |
| `assignment_label.boarding_supervisor` | Contoh `Pembina Asrama` | Assignment asrama | Label pembina asrama. |

## 6) Format `grade_formula_weights`

Default jika key tidak diisi atau JSON invalid:

```json
{
  "TUGAS": 30,
  "UH": 20,
  "UTS": 25,
  "UAS": 25
}
```

Value boleh berupa JSON langsung:

```json
{
  "TUGAS": 20,
  "UH": 20,
  "UTS": 25,
  "UAS": 35
}
```

Atau memakai struktur bertingkat:

```json
{
  "default": {
    "TUGAS": 30,
    "UH": 20,
    "UTS": 25,
    "UAS": 25
  },
  "academic_years": {
    "3": {
      "TUGAS": 25,
      "UH": 25,
      "UTS": 20,
      "UAS": 30
    }
  },
  "subjects": {
    "12": {
      "TUGAS": 40,
      "UH": 20,
      "UTS": 20,
      "UAS": 20
    }
  },
  "subject_academic_years": {
    "12:3": {
      "TUGAS": 20,
      "UH": 30,
      "UTS": 20,
      "UAS": 30
    }
  }
}
```

Prioritas pemilihan bobot:

1. `subject_academic_years` berdasarkan `subject_id:academic_year_id` atau `academic_year_id:subject_id`.
2. `subjects` berdasarkan `subject_id`.
3. `academic_years` berdasarkan `academic_year_id`.
4. `weights`, `default`, atau JSON root.
5. Default aplikasi.

`teacher.py` memanggil `calculate_weighted_final()` saat menghitung nilai siswa dan laporan wali kelas. Karena itu, perubahan `grade_formula_weights` per tenant langsung memengaruhi output nilai akhir di dashboard guru tenant tersebut.

### Adjustment Nilai Raport Resmi

Jika nilai akhir siswa/santri tertentu perlu disesuaikan setelah perhitungan normal, gunakan:

```text
/admin/akademik/adjustment-raport
```

Adjustment ini tidak mengubah nilai raw yang diinput guru. Sistem menyimpan nilai awal hasil rumus, nilai akhir setelah adjustment, siswa, kelas, tahun ajaran, mapel, admin penyetuju, waktu persetujuan, alasan, dan nomor dokumen persetujuan.

Prosedur minimal:

1. Pastikan nilai raw guru sudah lengkap dan tahun ajaran/mapel benar.
2. Siapkan dokumen resmi, misalnya berita acara/keputusan rapat, lalu isi nomor dokumennya pada `Nomor Dokumen Persetujuan`.
3. Isi alasan adjustment secara spesifik.
4. Simpan adjustment. Jika ada adjustment aktif sebelumnya untuk siswa-mapel-tahun yang sama, adjustment lama otomatis dibatalkan dan digantikan.
5. Jika adjustment salah, gunakan aksi `Batalkan` dan isi alasan pembatalan.

Output raport guru, cetak raport, dashboard siswa, dan API mobile memakai nilai adjustment aktif sebagai nilai akhir, serta tetap mempertahankan jejak audit pada tabel `report_score_adjustments`.

## 7) Master Akademik

Buka menu:

```text
/admin/akademik/tahun-ajaran
/admin/akademik/mapel
/admin/sekolah/kelas
/admin/akademik/jadwal
/admin/akademik/adjustment-raport
```

Konfigurasi penting:

| Area | Field | Value | Dampak ke Guru |
| --- | --- | --- | --- |
| Tahun ajaran | `name`, `semester`, `is_active` | Contoh `2026/2027`, `Ganjil`, aktif/nonaktif | Absensi, nilai, dan laporan memakai tahun aktif atau filter periode. |
| Mata pelajaran | `code`, `name`, `kkm` | Kode unik, nama mapel, angka KKM | Muncul di input nilai guru dan perhitungan raport. |
| Kelas | `name`, `grade_level`, `program_type`, `education_level`, `homeroom_teacher_id` | Lihat enum di bawah | Menentukan sidebar guru, akses kelas, wali kelas, peserta, dan jenis fitur yang tampil. |
| Jadwal | `class_id`, `teacher_id`, `subject_id`/`majlis_subject_id`, hari/jam | Sesuai form jadwal | Menentukan kelas dan mapel yang bisa diakses guru. |

Value `ProgramType`:

- `RQDF_SORE`
- `SEKOLAH_FULLDAY`
- `TAKHOSUS_TAHFIDZ`
- `MAJLIS_TALIM`
- `BAHASA`

Value `EducationLevel`:

- `NON_FORMAL`
- `SD`
- `SMP`
- `SMA`

Di `teacher.py`, kelas dikelompokkan menjadi:

| Program Kelas | Group Dashboard Guru | Fitur Sidebar |
| --- | --- | --- |
| `SEKOLAH_FULLDAY` atau default formal | `formal` | Raport perwalian, input nilai, absensi, perilaku, pengumuman, kelas online, AI Assistant. |
| `RQDF_SORE`, `TAKHOSUS_TAHFIDZ` | `rumah_quran` | Tahfidz, bacaan, evaluasi tahfidz, absensi, perilaku, pengumuman, kelas online, AI Assistant. |
| `BAHASA` | `bahasa` | Input nilai, absensi, perilaku, pengumuman, kelas online, AI Assistant. |
| `MAJLIS_TALIM` | `majlis` | Tahfidz, bacaan, evaluasi, absensi, perilaku, pengumuman, kelas online, AI Assistant. |

## 8) Assignment Guru

Assignment guru dibentuk dari:

- `homeroom_teacher_id` pada kelas.
- `StaffAssignment` yang dibuat/sinkron saat kelas disimpan.
- `Schedule` aktif dengan `teacher_id`.

Hal yang wajib benar:

- Guru dan kelas harus berada dalam tenant yang sama.
- Kelas harus memiliki `program_group_id` valid agar assignment modern dapat dibuat.
- Untuk guru mapel formal/bahasa, pastikan jadwal memiliki `subject_id`.
- Untuk majlis, gunakan `majlis_subject_id` bila fitur mapel majlis dipakai.

Jika guru tidak melihat kelas di dashboard guru, cek urutan ini:

1. User guru berada di tenant yang benar.
2. Paket tenant mengizinkan endpoint `teacher.*`.
3. Kelas masuk tenant aktif.
4. Guru dipasang sebagai wali kelas atau memiliki jadwal aktif.
5. Program type kelas sudah benar.

## 9) PPDB

Buka:

```text
/admin/ppdb/settings
/admin/ppdb/form-builder/<path_id>
```

Area yang bisa disesuaikan per tenant:

| Area | Field | Value |
| --- | --- | --- |
| Periode | `name`, `academic_year_label`, `start_date`, `end_date`, `registration_no_prefix`, `public_registration_enabled`, `status` | `DRAFT`, `OPEN`, `CLOSED` untuk status. |
| Program tenant | `code`, `name`, `system_type`, `education_level`, `category`, `sort_order`, `is_active` | `system_type` memakai `ProgramType`. |
| Jalur/jenis program | `code`, `name`, `tenant_program_id`, `education_level`, `scholarship_category`, `quota`, `sort_order`, `is_active` | Kuota boleh kosong atau angka >= 0. |
| Field formulir | `field_key`, `label`, `field_type`, `is_required`, `options`, `sort_order`, `is_active` | `TEXT`, `TEXTAREA`, `NUMBER`, `DATE`, `SELECT`, `BOOLEAN`. |
| Dokumen | `code`, `name`, `is_required`, `allowed_file_types`, `max_file_size_kb`, `sort_order`, `is_active` | Contoh file type: `pdf,jpg,png`. |
| Biaya | `name`, `amount`, `sort_order`, `is_active` | Nominal rupiah integer, tidak negatif. |

Value enum tambahan:

- `ScholarshipCategory`: `NON_BEASISWA`, `TAHFIDZ_5_JUZ`, `TAHFIDZ_10_30_JUZ`, `YATIM_DHUAFA`.
- `PpdbPeriodStatus`: `DRAFT`, `OPEN`, `CLOSED`.

## 10) Finance Settings

Buka:

```text
/admin/keuangan/settings
```

Pengaturan ini tersimpan di `FinanceSetting` dan `FinancePeriod`, bukan `AppConfig`.

| Field | Value | Dampak |
| --- | --- | --- |
| `accounting_basis` | `CASH` atau `ACCRUAL` | Basis pencatatan finance. |
| `default_cash_bank_account_id` | ID kas/bank tenant | Akun kas/bank default untuk posting. |
| `default_spp_revenue_account_id` | ID akun pendapatan | Default pendapatan SPP. |
| `default_registration_revenue_account_id` | ID akun pendapatan | Default pendapatan pendaftaran. |
| `default_savings_liability_account_id` | ID akun kewajiban | Default kewajiban tabungan siswa. |
| `default_donation_revenue_account_id` | ID akun pendapatan | Default pendapatan donasi. |
| Finance period `status` | `OPEN`, `CLOSED`, `LOCKED` | Posting transaksi hanya aman saat periode terkait terbuka. |

## 11) Checklist Setup Tenant Baru

1. Login sebagai `SUPER_ADMIN`.
2. Buat tenant di `/admin/platform/tenants`.
3. Pilih `tenant.module_package` sesuai kebutuhan tenant.
4. Isi `institution_name`, `institution_address`, dan `institution_phone`.
5. Buat admin tenant.
6. Login sebagai admin tenant.
7. Buat tahun ajaran dan aktifkan.
8. Buat mata pelajaran bila paket mendukung sekolah formal.
9. Buat kelas dengan `program_type` dan `education_level` yang benar.
10. Tambahkan guru dan pasang sebagai wali kelas atau pengampu jadwal.
11. Tambahkan siswa dan masukkan ke kelas/program.
12. Isi `grade_formula_weights` bila bobot nilai tenant berbeda dari default.
13. Atur PPDB bila tenant membuka pendaftaran publik.
14. Atur finance settings bila tenant memakai modul keuangan.
15. Uji login guru dan pastikan kelas muncul di dashboard guru.

## 12) Troubleshooting Cepat

| Gejala | Penyebab Umum | Cek |
| --- | --- | --- |
| Guru tidak bisa membuka dashboard guru | Paket tenant memblokir `teacher.*` atau role bukan `GURU` | `tenant.module_package`, role user. |
| Guru tidak melihat kelas | Tidak menjadi wali kelas, tidak ada jadwal aktif, atau kelas beda tenant | `homeroom_teacher_id`, `Schedule.teacher_id`, tenant user. |
| Nilai akhir tidak sesuai | JSON `grade_formula_weights` salah atau bobot subject/year override | Validasi JSON dan ID mapel/tahun ajaran. |
| PPDB publik tidak tampil | Periode belum `OPEN`, tanggal tidak aktif, domain belum cocok | Status periode, tanggal, `ppdb_public_domain`. |
| Data tenant tercampur | User/profil/kelas tidak punya relasi tenant yang konsisten | Cek `User.tenant_id`, group/program kelas, assignment. |
| Finance posting gagal | Periode belum `OPEN` atau akun default belum valid | Finance settings dan finance period. |
