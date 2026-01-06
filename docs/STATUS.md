# Dental PMS — Status (Stop Point)

## What's working now
- Auth + RBAC with admin-only `/users`
- Patients list/create/edit + notes per patient
- Appointments list + create
- Audit trail (created_by/updated_by) + audit log endpoints
- Appointment + note audit UI
- Patient timeline + soft-delete (archive/restore) for patients, notes, appointments
- Archived toggles on patients/appointments and restore actions
- Theme toggle (light/dark) with neon accents

## URLs
- Home: `http://100.100.149.40:3100`
- Login: `http://100.100.149.40:3100/login`
- Patients: `http://100.100.149.40:3100/patients`
- Patient timeline: `http://100.100.149.40:3100/patients/<id>/timeline`
- Notes: `http://100.100.149.40:3100/notes`
- Appointments audit: `http://100.100.149.40:3100/appointments/<id>/audit`
- Notes audit: `http://100.100.149.40:3100/notes/<id>/audit`

## Credentials
- Admin email/password live in `/home/amir/dental-pms/.env`
- Default is `admin@example.com` / `ChangeMe123!`

## Recent fixes
- Bcrypt/passlib pin
- Session check 500 resolved by enum schema fix
- Route groups + theme toggle
- Import alias `@/lib/auth` to fix Next module resolution
- Dark mode contrast polish (inputs, tabs, notices)
- Password reset flow (request + confirm endpoints + UI)
- Patient search filters for DOB + email
- Docker compose env wiring for reset-token settings
- Password reset validated end-to-end (debug mode used briefly, now disabled)
- Health check confirmed OK (`./ops/health.sh`)
- Frontend deterministic installs via package-lock + npm ci
- Password reset rate limiting + audit logging (no token leakage)
- Guarded route params/search params for strictNullChecks
- Reset-password page moved to Suspense wrapper; Next build completes with BUILD_ID
- Required [id] routes now enforce notFound() via server wrappers and client components
- App layout refactored to server wrapper + client shell
- Middleware added to return 404 for invalid numeric IDs
- Middleware now rewrites invalid ID routes to /__notfound__ for standard 404 UI + 404 status
- See README.md (Middleware section) for details on invalid numeric ID handling via middleware rewrite to /__notfound__ and HTTP 404 behaviour.
- Attribution columns added to patients/appointments lists; notes formatting aligned
- Admin reset-password flow + must-change-password support (backend + frontend)
- Alembic migrations added; forward-fill removed; baseline stamped and upgrade applied
- 2026-01-05: Frontend service restarted; port 3100 responding again
- 2026-01-05: Treat /api/me 401/403 as signed-out state to avoid error toast
- 2026-01-05: Repo initialized + compose restart policy and README updates (commits 69579f6, 153cbb1)
- 2026-01-06: Invoices + payments MVP (patient tab), INV-000001 numbering via id
- 2026-01-06: Invoice + receipt PDFs (ReportLab) with download buttons
- 2026-01-06: Updated invoice/receipt PDF headers to Clinic for Implant & Orthodontic Dentistry; 7 Chapel Road, Worthing, West Sussex BN11 1EG; Tel: 01903 821822; dental-worthing.co.uk
- 2026-01-06: Added admin reset script, removed login debug banner, and documented env recreation guidance

## Known issues
- None known.

## Next up
- Document templates (prescriptions/letters) OR global invoices list page + basic cash-up summary

## Verification
- 404 enforcement (auth): backend login returns bearer token (no cookie set); invalid routes render Next 404 UI but HTTP status is 200 in dev
- curl results (auth header, frontend dev server):
  - /appointments/INVALID/audit -> 200
  - /notes/INVALID/audit -> 200
  - /patients/INVALID -> 200
  - /patients/INVALID/audit -> 200
  - /patients/INVALID/timeline -> 200
- Production `next start` (frontend-prod container, port 3100) with middleware returns 404 for invalid routes:
  - /appointments/INVALID/audit -> 404
  - /notes/INVALID/audit -> 404
  - /patients/INVALID -> 404
  - /patients/INVALID/audit -> 404
  - /patients/INVALID/timeline -> 404
- Response headers show `HTTP/1.1 404 Not Found` and `x-middleware-rewrite: /__notfound__`; body includes custom 404 UI
- Alembic: `docker compose run --rm backend alembic stamp 0001_initial` + `docker compose run --rm backend alembic upgrade head` (OK)
- Build: `docker compose run --rm --no-deps frontend sh -lc 'set -eux; rm -rf .next; NODE_ENV=production npm run build'` (OK)
- Health: `./ops/health.sh` (OK)

## Version pins
- postgres:16
- python:3.12-slim
- node:18-slim
- bcrypt==3.2.2

- 2026-01-06 Added appointments day view + domiciliary patient fields + appointment↔estimate linkages (health OK)

- 2026-01-06 Added appointments week view + range API + domiciliary run sheet PDF
