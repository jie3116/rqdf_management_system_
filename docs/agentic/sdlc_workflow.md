# Workflow SDLC Agentic RQDF

Workflow ini memakai agent sebagai peran kerja berbasis dokumen. Agent boleh dijalankan oleh satu atau beberapa sesi Codex, tetapi artefak dan quality gate tetap sama.

## 0. Intake dan scope control

1. Buat salinan `specs/feature_spec_template.md` menjadi `specs/<feature>.md`.
2. Catat tujuan, owner, scope, out-of-scope, dan sistem production yang terdampak.
3. Jangan mengubah kode pada tahap ini.

**Gate:** scope cukup jelas untuk dianalisis.

## 1. Requirement analysis

Requirement Analyst mengisi:

- user stories;
- acceptance criteria;
- business rules;
- edge cases;
- role/tenant permission matrix;
- ambiguity, assumptions, dan open questions.

Jika keputusan bisnis masih terbuka, workflow berhenti pada requirement gate.

**Output:** feature spec dengan requirement yang dapat diuji.

## 2. Architecture analysis

Architecture Agent membaca spec dan kode existing yang relevan secara read-only, lalu menulis:

- data flow;
- route/blueprint/service/model/API/template impact;
- file impact plan;
- transaction boundary;
- tenant, role, ownership, dan soft-delete handling;
- compatibility, risiko, dan urutan implementasi.

**Gate:** desain mengikuti baseline atau deviasinya disetujui.

## 3. Implementation planning

Pecah pekerjaan menjadi patch kecil:

1. safety/characterization test bila behavior existing belum terlindungi;
2. model/migration draft bila diperlukan;
3. service/domain behavior;
4. route/API/template integration;
5. test dan dokumentasi.

Pisahkan refactor non-esensial ke backlog maintenance.

## 4. Database design dan migration review

Tahap ini hanya berlaku bila schema/data berubah.

Database & Migration Agent mereview model dan migration. Untuk perubahan berisiko, gunakan pola:

1. **Expand:** tambah schema yang backward-compatible.
2. **Backfill:** isi data secara idempotent dan terukur.
3. **Switch:** aplikasi mulai memakai schema baru.
4. **Contract:** hapus schema lama pada release terpisah setelah aman.

Membuat draft migration tidak sama dengan menjalankannya. `flask db upgrade`, downgrade, dan backfill memerlukan approval manusia.

**Gate:** migration dinyatakan aman atau memiliki conditions yang eksplisit.

## 5. Backend implementation

Backend Implementation Agent bekerja hanya dari spec dan architecture plan yang disetujui.

- Route: parsing request, auth, service call, response.
- Service: business rule, state transition, data access orchestration, transaction.
- Model: persistence rule dan relationship.
- Helper/serializer: transformasi reusable.

Setelah tiap patch, catat file berubah, asumsi, dan verifikasi.

## 6. Testing dan QA

Testing & QA Agent menurunkan test dari acceptance criteria dan risk register.

Urutan verifikasi:

1. test paling dekat dengan perubahan;
2. test domain/modul;
3. full pytest suite bila sesuai risiko;
4. PostgreSQL-specific/manual test bila SQLite tidak cukup.

Jika test gagal, dokumentasikan root cause sebelum memperbaiki. Simpan laporan di `reviews/<feature>/test_report.md`.

**Gate:** acceptance criteria memiliki bukti dan residual risk dinyatakan.

## 7. Independent reviews

Jalankan reviewer dengan scope yang eksplisit:

1. Security Reviewer
2. Performance Reviewer
3. Code Review Agent

Reviewer membaca spec, diff, dan test evidence. Reviewer default read-only. Temuan disimpan di `reviews/<feature>/`.

**Gate:** tidak ada temuan HIGH/CRITICAL yang unresolved tanpa keputusan manusia. Temuan lain harus fixed, accepted, atau dijadwalkan dengan owner.

## 8. Documentation

Documentation Agent menyelaraskan:

- dokumentasi fitur;
- API contract;
- migration notes;
- operational runbook;
- ADR;
- release notes.

Dokumentasi harus menggambarkan behavior final.

## 9. Release readiness

Deployment & Release Agent mengisi `checklists/deployment.md`:

- commit/image identity;
- backup dan restore readiness;
- migration sequence;
- deployment sequence;
- smoke tests;
- monitoring;
- rollback trigger dan steps.

Agent tidak menjalankan migration atau deploy.

**Gate:** human approval untuk tindakan production.

## 10. Deploy dan observasi

Dilakukan oleh manusia/operator yang berwenang sesuai runbook:

1. konfirmasi backup;
2. jalankan langkah release yang disetujui;
3. smoke test;
4. observasi log/metric/error;
5. rollback bila trigger tercapai.

Catat hasil aktual di release review.

## 11. Post-release dan maintenance

- Tutup open question.
- Catat incident/lesson learned.
- Buat technical-debt item yang terpisah.
- Maintenance & Refactoring Agent menyusun perubahan kecil, bukan refactor besar bersamaan dengan release fitur.

## Jalur audit aplikasi production

Audit berbeda dari delivery fitur:

1. Tentukan domain sempit dan read-only.
2. Buat `reviews/<audit-scope>/`.
3. Petakan entrypoint, role, tenant boundary, data, dan endpoint.
4. Jalankan security, testing-gap, performance, lalu code maintainability review.
5. Prioritaskan temuan; jangan langsung memperbaiki semuanya.
6. Untuk tiap fix, buka feature/hardening spec baru dan jalankan workflow normal.

Audit seluruh aplikasi tidak dimulai tanpa approval manusia.

