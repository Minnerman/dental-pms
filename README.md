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
   - Backend: http://localhost:8100/health
   - Frontend: http://localhost:3100

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
