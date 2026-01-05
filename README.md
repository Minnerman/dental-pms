# Dental PMS (Practice Build)

This repository is the starter skeleton for a Dental Practice Management System.

## Safety
This project lives ONLY in `~/dental-pms`. Do not mix it with other server projects.

## Stack (dev)
- Frontend: Next.js (TypeScript)
- Backend: FastAPI (Python)
- Database: Postgres
- Orchestration: Docker Compose

## Quick start
From the repo root:

1) Create environment file:
   cp .env.example .env

2) Start:
   docker compose up -d

3) Check services:
- Health: ./ops/health.sh
- Backend: http://localhost:8000/health
- Frontend: http://localhost:3000

## Where it runs
- http://<server-ip>:3100
- Tailscale: http://<tailscale-ip>:3100

## Stop
docker compose down

## Operations
- Common fixes: `docs/OPS_CHECKLIST.md#common-fixes`

- Access URLs (Tailscale + local): `docs/ACCESS_URLS.md`
- Quick ops checklist: `docs/OPS_CHECKLIST.md`
- Audit trail notes: `docs/AUDIT_TRAIL.md`
- Migration guide: `docs/SERVER_MIGRATION.md`
- Stop point status: `docs/STATUS.md`

## Auth / RBAC
- MVP auth + roles: `docs/AUTH_RBAC.md`
- Login UI: `/login`
- `/api/me` returns 401/403 when logged out (normal); UI should show signed-out state without a red error toast.

## Production notes
- Deploy guide: `docs/DEPLOY.md`
- First run: `docs/FIRST_RUN.md`

## Middleware
Invalid numeric IDs (e.g. `/patients/INVALID`) are handled in `frontend/middleware.ts`.
The middleware rewrites such requests to `/__notfound__`, whose page triggers `notFound()`.
This returns a real HTTP 404 while rendering the app router 404 UI (`frontend/app/not-found.tsx`).
