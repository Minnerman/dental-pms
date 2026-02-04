# Release Checklist (Stage 59)

Use this checklist before declaring a release-ready checkpoint on `master`.

## Preconditions
- `master` is clean locally (`git status --porcelain` is empty).
- PR checks on `master` are green.
- Backups are operational (Stage 56: `ops/backup_run.sh` + retention).
- UAT rehearsal is green (Stage 58 report: `.run/stage58/UAT_REPORT.md`).

## Pre-release commands
Run from repo root:

```bash
bash ops/env_check.sh
bash ops/health.sh
bash ops/verify.sh
docker compose exec -T backend pytest -q
bash ops/playwright_docker.sh npx playwright test tests/appointments-booking.spec.ts --reporter=line
```

## Backup gate (must pass before release)
```bash
bash ops/backup_run.sh
LATEST_DB="$(ls -1t .run/backups/db/db_*.sql.gz | head -n 1)"
gzip -t "$LATEST_DB"
LATEST_ATT="$(ls -1t .run/backups/attachments_*.tgz | head -n 1)"
tar -tzf "$LATEST_ATT" | head
```

Expected:
- `backup_run_status=ok`
- Latest DB/attachments artefacts exist and are non-empty.
- `gzip -t` succeeds and `tar -tzf` lists entries.

## Rollback reference
- Restore drill reference: Stage 53 entry in `docs/STATUS.md`.
- Backup restore runbook: `docs/OPS_BACKUPS.md` (DB + attachments restore commands).

## RC isolation drill (no compose variant required)
Run an isolated parallel stack by setting a project name and alternate ports:

```bash
export COMPOSE_PROJECT_NAME="dentalpms_rc_test"
export BACKEND_PORT=8110
export FRONTEND_PORT=3110
export POSTGRES_PORT=5443

docker compose up -d --build
docker compose ps
curl -fsS "http://localhost:${BACKEND_PORT}/health"
curl -fsS "http://localhost:${FRONTEND_PORT}/" >/dev/null

docker compose down -v
unset COMPOSE_PROJECT_NAME BACKEND_PORT FRONTEND_PORT POSTGRES_PORT
```

## Post-deploy verify
```bash
bash ops/health.sh
docker compose ps
docker compose logs --tail=200 backend
docker compose logs --tail=200 frontend
docker compose logs --tail=200 db
```

Then run quick user smoke:
- Login works.
- Patients list loads.
- Appointments page loads and can open booking modal.
- Clinical page opens for a known patient.
