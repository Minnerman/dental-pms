# Dental PMS — Status (Stop Point)

## What's working now
- Auth + RBAC with admin-only `/users`
- Patients list/create/edit + notes per patient
- Appointments list + create
- Appointments calendar (day/week/month/agenda with drag-and-drop)
- Appointments day sheet (R4-style list view with cut/copy/paste)
- Audit trail (created_by/updated_by) + audit log endpoints
- Appointment + note audit UI
- Patient timeline + soft-delete (archive/restore) for patients, notes, appointments
- Archived toggles on patients/appointments and restore actions
- Patient alerts/flags + recall controls + recall worklist
- Patient ledger + quick payment/adjustment entry
- Cash-up report (daily totals by payment method)
- Clinical chart (odontogram + tooth history) + treatment plan + clinical notes
- Clinical UX upgrades: quick-add to treatment plan, BPE recording, clinical timeline events
- Patient referrals (source + contact + notes)
- Document templates (prescriptions/letters)
- Patient attachments (uploaded files)
- Patient documents generated from templates (text)
- Template merge fields + preview warnings
- Patient document PDF downloads + attachment save
- Practice profile / letterhead settings for PDFs
- RBAC + audit coverage for templates, patient documents, attachments
- RBAC-aware UI for templates/docs/attachments
- Recalls workflow + recall letters (documents/PDF)
- Recall template pack + defaults for recall letters
- Recall KPI endpoint + recalls dashboard panel
- Financial reporting pack (cash-up, outstanding, trends)
- Monthly export pack (PDF summary + CSV bundle)
- Role management UI polish (roles, resets, disable)
- Theme toggle (light/dark) with neon accents
- Notes and treatments master-detail layout
- Patient sub-pages for clinical/documents/attachments
- Patient navigation polish (tabs + header quick links)
- Clinical chart view mode toggle + tooth badges (planned/history)
- Header nav cleanup (dedupe Home + patient tabs grouped)
- Header nav cleanup: remove patient chips from global header
- Patient booking: restore modal + appointments scroll anchor
- Patient page UX polish (booking scroll + two-column summary layout)

## URLs
- Home: `http://100.100.149.40:3100`
- Login: `http://100.100.149.40:3100/login`
- Patients: `http://100.100.149.40:3100/patients`
- Recalls: `http://100.100.149.40:3100/recalls`
- Patient timeline: `http://100.100.149.40:3100/patients/<id>/timeline`
- Notes: `http://100.100.149.40:3100/notes`
- Appointments audit: `http://100.100.149.40:3100/appointments/<id>/audit`
- Notes audit: `http://100.100.149.40:3100/notes/<id>/audit`

## Credentials
- Admin email/password live in `/home/amir/dental-pms/.env`
- Default is `admin@example.com` / `ChangeMe123!`

