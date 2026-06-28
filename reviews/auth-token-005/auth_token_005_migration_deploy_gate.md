# AUTH-TOKEN-005 Phase 1 Migration + Deploy Gate

Tanggal: 2026-06-28

Status:

- `READY FOR HUMAN MIGRATION/DEPLOY APPROVAL` jika seluruh pre-check di bawah lulus.
- `NOT APPROVED TO RUN MIGRATION UNTIL HUMAN SAYS YES`.
- `NOT APPROVED TO DEPLOY UNTIL HUMAN SAYS YES`.

Scope:

- AUTH-TOKEN-005 Phase 1.
- Migration adds `users.token_version INTEGER NOT NULL DEFAULT 0`.
- Strict mobile token cutover: old mobile tokens without `ver` are rejected with controlled `401 unauthorized`.
- Mobile users may be forced to log in again after deploy.

Out of scope:

- `AUTH-REFRESH-006` refresh rotation race remediation.
- Nginx config changes, unless separately approved.
- Any production DB operation without explicit human approval.

## 1. Pre-Deploy Checks

Run from the production checkout directory.

### Verify Current Branch

```powershell
git branch --show-current
```

Expected:

- Branch is the approved production/release branch.

### Verify Latest Commit

```powershell
git log -1 --oneline
git show --stat --oneline -1
```

Expected:

- Latest commit is the approved AUTH-TOKEN-005 Phase 1 commit.
- Commit includes only expected implementation/review files.

### Verify Working Tree

```powershell
git status --short
```

Expected:

- Clean working tree; or
- Only known unrelated documentation changes that will not be deployed from this checkout.

Do not deploy if there are unexpected modified application, migration, config, Docker, or environment files.

### Verify Migration File Exists

```powershell
Test-Path migrations\versions\af56gh78ij90_add_user_token_version.py
Get-Content migrations\versions\af56gh78ij90_add_user_token_version.py
```

Expected migration content:

```python
op.add_column(
    "users",
    sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
)
```

Expected downgrade:

```python
op.drop_column("users", "token_version")
```

### Verify Migration Has Not Already Been Applied

Requires production DB access through the app environment.

```powershell
docker compose exec web flask db current
docker compose exec web flask db heads
```

Expected:

- Current DB revision is before `af56gh78ij90`.
- Alembic head includes `af56gh78ij90`.
- If current already equals/includes `af56gh78ij90`, stop and investigate. Do not run migration again.

Optional direct DB check:

```powershell
docker compose exec db psql -U $env:POSTGRES_USER -d $env:POSTGRES_DB -c "\d users"
```

Expected before migration:

- `token_version` column is not present.

### Verify Tests Passed Before Deploy

Run in the release environment or CI before production migration/deploy:

```powershell
$env:PYTHONPATH='.'; .\.venv\Scripts\pytest.exe tests/test_mobile_token_version_invalidation.py -q
$env:PYTHONPATH='.'; .\.venv\Scripts\pytest.exe tests/test_mobile_auth_tenant_status.py -q
$env:PYTHONPATH='.'; .\.venv\Scripts\pytest.exe tests/test_mobile_package_capabilities.py -q
$env:PYTHONPATH='.'; .\.venv\Scripts\pytest.exe tests/test_auth_rate_limit_integration.py tests/test_auth_rate_limit_service.py -q
```

Expected:

- All targeted AUTH-TOKEN/AUTH-TENANT/AUTH-PACKAGE/AUTH-RATE tests pass.

Known unrelated finance full-suite failure, if still present, must be accepted separately by human owner before release.

## 2. Production Backup

Run before any migration or deploy.

### Create Timestamped Backup Directory

PowerShell:

```powershell
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupDir = "backups\auth_token_005_$timestamp"
New-Item -ItemType Directory -Force -Path $backupDir
```

### Run `pg_dump` from `db` Container

Custom-format dump:

```powershell
docker compose exec db pg_dump -U $env:POSTGRES_USER -d $env:POSTGRES_DB -F c -f /tmp/auth_token_005_pre_migration.dump
docker compose cp db:/tmp/auth_token_005_pre_migration.dump "$backupDir\auth_token_005_pre_migration.dump"
```

### Verify Backup with `pg_restore -l`

```powershell
docker compose exec db pg_restore -l /tmp/auth_token_005_pre_migration.dump
```

Optional local verification if `pg_restore` is installed on host:

```powershell
pg_restore -l "$backupDir\auth_token_005_pre_migration.dump"
```

Expected:

- `pg_restore -l` lists database objects without errors.
- Backup file exists in the timestamped backup directory.

## 3. PostgreSQL Version / Lock Awareness

### Check PostgreSQL Version

```powershell
docker compose exec db psql -U $env:POSTGRES_USER -d $env:POSTGRES_DB -c "SHOW server_version;"
docker compose exec db psql -U $env:POSTGRES_USER -d $env:POSTGRES_DB -c "SELECT version();"
```

Lock note:

- `ALTER TABLE users ADD COLUMN token_version INTEGER NOT NULL DEFAULT 0` requires a table lock on `users`.
- PostgreSQL 11+ generally optimizes adding a constant default without rewriting the full table, but the DDL still needs an `ACCESS EXCLUSIVE` lock while it changes table metadata.
- Older PostgreSQL versions may rewrite the table.

Deployment requirement:

- Run migration in a maintenance-safe window.
- Avoid running while long transactions or heavy login/user-management traffic are active.

