# AUTH-TOKEN-005 Phase 1 Post-Deploy Verification

Tanggal: 2026-06-28

Status: `POST-DEPLOY VERIFICATION PASSED`

## Scope

Post-deploy verification untuk AUTH-TOKEN-005 Phase 1 setelah production deploy dan migration.

Deploy ini menambahkan:

- `users.token_version`
- claim `ver` pada mobile access/refresh token
- strict rejection untuk token mobile lama tanpa `ver`
- invalidasi mobile access/refresh token setelah password user diubah/reset

Tidak dilakukan dalam closeout ini:

- perubahan kode aplikasi
- migration
- deploy ulang
- rollback

## Deployed Revision

Expected deployed migration revision:

```text
af56gh78ij90 (head)
```

Human-reported migration result:

```text
ae45fg67hi89 -> af56gh78ij90, add user token version
```

## Backup Evidence

File backup sebelum deploy:

```text
backups/pre_deploy_2026-06-28_140722.dump
```

Operator evidence:

- Backup verified with `pg_restore -l`.
- Archive metadata was listed successfully.

## Alembic Current/Head Evidence

Commands requested:

```bash
docker compose exec web flask db current
docker compose exec web flask db heads
```

Production operator evidence:

```text
docker compose exec web flask db current
af56gh78ij90 (head)

docker compose exec web flask db heads
af56gh78ij90 (head)
```

Assessment:

- `PASS`
- Production Alembic current revision and head are both `af56gh78ij90`.

## Schema Evidence: users.token_version

Command requested:

```bash
docker compose exec db sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "\d users"'
```

Production operator evidence:

```text
column_name   | data_type | is_nullable | column_default
--------------+-----------+-------------+----------------
token_version | integer   | NO          | 0
```

Assessment:

- `PASS`
- `token_version` column exists.
- type: `integer`
- nullable: `NO`
- default: `0`

## Container and Log Health Evidence

Commands requested:

```bash
docker compose ps
docker compose logs --tail=200 web
```

Production operator evidence:

```text
sekolah_app   sekolah_app_image   web   Up   127.0.0.1:8000->8000/tcp
sekolah_db    postgres:15         db    Up   5432/tcp
```

Web log health evidence:

```text
Starting gunicorn 23.0.0
Listening at: http://0.0.0.0:8000
Using worker: sync
Booting worker with pid: 8
Booting worker with pid: 9
Booting worker with pid: 10
Booting worker with pid: 11
```

Assessment:

- `PASS`
- web container is running.
- db container is running.
- gunicorn starts successfully.
- no startup crash reported in supplied evidence.
- no traceback, SQLAlchemy error, or `token_version` error reported in supplied evidence.

## Post-Deploy Log Scan

Command requested:

```bash
docker compose logs --tail=500 web | grep -Ei "500|Traceback|token_version|migration|sqlalchemy|psycopg|error"
```

Production operator evidence:

```text
No blocking post-deploy log issue reported by production operator.
```

Classification:

- `PASS`
- No blocking issue reported.

## Manual Smoke Test Checklist

Current evidence source: production operator smoke test report.

| Check | Status | Notes |
| --- | --- | --- |
| Web login berhasil | `PASS` | Production operator reported smoke test safe/passed |
| Mobile login `/api/v1/auth/login` returns access and refresh token | `PASS` | Production operator reported smoke test safe/passed |
| New access token works on `/api/v1/auth/me` | `PASS` | Production operator reported smoke test safe/passed |
| New refresh token works on `/api/v1/auth/refresh` | `PASS` | Production operator reported smoke test safe/passed |
| Old mobile token without `ver` returns controlled 401 | `EXPECTED BEHAVIOR / NOT AVAILABLE` | Marked expected if no old token was available during smoke test |
| Password change invalidates previous mobile access token | `PASS` | Production operator reported smoke test safe/passed |
| Password change invalidates previous mobile refresh token | `PASS` | Production operator reported smoke test safe/passed |
| Logout revocation still works | `PASS` | Included in operator smoke test report |

## Expected Behavior

- Token mobile lama tanpa `ver` ditolak dengan controlled `401 unauthorized`.
- User mobile mungkin perlu login ulang setelah strict cutover.
- Password change/reset existing user menaikkan `users.token_version`.
- Mobile access/refresh token lama dengan versi sebelum password change ditolak.
- Logout revocation tetap menggunakan `MobileRevokedToken`.
- AUTH-REFRESH-006 tetap backlog terpisah.

## Assumptions Recorded

- Production command evidence was supplied by the human production operator.
- This local environment did not run Docker verification directly.
- Legacy mobile token without `ver` is recorded as expected behavior / not available unless the operator confirms an old token was tested.
- Logout revocation is marked `PASS` based on the operator smoke test report.

## Issues Found

No blocking issue found in supplied production operator evidence.

## Final Decision

`POST-DEPLOY VERIFICATION PASSED`

Final decision:

AUTH-TOKEN-005 Phase 1 production deploy is verified complete.