## Recent fixes
- 2026-01-16: Stage64 completed (recalls CSV export already in place; added filter-respecting export coverage).
- 2026-01-15: Stage63 completed (Playwright smoke moved to its own workflow).
- 2026-01-15: Stage62 merged (PR #39, master 7dab879). Stage63 planned: move Playwright smoke out of recalls-api-tests.yml into a dedicated workflow (or Nightly smoke).
- 2026-01-15: Stage62 completed (appointments `?book=1` deep link smoke coverage + booking modal guard).
  - Verification: `bash ops/verify.sh`, `./ops/health.sh`, `docker compose exec -T backend pytest -q`.
- 2026-01-15: Stage61 merged (PR #38, master c1b7cd9); CI runs started: 21047920977, 21047920968 (in progress at merge).
  - 2026-01-15: Stage61 completed (recalls last-contact filters + last-contact list coverage tests).
  - Verification: `bash ops/verify.sh`, `./ops/health.sh`, `docker compose exec -T backend pytest -q`.
- 2026-01-15: CI hygiene (Nightly smoke .env generation; Recalls API workflow YAML parse fix; ops/smoke_recalls.sh port/root fix; backend health wait before pytest). Runs: 21047007486, 21047281140.
- 2026-01-13: Session close-out (baseline master d31ba9e; gh PR workflow enabled on practice server; backups in ~/backups/dental-pms/20260113T212657Z; services healthy; lint warnings remain warnings).
- 2026-01-14: Stage60 completed (recalls API pytest suite + CI workflow for recall regressions).
  - Verification: `bash ops/verify.sh`, `./ops/health.sh`, `docker compose exec -T backend sh -lc "python -m alembic upgrade head"`, `ALLOW_DEV_SEED=1 bash ops/seed_recalls_dev.sh`, `docker compose exec -T backend pytest -q`.
- 2026-01-14: Stage58 completed (dev recall seed + smoke scripts; dev seed doc).
  - Verification: `bash ops/verify.sh`, `./ops/health.sh`.
- 2026-01-14: Stage57 completed (export_count cache epoch invalidation on recall writes).
  - Verification: `bash ops/verify.sh`, `./ops/health.sh`, `npm --prefix frontend run typecheck`, `npm --prefix frontend run lint || true`.
- 2026-01-14: Stage56 completed (export_count cache + perf logs; recall comm index migration; timing logs for recalls exports).
  - Verification: `bash ops/verify.sh`, `./ops/health.sh`, `npm --prefix frontend run typecheck`, `npm --prefix frontend run lint || true`.
- 2026-01-14: Stage55 completed (recall export count preview + export page-only toggle; export limit guidance; export count endpoint).
  - Verification: `bash ops/verify.sh`, `./ops/health.sh`, `npm --prefix frontend run typecheck`, `npm --prefix frontend run lint || true`.
- 2026-01-14: Stage54 completed (recall exports honor full filters; export guardrail; ZIP empty-result message; export UX hints).
  - Verification: `bash ops/verify.sh`, `./ops/health.sh`, `npm --prefix frontend run typecheck`, `npm --prefix frontend run lint || true`.
- 2026-01-14: Stage53 completed (migration status/upgrade ops scripts; recalls error banner clarifies backend issue; alembic_version guard documented).
  - Verification: `bash ops/verify.sh`, `./ops/health.sh`, `npm --prefix frontend run typecheck`, `npm --prefix frontend run lint || true`.
- Alembic guard: `backend/alembic/env.py` widens `alembic_version.version_num` to prevent long revision IDs from blocking upgrades on fresh/older DBs.
- 2026-01-14: Stage52 completed (recalls popover for last-contact details; canonical other detail field + backfill; pagination resets on filter changes; alembic preflight widens version_num).
  - Verification: `bash ops/verify.sh`, `./ops/health.sh`, `npm --prefix frontend run typecheck`, `npm --prefix frontend run lint || true`.
- 2026-01-14: Stage51 completed (recalls dashboard shows other detail/outcome; empty-state with clear filters; last-contact metadata added to dashboard API).
  - Verification: `bash ops/verify.sh`, `./ops/health.sh`, `npm --prefix frontend run typecheck`, `npm --prefix frontend run lint || true`.
  - Tests: none (no API test harness; backend/tests only has placeholder).
- 2026-01-14: Stage50 completed (recall contact logging endpoint + dashboard log contact modal; last-contact filters by state/time/method; "other" method supported; migration 0027_recall_contact_events.py).
  - Verification: `bash ops/verify.sh`, `./ops/health.sh`, `npm --prefix frontend run typecheck`, `npm --prefix frontend run lint || true`.
- 2026-01-14: Stage48 completed (/recalls pagination controls with per-page + prev/next; filter changes reset offset; export.csv + letters.zip share params and honor pagination).
- 2026-01-14: Stage49 completed (dev workflow hardening: ops/typecheck.sh; verify runs typecheck; README updated with root typecheck command).
  - Verification: `bash ops/verify.sh`, `./ops/health.sh`, `npm --prefix frontend run typecheck`, `npm --prefix frontend run lint || true`.
- 2026-01-14: Stage47 completed (recall last contact fields and filters).
- 2026-01-14: Stage46 completed (migration 0026_patient_recall_communications.py; endpoints GET/POST /patients/{id}/recalls/{recallId}/communications; silent auto-log on letter.pdf + letters.zip with 60s guard).
- 2026-01-14: Stage45 completed (GET /recalls/letters.zip; same params as /recalls; zip filename recall-letters-YYYY-MM-DD.zip; PDFs named RecallLetter_<Surname>_<Forename>_<patientId>_<dueDate>.pdf or RecallLetter_patient-<id>_<dueDate>.pdf).
- 2026-01-14: Stage44 completed (/recalls Export CSV + Print view; GET /recalls/export.csv (same params as /recalls), filename recalls-YYYY-MM-DD.csv).
- 2026-01-14: Stage43 completed (GET /patients/{patient_id}/recalls/{recall_id}/letter.pdf; generate letter buttons on /recalls and patient recalls tab).
- 2026-01-14: Stage42 completed (/appointments prompt to mark recall completed when recallId present; PATCH recalls accepts outcome + linked_appointment_id (migration 0025); patient recalls tab shows outcome + quick next recall +6m/+12m).
- 2026-01-14: Stage41 completed (/recalls book appointment button; /appointments prefill via ?book=1&patientId=&reason=).
- 2026-01-14: Stage40 completed (/recalls dashboard with filters + complete/snooze actions + mobile cards; GET /recalls query + shared status helper in backend/app/services/recalls.py).
- 2026-01-14: Stage39 completed (patient recalls model + migration 0024_patient_recalls.py; endpoints GET/POST/PATCH /patients/{id}/recalls; patient Recalls tab with add/edit/complete + mobile cards).
- 2026-01-14: Stage38 patient finance summary panel (balance + recent invoices/payments + PDF downloads).
- 2026-01-13: PR #12 merged (ESLint config + lint fixes); lint runs with warnings only; typecheck passes; master f300dcd.
- Patient summary: in-page booking jump + collapsible docs/attachments + tighter two-column layout.
- Summary grid breakpoint/spacing updated (class currently only used on patient summary).
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
- Session handoff: master a70a77f, services running, exhaustive-deps lint warnings tracked (non-blocking).
- Password reset rate limiting + audit logging (no token leakage)
- Guarded route params/search params for strictNullChecks
- Reset-password page moved to Suspense wrapper; Next build completes with BUILD_ID
- Required [id] routes now enforce notFound() via server wrappers and client components
- App layout refactored to server wrapper + client shell
- Middleware added to return 404 for invalid numeric IDs
- Middleware now rewrites invalid ID routes to /__notfound__ for standard 404 UI + 404 status
- Document templates list 500 resolved (audit actor email validation relaxed)
- Ops verify script added (./ops/verify.sh) for build + health checks
- Patient subpages: clearer empty states and not-found redirect for missing patients
- Book appointment action now waits for the booking panel before scrolling
- Manual smoke checklist added for patient flows (docs/SMOKE_TESTS.md)
- Server guard added to return HTTP 404 for non-existent patients in production
- Prod middleware now checks patient existence when auth cookie present to return true 404
- 2026-01-11: Stage29 on master (3af2950) verified: booking widget scroll + templates load
- 2026-01-12: Stage30 merged + deployed (ops verify scripts, prod 404 guard, patient UX hardening).
- 2026-01-12: Verified after deploy: `docker compose build`, `docker compose up -d`, `bash ops/verify.sh`, `bash ops/verify_prod_404.sh`, `./ops/health.sh`.
- 2026-01-12: Stage31 merged + deployed (appointments deep link booking, refresh-after-create, routing from patients).
- 2026-01-12: Verified after deploy: `docker compose build`, `docker compose up -d`, `bash ops/verify.sh`, `bash ops/verify_prod_404.sh`, `./ops/health.sh`.
- 2026-01-12: Stage31 post-merge redeploy verification: `docker compose build`, `docker compose up -d`, `bash ops/verify.sh`, `bash ops/verify_prod_404.sh`, `./ops/health.sh`.
- 2026-01-12: Stage32 merged + deployed (appointments deep link start/duration prefill).
- 2026-01-12: Verified after deploy: `docker compose build`, `docker compose up -d`, `bash ops/verify.sh`, `bash ops/verify_prod_404.sh`, `./ops/health.sh`.
- 2026-01-12: Stage33 merged + deployed (appointments date/view/clinician deep links).
- 2026-01-12: Verified after deploy: `docker compose build`, `docker compose up -d`, `bash ops/verify.sh`, `bash ops/verify_prod_404.sh`, `./ops/health.sh`.
- 2026-01-13: Stage34 merged + deployed (appointments conflict warning).
- 2026-01-13: Verified after deploy: `docker compose build`, `docker compose up -d`, `bash ops/verify.sh`, `bash ops/verify_prod_404.sh`, `./ops/health.sh`.
- 2026-01-13: Stage35 merged + deployed (conflict warning view link).
- 2026-01-13: Verified after deploy: `docker compose build`, `docker compose up -d`, `bash ops/verify.sh`, `bash ops/verify_prod_404.sh`, `./ops/health.sh`.
- 2026-01-13: Stage36 merged + deployed (booking duration selector).
- 2026-01-13: Verified after deploy: `docker compose build`, `docker compose up -d`, `bash ops/verify.sh`, `bash ops/verify_prod_404.sh`, `./ops/health.sh`.
- 2026-01-13: Stage37 merged + deployed (date deep link respects day-sheet mode).
- 2026-01-13: Verified after deploy: `docker compose build`, `docker compose up -d`, `bash ops/verify.sh`, `bash ops/verify_prod_404.sh`, `./ops/health.sh`.
- 2026-01-14: Stage38 completed (patient finance summary panel on patient home; adds GET /patients/{id}/finance-summary; next-env.d.ts hygiene update).
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
- 2026-01-08: Clinical chart module (odontogram, tooth history, treatment plan, clinical notes)

## Known issues
- None known.

## PR draft (stage30-hardening-and-polish -> master)
- Summary:
  - Ops verify scripts (dev build/health + prod 404 check)
  - Production 404 for missing patient IDs
  - Patient UX hardening (empty states, booking action reliability)
  - Docs updates (smoke checklist + notes)
- Verification: `bash ops/verify.sh`, `bash ops/verify_prod_404.sh`, `./ops/health.sh`.
- Risks/notes: prod 404 relies on auth cookie; dev still UI-driven for missing patients.

## PR draft (stage31-appointments-workflow -> master)
### Stage31 appointments workflow
- Summary:
  - Deep link booking: `/appointments?book=1` (+ optional `patientId`)
  - Calendar updates immediately after create + canonical refetch
  - Improved validation + friendly errors
  - Patient “Book appointment” routes to appointments deep link
  - Smoke tests updated
- Verification: `bash ops/verify.sh`, `bash ops/verify_prod_404.sh`, `./ops/health.sh`.
- Manual checks:
  - `/appointments?book=1` opens booking once and cleans URL
  - `/appointments?book=1&patientId=5` preselects patient
  - Create appointment appears immediately; persists after refresh
  - Missing patient/invalid time shows friendly error
  - Patient page Book appointment routes and back button works
- Risks/notes:
  - Deep link relies on appointments page patient list being loaded

## PR draft (stage32-appointments-start-prefill -> master)
- Summary:
  - Deep link booking now supports `start=` prefill (local or ISO with timezone)
  - Optional `duration=` prefills the end time when `start` is valid
  - Smoke tests updated for deep link start/duration scenarios
- Verification: `bash ops/verify.sh`, `bash ops/verify_prod_404.sh`, `./ops/health.sh`.
- Manual checks:
  - `/appointments?book=1&start=2026-01-14T13:30` prefills start time
  - `/appointments?book=1&patientId=5&start=2026-01-14T13:30` prefills both
  - `/appointments?book=1&start=2026-01-14T13:30:00Z` converts to local time
  - Invalid `start` is ignored safely
  - Optional `duration=30` prefills the end time when `start` is valid
- Risks/notes:
  - End time prefill uses `duration` only for the booking form; it does not enforce scheduling rules.

## PR draft (stage33-appointments-date-deeplink -> master)
- Summary:
  - `/appointments?date=YYYY-MM-DD` jumps the calendar to a target date
  - Optional `view=day|week|month` sets calendar view when provided
  - Optional `clinicianId=` preselects clinician in booking flow
  - Smoke tests updated for appointment deep links
- Verification: `bash ops/verify.sh`, `bash ops/verify_prod_404.sh`, `./ops/health.sh`.
- Manual checks:
  - `/appointments?date=2026-01-14` jumps calendar to date
  - `/appointments?date=2026-01-14&view=week` preserves week view
  - `/appointments?date=2026-01-14&book=1` still opens booking
  - `/appointments?book=1&clinicianId=2` preselects clinician
- Risks/notes:
  - Date deep link does not remove `date` or `view` params after navigation.

## PR draft (stage34-appointments-conflict-warning -> master)
- Summary:
  - Non-blocking warning for overlapping appointments for the same clinician
  - Warning shown on create and reschedule/resize
  - Smoke checklist updated with conflict cases
- Verification: `bash ops/verify.sh`, `bash ops/verify_prod_404.sh`, `./ops/health.sh`.
- Manual checks:
  - Overlapping same clinician shows warning (still saves)
  - Overlapping different clinician shows no warning
  - Boundary case end==start shows no warning
- Risks/notes:
  - Conflict detection is front-end only and limited to loaded range.

## PR draft (stage35-conflict-warning-viewlink -> master)
- Summary:
  - Conflict warning includes “View conflicts” action to jump calendar to conflict time
  - Warning notes conflicts are limited to loaded range
  - Smoke checklist updated for view conflicts action
- Verification: `bash ops/verify.sh`, `bash ops/verify_prod_404.sh`, `./ops/health.sh`.
- Manual checks:
  - Conflict warning “View conflicts” jumps calendar to conflict time
  - Warning remains non-blocking
- Risks/notes:
  - View conflicts switches to calendar day view to show the conflict context.

## PR draft (stage36-booking-duration-selector -> master)
- Summary:
  - Booking form includes duration selector with common minute values
  - End time auto-adjusts when duration or start changes
  - Smoke checklist updated for duration selector
- Verification: `bash ops/verify.sh`, `bash ops/verify_prod_404.sh`, `./ops/health.sh`.
- Manual checks:
  - Selecting duration updates end time
  - Editing end time updates duration to match or falls back to Custom
- Risks/notes:
  - Duration auto-sync applies only when a preset duration is selected.

## PR draft (stage37-date-deeplink-respect-daysheet -> master)
- Summary:
  - `?date=` deep link respects day-sheet mode without switching views
  - `view=` only affects calendar mode
  - Smoke checklist updated for day-sheet deep link behavior
- Verification: `bash ops/verify.sh`, `bash ops/verify_prod_404.sh`, `./ops/health.sh`.
- Manual checks:
  - Day-sheet mode stays active with `/appointments?date=2026-01-14`
  - `/appointments?date=2026-01-14&view=week` honors view only in calendar mode
  - `/appointments?date=2026-01-14&book=1` opens booking without mode change
- Risks/notes:
  - Deep link view changes are ignored when in day-sheet mode.

## RBAC matrix
- Templates: list/read/download (all), create/update/delete (superadmin)
- Patient documents: list/read/download (all), create (all), delete (superadmin)
- Attachments: list/download/upload (all), delete (superadmin)

## CI hygiene
- Nightly smoke (run 21019750369) failed during `docker compose up -d --build` because `.env` was missing and required vars were unset (POSTGRES_*, BACKEND_PORT/FRONTEND_PORT, SECRET/JWT, ADMIN_*). Error: `env file .../.env not found` with multiple "variable is not set" warnings.
- Workflow validation failure (run 21016501636) is a 0s failure on `.github/workflows/recalls-api-tests.yml` (no logs). Likely workflow-file validation issue; latest master CI run is green.

## Next up
- Stage 23 follow-up:
  - Clinical reporting polish

## Stage 66
- Completed (PR #43, master 1b4de3d): clinical tab last-updated + refresh, error retry, standardized timestamps, newest-first ordering for notes/procedures, and clearer empty-state copy.

## Stage 67
- Completed (PR #44, master 6b008a8): appointments range end is exclusive (frontend sends day-after end), stale range fetches are ignored, and backend range boundary tests cover late-day inclusion + end-day exclusion.
- Verification: `bash ops/verify.sh`, `./ops/health.sh`, `docker compose exec -T backend pytest -q`.

## Stage 68
- Completed (PR #45, master c004aa6): recall export audit logging for CSV+letters ZIP, Content-Disposition filenames include filters/page-only, and frontend respects export filenames.
- Verification: `bash ops/verify.sh`, `./ops/health.sh`, `docker compose exec -T backend pytest -q`.

## Stage 65
- Completed (PR #42, master 67975f2): booking modal deep-link stability tests (refresh/back/forward/view+location), added booking modal field testids for Playwright selectors, CI hardening retries for docker pulls/builds (recalls-api, CI docker-build, Playwright smoke).

## Roadmap (stages)
- Stage 47: recall dashboard last contact and contact filters (completed)
- Stage 48: recall dashboard pagination controls (completed)
- Stage 49: developer workflow hardening (typecheck entrypoint + verify guidance)
- Stage 50+: TBD

## Stage 31 backlog
- Appointments: booking modal reliability across refresh/tab changes.
- Appointments: calendar interactions and range loading edge cases.
- Appointments: confirm creation flow when switching clinicians/locations.

## Role management access
- Superadmin: change roles, enable/disable users, grant/revoke superadmin.
- Admin: create users, reset passwords.

## Monthly pack definitions
- PDF summary includes cash-up totals, method totals, and outstanding snapshot as of month end.
- ZIP bundle includes `cashup_daily.csv`, `cashup_by_method.csv`, and `top_debtors.csv`.

## Financial reporting definitions
- Cash-up summary uses ledger payment entries within the selected date range (totals by day and method).
- Outstanding balances sum ledger entries up to the selected `as_of` date; top debtors are the highest positive balances.
- Trends are daily sums from ledger entries: payments (absolute), charges (charges + adjustments), net (sum of all).

## Recall KPI definitions
- Due/overdue/booked/declined are counted by current status filtered to recall due dates within the KPI date range.
- Overdue is a due recall with due date before today.
- Contacted uses `recall_last_contacted_at` within the KPI date range.
- Contacted rate = contacted / (due + overdue).
- Booked rate = booked / (contacted + booked).

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
- 2026-01-07 Appointments calendar switched to react-big-calendar (range API `/api/appointments/range`, schedule `/api/settings/schedule`)
- 2026-01-07 Patient workspace tabs + patient home booking panel wired to appointments day view
- 2026-01-07 Appointment cancellation reasons + diary cut/copy/paste context menu (frontend+backend)
- 2026-01-07 Day sheet view toggle and patient list refresh (R4 workflow)
- 2026-01-07 Notes edit endpoint + master-detail lists for notes/treatments
- 2026-01-07 Patient recall fields + alert flags + recalls worklist UI
- 2026-01-07 Patient ledger entries + quick payments + ledger tab
- 2026-01-07 Cash-up report + ledger backfill script
