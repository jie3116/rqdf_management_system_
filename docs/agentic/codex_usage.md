# Menggunakan Codex dengan Multi-Agent RQDF

Codex dapat menjalankan peran agent secara berurutan. Keandalan berasal dari scope, dokumen handoff, dan quality gate—bukan dari banyaknya percakapan.

## Memulai fitur baru

Berikan instruksi awal:

> Baca `AGENTS.md` dan `docs/agentic/sdlc_workflow.md`. Kita akan mengerjakan fitur `<nama>`. Mulai hanya sebagai Requirement Analyst Agent. Buat `specs/<nama>.md` dari template. Jangan ubah kode, migration, atau production config. Berhenti setelah requirement gate dan tampilkan open questions.

Setelah requirement disetujui:

> Lanjutkan sebagai Architecture Agent untuk `specs/<nama>.md`. Analisis kode terkait secara read-only, isi architecture impact dan file impact plan. Jangan implementasi.

Setelah architecture disetujui:

> Lanjutkan sebagai Backend Implementation Agent. Implementasikan hanya scope yang approved dalam patch kecil. Jangan jalankan migration atau deploy. Setelah perubahan, jalankan test relevan dan laporkan bukti.

## Menjalankan agent database

> Bertindak sebagai Database & Migration Agent. Review perubahan model dan draft migration fitur `<nama>`. Gunakan `checklists/deployment.md` untuk compatibility concern. Jangan menjalankan upgrade/downgrade/backfill. Simpan review di `reviews/<nama>/database_review.md`.

Selalu bedakan:

- membuat atau mereview migration;
- menjalankan migration pada environment tertentu.

Yang kedua memerlukan approval manusia.

## Menjalankan reviewer independen

Gunakan sesi baru atau minta Codex mengabaikan asumsi implementer:

> Bertindak sebagai Security Reviewer Agent read-only. Scope hanya diff dan endpoint fitur `<nama>`. Baca spec, permission matrix, dan `checklists/security.md`. Simpan temuan di `reviews/<nama>/security_review.md`. Jangan membuat patch sampai saya approve.

Ulangi untuk performance dan code review dengan checklist masing-masing.

## Meminta patch dari sebuah temuan

Jangan memberi perintah umum seperti “fix semua”. Gunakan finding ID:

> Implementasikan perbaikan untuk `SEC-02` dari `reviews/<nama>/security_review.md`. Pertahankan scope, tambahkan regression test, jangan mengubah finding lain, migration, atau config production.

Kemudian minta reviewer memverifikasi ulang finding tersebut.

## Audit aplikasi production secara aman

Mulai dari domain kecil:

> Buat audit read-only untuk mobile authentication `/api/v1/auth/*`. Baca `AGENTS.md`, gunakan Security Reviewer Agent, dan simpan output di `reviews/audit-mobile-auth/`. Jangan mengubah kode dan jangan memperluas scope.

Setelah hasil keluar:

1. triage severity dan bukti;
2. pilih temuan yang akan diperbaiki;
3. buat hardening spec terpisah;
4. jalankan workflow fitur normal;
5. release dengan checklist dan approval manusia.

## Prompt orkestrasi lengkap

> Baca `AGENTS.md`. Orkestrasi fitur `<nama>` melalui Requirement Analyst, Architecture, Backend Implementation, Database & Migration bila relevan, Testing & QA, Security Reviewer, Performance Reviewer, Code Review, Documentation, dan Deployment & Release. Patuhi setiap quality gate. Berhenti untuk approval saya sebelum implementasi, sebelum menjalankan migration, dan sebelum deploy. Simpan spec di `specs/` dan review di `reviews/<nama>/`.

## Informasi yang sebaiknya selalu diberikan

- tujuan bisnis dan role pengguna;
- endpoint/flow/file yang diduga relevan;
- behavior existing dan behavior target;
- data/tenant constraints;
- out-of-scope;
- apakah Codex boleh mengubah kode atau hanya review;
- command test yang diizinkan;
- environment yang boleh disentuh;
- approval gate yang wajib.

## Tanda output agent yang baik

- menunjuk file dan behavior aktual;
- menyatakan asumsi dan bagian yang belum diverifikasi;
- memisahkan fakta dari rekomendasi;
- memiliki acceptance criteria/test evidence;
- perubahan kecil dan sesuai scope;
- tidak mengklaim deploy/migration dilakukan jika belum;
- menghasilkan handoff yang dapat dipakai agent berikutnya.

## Tanda workflow perlu dihentikan

- requirement bisnis masih ambigu;
- permission matrix belum disepakati;
- migration berpotensi merusak data atau lock tanpa strategi;
- test gagal tanpa root cause;
- reviewer menemukan HIGH/CRITICAL unresolved;
- rollback atau backup belum siap;
- tindakan membutuhkan akses/approval production yang belum diberikan.

