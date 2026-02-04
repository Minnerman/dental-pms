# Operations

## Migrations
- Apply latest migrations:
  - `docker compose run --rm backend alembic upgrade head`

## Default templates
- Recall letter templates are auto-seeded on backend startup if missing.
- Templates remain editable in the Templates page.

## Health checks
- `./ops/health.sh`
- Backend: `http://localhost:8100/health`
- Frontend proxy: `http://localhost:3100/api/health`

## Database access
- Open psql:
  - `docker compose exec db psql -U dental_pms -d dental_pms`
  - Use the DB user from your compose env (`POSTGRES_USER`), not `postgres` if that role doesn't exist.
- List tables:
  - `\\dt`

## Attachments
- Stored on the backend container at `/data` (named volume).

## Backups
- See `docs/OPS_BACKUPS.md` for Stage 56 backup/retention runbook.
- See `docs/BACKUP_RESTORE.md` for legacy backup/restore notes.

## Go-live + monitoring
- UAT checklist: `docs/UAT_CHECKLIST.md`
- Monitoring and first-response triage: `docs/OPS_MONITORING.md`
- Release-ready gate/checklist: `docs/RELEASE_CHECKLIST.md`
