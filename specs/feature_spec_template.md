# Feature Spec: <Nama Fitur>

## Metadata

- Status: `DRAFT | REQUIREMENT REVIEW | ARCHITECTURE REVIEW | APPROVED | IMPLEMENTING | VERIFYING | RELEASE READY | RELEASED`
- Owner:
- Requirement Analyst:
- Architecture Reviewer:
- Target release:
- Related issue:
- Last updated:

## Ringkasan

Jelaskan masalah bisnis, pengguna terdampak, dan hasil yang diinginkan dalam 2–4 paragraf.

## Goals

- 

## Out of scope

- 

## Current behavior

Jelaskan behavior existing dan sertakan file/route/API yang relevan.

## User stories

### US-01

Sebagai `<role>`, saya ingin `<capability>`, sehingga `<business outcome>`.

## Acceptance criteria

Gunakan hasil yang dapat diamati dan diuji.

- AC-01:
- AC-02:

## Role dan permission matrix

| Aksi | Super Admin | Admin | Pimpinan | TU | Guru | Wali Asrama | Wali Murid | Siswa | Peserta Majlis | Tenant/ownership rule |
|---|---|---|---|---|---|---|---|---|---|---|
| Contoh |  |  |  |  |  |  |  |  |  |  |

## Business rules

- BR-01:

## Edge cases dan failure behavior

| ID | Kondisi | Expected behavior |
|---|---|---|
| EC-01 |  |  |

## API contract

Isi bila ada perubahan `/api/v1`.

- Endpoint/method:
- Authentication:
- Request:
- Success response:
- Error responses:
- Backward compatibility:

## UI/web flow

Isi bila ada perubahan route/template/form.

## Data dan migration impact

- Model/table/column:
- Nullable/default:
- Index/FK/unique:
- Backfill:
- Compatibility:
- Rollback consideration:
- Migration execution: **memerlukan approval manusia**

## Architecture impact

- Blueprint/route:
- Service:
- Model:
- Helper/serializer:
- Template/API:
- Transaction boundary:
- Tenant/role/soft-delete handling:
- External dependency:

## File impact plan

| File/modul | Jenis perubahan | Alasan |
|---|---|---|
|  |  |  |

## Testing plan

- Unit:
- Integration:
- Permission/tenant:
- Edge case:
- PostgreSQL-specific:
- Manual smoke:

## Security considerations

- 

## Performance considerations

- 

## Deployment dan rollback

- Release sequence:
- Feature flag/compatibility:
- Backup:
- Smoke test:
- Monitoring:
- Rollback trigger:
- Rollback steps:

## Documentation impact

- Feature docs:
- API docs:
- Migration notes:
- Runbook:
- ADR:

## Risks, assumptions, dan open questions

| Tipe | Item | Owner | Status/decision |
|---|---|---|---|
| Risk |  |  |  |
| Assumption |  |  |  |
| Question |  |  |  |

## Approval gates

- [ ] Requirement approved
- [ ] Architecture approved
- [ ] Database plan approved, bila relevan
- [ ] Implementation complete
- [ ] Test evidence complete
- [ ] Security review complete
- [ ] Performance review complete atau N/A
- [ ] Code review complete
- [ ] Documentation complete
- [ ] Release plan complete
- [ ] Human approval untuk migration/deploy

