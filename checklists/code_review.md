# Code Review Checklist

## Correctness

- [ ] Patch memenuhi spec dan acceptance criteria.
- [ ] Edge case dan failure path ditangani.
- [ ] Transaction commit/rollback konsisten.
- [ ] State transition dan idempotency benar.
- [ ] Tidak ada regression yang terlihat pada flow existing.

## Architecture dan data boundaries

- [ ] Factory, blueprint, dan service layer dipertahankan.
- [ ] Route tipis; business rule tidak tersebar.
- [ ] Tenant, role, ownership, dan soft-delete benar.
- [ ] Model/migration/API changes compatible.
- [ ] Coupling baru memiliki alasan.

## Maintainability

- [ ] Naming jelas dan konsisten.
- [ ] Fungsi memiliki tanggung jawab fokus.
- [ ] Duplication signifikan tidak ditambah.
- [ ] Error handling spesifik dan dapat ditelusuri.
- [ ] Logging berguna, tidak noisy, dan tidak membocorkan data.
- [ ] Comment menjelaskan alasan, bukan mengulang kode.

## Verification

- [ ] Test mencakup risiko utama.
- [ ] Test tidak terlalu bergantung pada implementation detail.
- [ ] Command dan hasil test tersedia.
- [ ] Diff bebas perubahan di luar scope.
- [ ] Dokumentasi relevan diperbarui.

