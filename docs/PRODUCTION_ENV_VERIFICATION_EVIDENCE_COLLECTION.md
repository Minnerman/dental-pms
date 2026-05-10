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
- Owner/operator supplied non-sensitive evidence provided after the initial
  collection record: production environment label, deployment target status,
  owner/operator roles, backup target schedule/retention, restore target
  classification, and restore status.

## Collected Evidence

| Evidence item | Status | Safe value | Evidence source type | Timestamp | Redaction notes |
| --- | --- | --- | --- | --- | --- |
| Production environment label | Verified | Dental PMS production candidate | Owner/operator supplied evidence | Not applicable | No private host/IP recorded |
| Deployment target label | Blocked | Production server / hosting environment pending verification | Owner/operator supplied evidence | Not applicable | No private host/IP recorded |
| Frontend availability result | Verified by read-only check / pending owner acceptance | HTTP `200`, `time_total=0.008863` for redacted frontend root; owner/operator stated independent availability result is not yet verified | Read-only HTTP GET plus owner/operator supplied status | `2026-05-10T08:32:28Z` | Private URL redacted |
| Backend availability result | Verified by read-only check / pending owner acceptance | HTTP `200`, `time_total=0.001790` for redacted server-local backend health endpoint; owner/operator stated independent availability result is not yet verified | Read-only HTTP GET plus owner/operator supplied status | `2026-05-10T08:32:28Z` | Server-local URL not recorded |
| App health check result | Verified by read-only check / pending owner acceptance | HTTP `200`, `time_total=0.028810` for redacted frontend health proxy; owner/operator stated independent health result is not yet verified | Read-only HTTP GET plus owner/operator supplied status | `2026-05-10T08:32:28Z` | Private URL redacted |
| Backup owner/role | Verified | Project owner / production operator | Owner/operator supplied evidence | Not applicable | Role only, no personal data |
| Backup schedule/frequency | Partially verified | daily target, pending verification | Owner/operator supplied evidence | Not applicable | No private paths recorded |
| Backup retention policy | Partially verified | minimum 30 days target, pending verification | Owner/operator supplied evidence | Not applicable | No backup storage path recorded |
| Latest safe backup timestamp | Blocked | Unavailable | Not safely available from committed non-secret docs/input | Not applicable | Backup storage was not inspected |
| Restore rehearsal target classification | Verified for intended target class | non-live restore test only | Owner/operator supplied evidence | Not applicable | No target details recorded |
| Restore rehearsal status | Blocked | not yet performed | Owner/operator supplied evidence | Not applicable | No restore logs inspected |
| Monitoring/logging owner role | Verified | Project owner / production operator | Owner/operator supplied evidence | Not applicable | Role only, no personal data |
| Support contact role | Verified | Project owner | Owner/operator supplied evidence | Not applicable | Role only, no personal data |

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

- deployment target verification for the production server / hosting
  environment;
- independent owner/operator acceptance of the frontend, backend, and app
  health results if required for go/no-go;
- actual backup schedule/frequency verification beyond the daily target;
- actual backup retention verification beyond the minimum 30 days target;
- latest safe backup timestamp;
- restore rehearsal execution/status, which is currently not performed.

## Next Recommended Action

The availability checks and role-label defaults reduce the production
environment evidence gap, but backup and restore proof remain blocked. The
owner/operator has authorised non-invasive production readiness checks only;
that authorisation does not include database connection, database writes,
live/default PMS DB writes, actual PMS Postgres writes, finance import,
production cutover, R4 access, patient data access, or secret exposure. The
next safe action is to either obtain the remaining non-sensitive
operator-supplied backup/restore evidence, or create a separately scoped
non-invasive backup/restore execution evidence slice with explicit redaction
rules and stop conditions.

This record does not authorise production writes, live/default PMS DB writes,
actual PMS Postgres writes, production execution, live finance import,
invoice/payment/staging import, or cutover.
