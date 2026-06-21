# Package Capability Matrix V2

Tanggal: 2026-06-21  
Mode: analysis/design only  
Scope: SaaS package/capability model untuk authorization web dan mobile  
Tidak dilakukan: perubahan kode aplikasi, decorator, policy existing, migration, atau deploy.

## 1. Current Model

Model yang ada di codebase saat ini berbasis config `AppConfig` key `tenant.module_package` dengan tiga value:

| Legacy package | Constant | Meaning saat ini |
|---|---|---|
| `full` | `PACKAGE_FULL` | Semua role dan endpoint package guard diizinkan. |
| `sekolah` | `PACKAGE_SEKOLAH` | Fokus sekolah; blocking web terhadap `staff.*`, `boarding.*`, dan beberapa endpoint majlis. |
| `rumah_quran` | `PACKAGE_RUMAH_QURAN` | Fokus rumah quran/majlis; blocking web terhadap `teacher.*`, `student.*`, `boarding.*`, `parent.dashboard`, dan beberapa admin akademik sekolah. |

Mapping role/package existing:

| Legacy package | Role allowed |
|---|---|
| `full` | semua role |
| `sekolah` | `ADMIN`, `PIMPINAN`, `TU`, `GURU`, `SISWA`, `WALI_MURID` |
| `rumah_quran` | `ADMIN`, `PIMPINAN`, `TU`, `WALI_MURID`, `MAJLIS_PARTICIPANT` |

Kelemahan model lama:

1. Authorization bergantung pada nama package marketing lama, bukan capability bisnis yang stabil.
2. `full` terlalu luas dan menjadi default bila config tidak ada, sehingga tenant tanpa config mendapat semua modul.
3. `endpoint_allowed_for_package()` mengizinkan semua `api.*`, sehingga mobile API tidak mengikuti restriction package.
4. Guard web berbasis prefix endpoint dan exception list, bukan capability eksplisit.
5. Add-on seperti finance, PPDB, online class, dan AI assistant belum punya licensing boundary yang jelas.
6. Endpoint campuran seperti parent dashboard dan leadership dashboard memuat beberapa capability dalam satu response, sehingga sulit diputuskan hanya dari package name.
7. `BOARDING` dalam model bisnis baru bukan setara dengan package lama `full`; ia adalah SCHOOL + QURAN + boarding capability, belum tentu semua add-on.

## 2. Target Model

Authorization jangka panjang harus berbasis capability:

```text
tenant_has_capability(tenant, capability)
```

Package marketing hanya sumber awal entitlement, bukan boundary yang dipakai langsung oleh route/decorator.

Package marketing target:

| Marketing package | Definisi bisnis |
|---|---|
| `QURAN` | Produk rumah quran/majlis/tahfidz dasar. |
| `SCHOOL` | Produk sekolah akademik dasar. |
| `BOARDING` | `SCHOOL` + `QURAN` + capability boarding. Bukan package terpisah murni. |
| `INTEGRATED` | `BOARDING` + semua add-on. |

Add-on berbayar lintas paket:

| Add-on | Capability |
|---|---|
| `FINANCE` | `finance` |
| `PPDB` | `ppdb` |
| `ONLINE_CLASS` | `online_class` |
| `AI_ASSISTANT` | `ai_assistant` |

Aturan add-on:

- Tenant `QURAN`, `SCHOOL`, dan `BOARDING` harus membeli add-on terpisah.
- Tenant `INTEGRATED` mendapat semua add-on.
- `analytics` perlu diputuskan apakah base capability untuk admin/leadership atau add-on/reporting premium.
- `announcement` sebaiknya base capability yang mengikuti domain target, bukan add-on mandiri di tahap awal.

## 3. Capability Matrix

Capability minimal:

