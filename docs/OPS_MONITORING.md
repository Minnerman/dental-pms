# Ops Monitoring + Triage (Stage 57)

Use this runbook for first-response triage and basic operational checks.

## Quick triage (first 5 minutes)

```bash
cd ~/dental-pms
docker compose ps
bash ops/health.sh
docker compose logs --tail=200 backend
docker compose logs --tail=200 frontend
docker compose logs --tail=200 db
```

What good looks like:
- `docker compose ps`: all core services (`db`, `backend`, `frontend`) are `Up` and db/backend are healthy.
- `ops/health.sh`: backend `/health` is OK, frontend proxy is OK, auth check passes.
- Logs: no crash loop, no repeated fatal connection errors, no migration failures.

## Disk and backups

```bash
df -h
ls -lah /srv/dental-pms/backups || true
```

What good looks like:
- Sufficient free disk space (especially root/docker volume host filesystem).
- Backup directory exists (if using `/srv/dental-pms/backups`) with recent files:
  - `db/db_YYYY-MM-DD_HHMMSS.sql.gz`
  - `attachments_YYYY-MM-DD_HHMMSS.tgz`

## DB sanity

```bash
docker compose exec -T db sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "select now();"'
```

What good looks like:
- Command returns current timestamp without auth/connection errors.

## Common failure modes

1) Ports already bound
- Symptom: service fails to start with bind/listen errors.
- Check: `docker compose ps`, `docker compose logs --tail=200 <service>`.
- Fix: free conflicting ports or adjust `.env` (`FRONTEND_PORT`, `BACKEND_PORT`, `POSTGRES_PORT`), then recreate.

2) DB unhealthy or migrations pending
- Symptom: backend failing startup, migration/head mismatch errors.
- Check: db logs and migration status commands from `docs/DEPLOY_RUNBOOK.md`.
- Fix: wait for db healthy, then run migrations and restart backend if needed.

3) Missing env keys
- Symptom: startup failures, auth/config errors.
- Check: `bash ops/env_check.sh`.
- Fix: populate required keys in `.env`, then restart affected services.

4) Frontend cannot reach backend base URL
- Symptom: UI loads but API calls fail (proxy/network errors).
- Check: frontend logs, backend health, `NEXT_PUBLIC_API_BASE` config.
- Fix: ensure frontend env/proxy points to backend path and backend is reachable.

## Related runbooks
- `docs/DEPLOY_RUNBOOK.md`
- `docs/OPS_BACKUPS.md`