Optional lock inspection before migration:

```powershell
docker compose exec db psql -U $env:POSTGRES_USER -d $env:POSTGRES_DB -c "SELECT pid, state, wait_event_type, wait_event, query FROM pg_stat_activity WHERE datname = current_database() AND state <> 'idle';"
```

## 4. Migration Command

Requires explicit human approval.

Do not run until the human operator says yes.

```powershell
docker compose exec web flask db upgrade
```

Post-migration verification:

```powershell
docker compose exec web flask db current
docker compose exec db psql -U $env:POSTGRES_USER -d $env:POSTGRES_DB -c "\d users"
```

Expected:

- Alembic current revision includes `af56gh78ij90`.
- `users.token_version` exists as integer, not null, default `0`.

## 5. App Deploy / Restart Plan

Expected production sequence for this repo:

1. Pull or merge the approved AUTH-TOKEN-005 commit.

```powershell
git fetch --all --prune
git pull --ff-only
git log -1 --oneline
```

2. Rebuild/recreate app container if needed.

If image rebuild is required:

```powershell
docker compose build web
```

If only recreate/restart is needed:

```powershell
docker compose up -d web
```

3. Run migration at the approved point.

```powershell
docker compose exec web flask db upgrade
```

4. Restart/recreate web service after migration if not already recreated with new code.

```powershell
docker compose up -d web
```

5. Reload nginx only if nginx config changed.

AUTH-TOKEN-005 does not require nginx config changes. Do not reload nginx unless a separate approved nginx change is included.

If nginx reload is explicitly needed:

```powershell
docker compose exec nginx nginx -s reload
```

## 6. Smoke Tests

Run after deploy and migration.

### Web Login

Expected:

- Existing web login still works.
- User reaches dashboard.

Manual/browser check:

```text
POST /auth/login
GET /dashboard
```

### Mobile Login Returns Token Pair

Example:

```powershell
curl -i -X POST "https://<host>/api/v1/auth/login" `
  -H "Content-Type: application/json" `
  -d '{"identifier":"<user>","password":"<password>"}'
```

Expected:

- HTTP `200`.
- Response includes `access_token` and `refresh_token`.

### Mobile `/api/v1/auth/me` Works with New Access Token

```powershell
curl -i "https://<host>/api/v1/auth/me" `
  -H "Authorization: Bearer <new_access_token>"
```

Expected:

- HTTP `200`.
- User payload returned.

### Refresh Works with New Refresh Token

```powershell
curl -i -X POST "https://<host>/api/v1/auth/refresh" `
  -H "Content-Type: application/json" `
  -d '{"refresh_token":"<new_refresh_token>"}'
```

Expected:

- HTTP `200`.
- New access/refresh token pair returned.

### Old Mobile Token Without `ver` Returns Controlled 401

Use a pre-deploy mobile token if one is available.

```powershell
curl -i "https://<host>/api/v1/auth/me" `
  -H "Authorization: Bearer <old_access_token_without_ver>"
```

Expected:

- HTTP `401`.
- Response body:

```json
{
  "success": false,
  "code": "unauthorized",
  "message": "Sesi sudah tidak berlaku. Silakan login ulang."
}
```

### Password Change Invalidates Previous Mobile Access/Refresh Tokens

Flow:

1. Mobile login and save access/refresh token pair.
2. Change password through web self-service or approved admin reset flow.
3. Retry old access token on `/api/v1/auth/me`.
4. Retry old refresh token on `/api/v1/auth/refresh`.
5. Login with new password and verify new tokens work.

Expected:

- Old access token returns controlled `401`.
- Old refresh token returns controlled `401`.
- New login works.

### Logout Revocation Still Works

Flow:

1. Mobile login and save access/refresh token pair.
2. Call logout with access token and refresh token.
3. Reuse old access token.

Expected:

- Logout returns `200`.
- Reusing old access token returns `401`.
- No 500 errors.

## 7. Monitoring

Tail web logs during and after deploy:

```powershell
docker compose logs -f --tail=100 web
```

Watch for:

- `500` errors;
- migration errors;
- SQL errors related to `token_version`;
- repeated `unauthorized` responses indicating mobile clients need re-login messaging;
- unexpected failures in `/api/v1/auth/login`, `/api/v1/auth/refresh`, `/api/v1/auth/me`.

Optional log search:

```powershell
docker compose logs --tail=500 web | Select-String -Pattern "500|Traceback|token_version|migration|unauthorized"
```

## 8. Rollback Notes

Preferred rollback approach:

- Code-first rollback if application errors occur.
- Do not immediately drop the DB column.

Reason:

- The added `token_version` column is backward-compatible for old code if old code ignores it.
- Dropping the column after deploy is a schema rollback and requires explicit human approval.

Strict cutover note:

- Old mobile tokens without `ver` are expected to be invalid after deploy.
- This is intended behavior, not a rollback trigger by itself.

Do not run downgrade casually.

Downgrade command, if explicitly approved:

```powershell
docker compose exec web flask db downgrade -1
```

This must only be used after human approval and after confirming app code compatibility.

## 9. Final Decision

**READY FOR HUMAN MIGRATION/DEPLOY APPROVAL if all checks pass**

**NOT APPROVED TO RUN MIGRATION UNTIL HUMAN SAYS YES**

**NOT APPROVED TO DEPLOY UNTIL HUMAN SAYS YES**