| Capability | Deskripsi | Contoh route/fitur |
|---|---|---|
| `quran` | Tahfidz, bacaan, evaluasi Quran, program rumah quran. | teacher input tahfidz/bacaan/evaluasi, parent memorization report |
| `school_academic` | Akademik sekolah formal: kelas, mapel, jadwal, nilai, absensi, raport. | admin akademik, teacher grades/attendance, student dashboard |
| `teacher` | Portal/operasi guru. Biasanya melekat pada `school_academic`, tetapi tetap capability terpisah untuk authorization endpoint. | web/mobile teacher dashboard, input nilai, input absensi |
| `student` | Portal/data siswa dan learner school-facing. | student dashboard, parent child academic endpoints |
| `parent` | Portal wali murid/orang tua. Perlu sub-policy karena parent bisa school atau quran/majlis. | parent dashboard, children, reports |
| `boarding` | Asrama, wali asrama, dormitory, boarding attendance, boarding savings operations. | web/mobile boarding |
| `majlis` | Peserta majlis dan majlis parent participation. | web parent majlis, mobile majlis dashboard |
| `finance` | Billing, kasir, invoice, GL, cash/bank, laporan keuangan, savings ledger. | admin/staff keuangan, parent finance, boarding savings posting |
| `ppdb` | Penerimaan peserta didik baru dan konfigurasi form/fee PPDB. | admin/staff PPDB, public PPDB form |
| `online_class` | Kelas online, session, material, assignment. | teacher/student online class |
| `ai_assistant` | AI assistant documents, request, output. | teacher AI assistant |
| `analytics` | Dashboard ringkasan, leadership drilldown, operational analytics. | admin/pimpinan dashboard, finance/PPDB summary |
| `announcement` | Pengumuman lintas domain. | staff announcement, teacher class announcement, majlis announcement |

Catatan desain:

- Capability endpoint boleh lebih dari satu. Contoh `/parent/children/<id>/savings` membutuhkan `parent` dan `boarding` atau `finance` tergantung keputusan licensing savings.
- Capability role bukan pengganti RBAC. User tetap harus punya role yang sesuai setelah tenant punya capability.
- `teacher` dan `school_academic` sengaja dipisah agar route guru bisa dicek jelas, sementara data akademik/admin bisa memakai `school_academic`.

## 4. Package-to-Capability Mapping

Target mapping awal:

| Package marketing | Base capabilities |
|---|---|
| `QURAN` | `quran`, `parent`, `majlis`, `announcement`, `analytics` basic |
| `SCHOOL` | `school_academic`, `teacher`, `student`, `parent`, `announcement`, `analytics` basic |
| `BOARDING` | semua capability `SCHOOL` + semua capability `QURAN` + `boarding` |
| `INTEGRATED` | semua capability `BOARDING` + semua add-on capabilities |

Detail:

- `BOARDING` harus punya `school_academic`, `teacher`, `student`, `parent`, `quran`, `majlis`, `boarding`, `announcement`, dan analytics basic.
- `INTEGRATED` harus punya `finance`, `ppdb`, `online_class`, dan `ai_assistant` tanpa add-on tambahan.
- `announcement` dapat dianggap base karena pengumuman dibutuhkan di QURAN/SCHOOL/BOARDING, tetapi target audience tetap harus divalidasi oleh domain capability terkait.
- `analytics` basic boleh diberikan ke semua package untuk dashboard dasar. Analytics premium/reporting lanjutan perlu keputusan terpisah jika ingin dilisensikan.

## 5. Add-on-to-Capability Mapping

| Add-on | Capability unlocked | Applies to |
|---|---|---|
| `FINANCE` | `finance` | `QURAN`, `SCHOOL`, `BOARDING`; included in `INTEGRATED` |
| `PPDB` | `ppdb` | `QURAN`, `SCHOOL`, `BOARDING`; included in `INTEGRATED` |
| `ONLINE_CLASS` | `online_class` | `QURAN`, `SCHOOL`, `BOARDING`; included in `INTEGRATED` |
| `AI_ASSISTANT` | `ai_assistant` | `QURAN`, `SCHOOL`, `BOARDING`; included in `INTEGRATED` |

