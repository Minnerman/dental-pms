# Deploy Runbook (Stage 52)

## Purpose + scope
This runbook defines the production-ish deployment path for a single-practice Dental PMS install using Docker Compose.

## Prerequisites
- Ubuntu/Linux host with Docker Engine + Docker Compose plugin installed.
- Git access to this repository.
- Required host ports available: `3100` (frontend), `8100` (backend), `5442` (Postgres), unless overridden in `.env`.
- A local `.env` file in repo root (never commit secrets).

## First-time setup
```bash
git clone git@github.com:Minnerman/dental-pms.git
cd dental-pms
cp .env.example .env
```

Set required values in `.env`:
- `SECRET_KEY` (>=32 chars)
- `JWT_SECRET` (>=32 chars)
- `ADMIN_EMAIL`
- `ADMIN_PASSWORD` (>=12 chars)

Validate env before starting:
```bash
bash ops/env_check.sh
```

## Start / stop / status
Start (build + run):
```bash
docker compose up -d --build
```

Stop:
```bash
docker compose down
```

Status + health:
```bash
docker compose ps
bash ops/health.sh
```

## Migrations
Apply migrations:
```bash
docker compose run --rm backend sh -lc 'python -m alembic upgrade head'
```

Check migration state:
```bash
docker compose run --rm backend sh -lc 'python -m alembic current'
docker compose run --rm backend sh -lc 'python -m alembic heads'
```

## Logs + troubleshooting
```bash
docker compose logs -f --tail=200 backend
docker compose logs -f --tail=200 frontend
docker compose logs -f --tail=200 db
```

Common failure classes:
- Missing env: run `bash ops/env_check.sh` and fix reported keys.
- Port conflicts: check bindings and adjust `BACKEND_PORT`/`FRONTEND_PORT`/`POSTGRES_PORT` in `.env`.
- DB startup timing: check `docker compose logs db` and rerun migrations after DB is healthy.

## Backups (Stage 53 drill target)
Data locations:
- Postgres volume: `dental_pms_db_data`
- Attachments/uploads volume: `dental_pms_attachments`

Existing helper scripts:
- `ops/backup_db_volume.sh`
- `ops/restore_db_volume.sh`
- `ops/db_backup.sh`
- `ops/db_restore.sh`

Stage 53 will run and document a full backup/restore drill.

## Rollback
Application rollback:
```bash
git checkout <previous-known-good-sha>
docker compose up -d --build
bash ops/health.sh
```

Notes:
- Keep previous known-good SHAs in release notes/PRs.
- DB migration rollback is not assumed automatic; if a release includes irreversible migrations, use restore procedure from backups.

## R4 SQL Server policy
- Policy is strict SELECT-only.
- Always enforce `R4_SQLSERVER_READONLY=true` for SQL Server sourced runs.
- SQL Server credentials are env-only and must not be committed.
- CI/test workflows should not depend on live R4 SQL Server credentials.
