# Production Environment Verification Evidence Collection

Status date: 2026-05-10

Baseline:
`origin/master@fa95879d82844c77eb145d9c933a43f34e8e67a0`

This is a non-invasive production evidence collection record. It uses only
committed repo docs/config metadata and unauthenticated read-only HTTP
availability checks against already documented endpoints. It does not perform
production writes, connect to any PMS database, open or query local scratch
SQLite, access R4, access/hash/inspect real R4 artefacts, use patient data, run
validation/no-write, run guarded apply/write, perform finance import, perform
invoice/payment/staging import, write live/default PMS data, write actual PMS
Postgres data, or perform production cutover.

No secrets, DSNs, tokens, passwords, private URLs, exact private filesystem
paths, raw database dumps, credentials, or patient data are included here.
Private endpoint values found in committed docs are redacted in this record.

R4 remains the live/main PMS. Dental PMS is not live/main PMS.
`finance_import_ready=false`. Live finance import, production execution,
production cutover, live/default PMS DB writes, actual PMS Postgres writes, and
invoice/payment/staging import remain unauthorised.

## Evidence Sources Used

- Repo docs: `README.md`, `docs/ACCESS_URLS.md`,
  `docs/DEPLOY_RUNBOOK.md`, `docs/DEPLOY.md`, `docs/OPERATIONS.md`,
  `docs/OPS_BACKUPS.md`, `docs/OPS_MONITORING.md`,
  `docs/RELEASE_CHECKLIST.md`, and `docs/STATUS.md`.
- Repo code inspection for endpoint safety:
  - `backend/app/main.py` shows `GET /health` returns a static status.
  - `frontend/app/api/health/route.ts` proxies to backend `GET /health`.
- Read-only HTTP checks performed at `2026-05-10T08:32:28Z`.

## Collected Evidence

| Evidence item | Status | Safe value | Evidence source type | Timestamp | Redaction notes |
| --- | --- | --- | --- | --- | --- |
| Production environment label | Partially verified | production candidate on the documented practice-server / single-practice Docker Compose deployment; owner/operator confirmation still required | Repo docs | Not applicable | No private host/IP recorded |
| Deployment target label | Partially verified | Docker Compose deployment target on documented practice-server, with frontend, backend, and Postgres service ports documented; exact production target confirmation still required | Repo docs | Not applicable | No private host/IP recorded |
| Frontend availability result | Verified | HTTP `200`, `time_total=0.008863` for redacted frontend root | Read-only HTTP GET | `2026-05-10T08:32:28Z` | Private URL redacted |
| Backend availability result | Verified | HTTP `200`, `time_total=0.001790` for redacted server-local backend health endpoint | Read-only HTTP GET | `2026-05-10T08:32:28Z` | Server-local URL not recorded |
| App health check result | Verified | HTTP `200`, `time_total=0.028810` for redacted frontend health proxy | Read-only HTTP GET | `2026-05-10T08:32:28Z` | Private URL redacted |
| Backup owner/role | Partially verified | Project owner / production operator | Owner role default, no separate operator documented | Not applicable | Role only, no personal data |
| Backup schedule/frequency | Partially verified | Canonical backup docs include manual backup commands and a systemd timer template; current installed production schedule still needs owner/operator confirmation | Repo docs | Not applicable | No private paths recorded |
| Backup retention policy | Partially verified | Canonical backup docs use `BACKUP_KEEP` with default `14` files per stream; current production override still needs owner/operator confirmation | Repo docs | Not applicable | No backup storage path recorded |
| Latest safe backup timestamp | Blocked | Unavailable | Not safely available from committed non-secret docs/input | Not applicable | Backup storage was not inspected |
| Restore rehearsal target classification | Blocked | Unavailable; later restore target must be non-live/safe | Repo plan gives required classification only | Not applicable | No target details recorded |
| Restore rehearsal status | Blocked | Unavailable | Not safely available from committed non-secret docs/input | Not applicable | No restore logs inspected |
| Monitoring/logging owner role | Partially verified | Project owner / production operator | Owner role default, no separate owner documented | Not applicable | Role only, no personal data |
| Support contact role | Partially verified | Project owner / support operator | Owner role default, no separate role documented | Not applicable | Role only, no personal data |

## Read-Only HTTP Checks

The only availability checks performed were unauthenticated HTTP GET requests
to endpoints already documented in committed repo docs. The record captures
only HTTP status code and total request time.

- Frontend root: pass, HTTP `200`, `time_total=0.008863`.
- Frontend health proxy: pass, HTTP `200`, `time_total=0.028810`.
- Backend static health endpoint: pass, HTTP `200`, `time_total=0.001790`.

No authentication was attempted, no patient routes were called, no request body
was sent, no response body was committed, and no PMS database connection was
made by this slice.

## Remaining Blockers

The following evidence remains blocked or needs owner/operator confirmation:

- owner/operator confirmation of the production environment label;
- owner/operator confirmation of the exact deployment target label;
- current installed backup schedule/frequency, if different from repo docs;
- current backup retention override, if different from repo docs;
- latest safe backup timestamp;
- restore rehearsal target classification;
- restore rehearsal status.

## Next Recommended Action

The availability checks and role-label defaults reduce the production
environment evidence gap, but backup and restore proof remain blocked. The
next safe action is for the owner/operator to supply the remaining
non-sensitive backup/restore evidence, or to authorise a separate
non-invasive backup/restore execution evidence slice with explicit redaction
rules and stop conditions.

This record does not authorise production writes, live/default PMS DB writes,
actual PMS Postgres writes, production execution, live finance import,
invoice/payment/staging import, or cutover.