Recommended semantics:

- Add-on capability is tenant-level entitlement, not user-level permission.
- RBAC still controls who can use it after entitlement passes.
- Add-on enforcement should start as read-only/tested policy before blocking production routes, especially for finance.

## 6. Backward Compatibility Plan

Tidak perlu migration besar untuk AUTH-PACKAGE-003. Tambahkan adapter konseptual dari package lama ke capability baru:

| Legacy package | Interpreted target equivalent | Capabilities via adapter |
|---|---|---|
| `full` | `INTEGRATED` for compatibility | all base capabilities + all add-ons |
| `sekolah` | `SCHOOL` | `school_academic`, `teacher`, `student`, `parent`, `announcement`, basic `analytics` |
| `rumah_quran` | `QURAN` | `quran`, `parent`, `majlis`, `announcement`, basic `analytics` |

Adapter behavior:

1. Read current `tenant.module_package`.
2. Normalize legacy value exactly as existing code does.
3. Convert to a capability set in memory.
4. Implement `tenant_has_capability(tenant_id, capability)` using the adapter.
5. Keep existing `get_tenant_package()`, `role_allowed_for_package()`, and `endpoint_allowed_for_package()` behavior unchanged during Phase 1.
6. Use the capability helper only for new AUTH-PACKAGE-003 mobile checks and focused characterization tests.

Important compatibility caveat:

- Treating legacy `full` as `INTEGRATED` preserves current behavior, but it also means tenants without config still get every capability because `get_tenant_package()` defaults to `full`. That should be documented as a known risk and fixed in a later migration/config-hardening phase, not silently changed in AUTH-PACKAGE-003.

## 7. Recommended Implementation Phases

### Phase 1 - Capability helper without migration

Goal: close AUTH-PACKAGE-003 for clear mobile modules without changing storage.

Work:

- Add capability constants and a helper such as `tenant_has_capability(tenant_id, capability)`.
- Back it with adapter mapping from legacy packages.
- Add small helper for route capability decisions, but do not replace all web guard behavior yet.
- Use it for AUTH-PACKAGE-003 on mobile `teacher`, `boarding`, and `majlis` endpoints only.
- Keep auth/common endpoints unaffected except existing tenant lifecycle checks.
- Add tests proving:
  - legacy `full` allows teacher/boarding/majlis;
  - legacy `sekolah` allows teacher and blocks boarding/majlis;
  - legacy `rumah_quran` allows majlis and blocks teacher/boarding;
  - mobile and web decisions align for these three modules.

Why this phase is safe:

- No schema change.
- No marketing package migration.
- Scope avoids ambiguous finance, PPDB, online class, AI assistant, and mixed parent endpoints.
- It directly fixes the HIGH finding that mobile API bypasses module restriction.

### Phase 2 - Define add-on licensing

Goal: prepare add-on enforcement without blocking routes prematurely.

Work:

- Define canonical add-on keys: `FINANCE`, `PPDB`, `ONLINE_CLASS`, `AI_ASSISTANT`.
- Decide storage source for add-ons during transition, likely `AppConfig` keys, without schema change if possible.
- Add non-blocking tests or policy tests for `finance`, `ppdb`, `online_class`, and `ai_assistant`.
- Inventory route groups:
  - finance: admin `/keuangan/*`, staff cashier/billing, parent finance, boarding savings posting;
  - ppdb: admin/staff PPDB, public PPDB form and candidate flow;
  - online class: teacher/student `/kelas-online`;
  - AI assistant: teacher `/ai-assistant`.
- Do not enforce finance add-on until data model and operational expectations are clear.

### Phase 3 - Persist target package/add-ons if needed

Goal: move storage from legacy package values to first-class SaaS entitlement.

Options:

- Add `package_type` and add-on storage to tenant/config model via migration.
- Keep `AppConfig` but introduce canonical keys such as `tenant.package_type` and `tenant.addons`.
- Backfill old values:
  - `full` -> `INTEGRATED`;
  - `sekolah` -> `SCHOOL`;
  - `rumah_quran` -> `QURAN`.
