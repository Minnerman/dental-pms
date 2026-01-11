# Operations

## Migrations
- Apply latest migrations:
  - `docker compose run --rm backend alembic upgrade head`

## Health checks
- `./ops/health.sh`
- Backend: `http://localhost:8100/health`
- Frontend proxy: `http://localhost:3100/api/health`

## Database access
- Open psql:
  - `docker compose exec db psql -U dental_pms -d dental_pms`
- List tables:
  - `\\dt`

## Attachments
- Stored on the backend container at `/data` (named volume).

## Backups
- See `docs/BACKUP_RESTORE.md` for guidance.
