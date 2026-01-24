# Dental PMS (Practice Build)

Dental Practice Management System (PMS) with a R4-style workflow: patient tabs, day sheet diary, and patient-led booking.

## Safety
This project lives ONLY in `~/dental-pms`. Do not mix it with other server projects.

## Stack
- Frontend: Next.js (TypeScript)
- Backend: FastAPI (Python)
- Database: Postgres
- Orchestration: Docker Compose

## Quick start
From the repo root:

1) Create environment file:
   cp .env.example .env

2) Start:
   docker compose up -d --build

3) Apply migrations:
   docker compose run --rm backend alembic upgrade head

4) Check services:
   - Health: ./ops/health.sh
   - Verify (build + health): ./ops/verify.sh
   - TypeScript typecheck: npm --prefix frontend run typecheck
   - Backend: http://localhost:8100/health
   - Frontend: http://localhost:3100

## R4 imports (safe defaults)
- Without R4 connectivity, use fixtures: `--source fixtures`.
- `--dry-run`/`--apply` are supported only with `--source sqlserver`.
- R4 SQL Server must be reachable from the backend container (host/port routing).
- Use read-only SQL Server credentials only; no writes or stored procs.
- Long imports may exceed shell/CI timeouts; use `r4_import_checkpoint` output plus
  a rerun of `--apply` to confirm completion or resume with `--patients-from`.
- Postgres-only verification is available via `--verify-postgres` for patients windows.

## Charting viewer enablement
- Default is off unless `FEATURE_CHARTING_VIEWER=true` is set.
- Enable: set `FEATURE_CHARTING_VIEWER=true` in `.env` and restart containers.
- Verify: `curl http://localhost:8100/config` and look for `"charting_viewer": true`.
- Disable quickly: remove the env var or set `FEATURE_CHARTING_VIEWER=false` and restart.
- Full runbook: `docs/r4/CHARTING_VIEWER_ENABLEMENT.md`.

Patients-only pilot (Stage 108):
```bash
# Dry-run (read-only, bounded range)
docker compose exec -T backend python -m app.scripts.r4_import \
  --source sqlserver \
  --entity patients \
  --dry-run \
  --limit 25 \
  --patients-from <START_CODE> \
  --patients-to <END_CODE>

# Apply (gated, same range)
docker compose exec -T backend python -m app.scripts.r4_import \
  --source sqlserver \
  --entity patients \
  --apply \
  --confirm APPLY \
  --patients-from <START_CODE> \
  --patients-to <END_CODE>

# Rerun apply to confirm idempotency (expect 0 updates)
docker compose exec -T backend python -m app.scripts.r4_import \
  --source sqlserver \
  --entity patients \
  --apply \
  --confirm APPLY \
  --patients-from <START_CODE> \
  --patients-to <END_CODE>
```

## Where it runs
- http://<server-ip>:3100
- Tailscale: http://<tailscale-ip>:3100

## Ports
- Frontend: 3100
- Backend: 8100
- Postgres: 5442

## Major modules
- Patients, appointments, recalls
- Notes + clinical chart
- Document templates + patient documents + attachments
- Invoices, payments, cash-up

Status details: `docs/STATUS.md`

## Key features
- R4-style patient workspace tabs with persistence
- Patient home summary + booking flow
- Appointments day sheet + calendar toggle (10-minute slots)
- Diary actions: cancel with reason, cut/copy/paste
- Notes and treatments master-detail layout

## Stop
docker compose down

## Operations
- Common fixes: `docs/OPS_CHECKLIST.md#common-fixes`
- Dev commands: `docs/DEV.md`
- GitHub PR workflow (on practice server): use `gh pr create` and `gh pr merge --squash --delete-branch --auto` (origin remote via SSH).

- Access URLs (Tailscale + local): `docs/ACCESS_URLS.md`
- Quick ops checklist: `docs/OPS_CHECKLIST.md`
- Audit trail notes: `docs/AUDIT_TRAIL.md`
- Architecture overview: `docs/ARCHITECTURE.md`
- Operations quick guide: `docs/OPERATIONS.md`
- Migration guide: `docs/SERVER_MIGRATION.md`
- Stop point status: `docs/STATUS.md`

## Auth / RBAC
- MVP auth + roles: `docs/AUTH_RBAC.md`
- Login UI: `/login`
- `/api/me` returns 401/403 when logged out (normal); UI should show signed-out state without a red error toast.

## R4 mapping
- UX mapping: `docs/UX_R4_MAPPING.md`

## Production notes
- Deploy guide: `docs/DEPLOY.md`
- First run: `docs/FIRST_RUN.md`
- Migrations: `docker compose run --rm backend alembic upgrade head`

## Middleware
Invalid numeric IDs (e.g. `/patients/INVALID`) are handled in `frontend/middleware.ts`.
The middleware rewrites such requests to `/__notfound__`, whose page triggers `notFound()`.
This returns a real HTTP 404 while rendering the app router 404 UI (`frontend/app/not-found.tsx`).