- Add explicit default for tenants without config; do not rely on implicit `full`.
- Update admin/platform UI to manage package type and add-ons.
- After rollout, deprecate direct use of legacy constants from authorization code.

## 8. Risk Analysis

### Mobile regression

Mobile clients may have used endpoints that were unintentionally available under legacy package restrictions. Phase 1 should return clear `403` for teacher/boarding/majlis only where web already denies equivalent modules.

### Web/mobile consistency

During transition, web uses `endpoint_allowed_for_package()` and mobile may use `tenant_has_capability()`. Tests must compare decisions for teacher, boarding, and majlis to prevent policy drift.

### Tenant without config defaults to full

Existing `get_tenant_package()` returns `full` when no config exists. The adapter must preserve this in Phase 1, but the risk should remain visible because it gives every capability to misconfigured tenants.

### Finance add-on

Finance appears in many places:

- admin `/keuangan/*`;
- staff cashier/billing routes;
- parent `/children/<id>/finance`;
- parent/boarding savings;
- dashboard summaries and finance posting services.

Blocking `finance` too early can break dashboards, billing, savings workflows, and posting side effects. Finance should be designed as licensed capability in Phase 2, with enforcement postponed until add-on data and route boundaries are ready.

### Parent endpoint campuran

Parent endpoints combine school academic, Quran memorization, finance, announcement, and boarding-adjacent savings/attendance. A single endpoint-level capability can over-block or leak partial module data. Recommended approach:

- Phase 1: do not enforce parent mixed endpoints except majlis-specific mobile/web routes already clear.
- Later: either split endpoints by capability or filter response sections by capability with explicit tests.

### Announcement capability

Announcement is cross-domain. Treating it as global is convenient but can leak target-domain data if audience filtering is weak. Better rule: tenant needs `announcement`, and the target domain also must be allowed where applicable.

### Add-on storage ambiguity

Without a canonical add-on storage model, `tenant_has_capability()` can only infer base package capabilities. Add-on capabilities should not be enforced from guesses.

## 9. Human Decisions Required

1. Is legacy `full` definitely equivalent to `INTEGRATED` during transition?
2. Should tenants without `tenant.module_package` continue to default to all capabilities until migration, or should platform audit/fix configs first?
3. Is `analytics` included as basic capability for all packages, or should advanced analytics become a separate add-on?
4. Does `announcement` belong to all packages, or should announcement creation require the target module capability?
5. For `QURAN`, should `parent` include only majlis/Quran parent views, or also child/student views where the child is in a Quran program?
6. For `SCHOOL`, should Quran/tahfidz fields inside teacher/parent endpoints be hidden, blocked, or allowed when they are attached to school students?
7. Is boarding savings licensed by `boarding`, `finance`, or both?
8. Should PPDB be available for QURAN package, SCHOOL package, or both as an add-on?
9. What is the API error contract for disabled capability: `module_disabled`, `capability_disabled`, or existing `forbidden`?
10. Should `SUPER_ADMIN` bypass capability checks in mobile API, or is super admin mobile unsupported?

## 10. Recommendation for AUTH-PACKAGE-003

AUTH-PACKAGE-003 can continue without waiting for package/add-on migration.

Recommended scope:

- Implement a capability helper backed by legacy adapter.
- Enforce only clear mobile module groups first:
  - teacher endpoints require `teacher`;
  - boarding endpoints require `boarding`;
  - majlis endpoints require `majlis`.
- Keep parent mixed endpoints, finance, PPDB, online class, AI assistant, and analytics out of enforcement until Phase 2/3 decisions.

This approach fixes the immediate mobile bypass while aligning the implementation direction with the SaaS Nizamiya model. Migration for `package_type` and add-ons is useful later, but it is not a prerequisite for AUTH-PACKAGE-003 Phase 1.

