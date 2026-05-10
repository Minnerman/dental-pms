# Dental PMS Production Readiness Execution Tracker

Status date: 2026-05-10

Baseline:
`origin/master@719c5c8290950cc673d19e20528f5e3f6b2b293a`

This is a docs-only production readiness execution tracker and gap
assessment. It does not perform production execution, live import, production
cutover, R4 access, real artefact access, patient-data review, PMS database
connection, validation/no-write, guarded apply/write, finance import, or
invoice/payment/staging import.

R4 remains the live/main PMS. Dental PMS is not live/main PMS.
`finance_import_ready=false`.

The R4 opening-balance full eligible-row non-live evidence track is complete
through signed-off guarded apply/write proof, and the independent
business/accounting reconciliation sign-off is recorded. This tracker does not
authorise any live/default PMS DB write, actual PMS Postgres write, production
execution, live finance import, invoice/payment/staging import, or Dental PMS
becoming the live/main PMS.

Production-environment, backup, and restore verification planning is recorded
in `docs/PRODUCTION_ENV_BACKUP_RESTORE_VERIFICATION_PLAN.md`. That plan does
not execute verification, connect to production, connect to any PMS database,
or claim production readiness.

The non-sensitive evidence request and execution checklist is recorded in
`docs/PRODUCTION_ENV_VERIFICATION_EVIDENCE_REQUEST.md`. That request does not
run verification, connect to production, expose secrets, or authorise live
writes.

The current production environment evidence record is
`docs/PRODUCTION_ENV_VERIFICATION_EVIDENCE_RECORD.md`. It records that
non-sensitive production environment, backup, and restore evidence is not yet
available and lists the exact missing items.

The follow-up non-invasive production evidence collection record is
`docs/PRODUCTION_ENV_VERIFICATION_EVIDENCE_COLLECTION.md`. It partially
verifies the documented production candidate/deployment labels, verifies
unauthenticated read-only frontend/backend/app health availability, records
role-label defaults, and keeps backup timestamp plus restore proof evidence
blocked.

No patient-level contents, raw artefact contents, exact artefact paths, DSNs,
production passwords, live credentials, or secrets belong in this tracker.

## Workstream Tracker

| Workstream | Owner | Status | Blocker | Target Evidence | Go/No-Go Impact |
| --- | --- | --- | --- | --- | --- |
| Business reconciliation closure | Owner/business | Complete | None for non-live evidence closure | Business reconciliation sign-off record | Required input is complete for readiness planning; does not authorise live import or cutover |
| Production environment readiness | Ops owner | Partially verified / pending owner-operator confirmation | Read-only frontend, backend, and app health checks passed; production candidate/deployment labels still require owner/operator confirmation | `docs/PRODUCTION_ENV_VERIFICATION_EVIDENCE_COLLECTION.md`, then owner/operator target confirmation | No-go until accepted |
| Backup readiness | Ops owner | Partially verified / blocked on backup evidence | Owner role default, repo backup schedule template, and default retention policy are recorded; latest safe backup timestamp and current production schedule/retention confirmation are unavailable | `docs/PRODUCTION_ENV_VERIFICATION_EVIDENCE_COLLECTION.md`, then latest safe backup timestamp and backup integrity evidence | No-go until accepted |
| Restore proof | Ops owner | Blocked / pending evidence | Restore rehearsal target classification and restore rehearsal status are unavailable | `docs/PRODUCTION_ENV_VERIFICATION_EVIDENCE_COLLECTION.md`, then non-live restore target classification and restore rehearsal status/evidence | No-go until accepted |
| Rollback plan | Owner plus ops owner | Pending evidence | Rollback owner, triggers, and communication path not accepted | Written rollback plan with triggers, decision owner, and operator notices | No-go until accepted |
| User/access readiness | Practice owner | Pending evidence | User roles and access review not recorded | Role/access review for admin, reception, clinical, finance, and support users | No-go for live use until accepted |
| Smoke/regression testing | Technical owner | Pending evidence | Production-readiness smoke/regression pass not recorded | Smoke/regression checklist with pass/fail thresholds | No-go until accepted or explicitly waived |
| UAT/practice workflow testing | Practice owner | Not started | UAT checklist and acceptance not recorded | Practice workflow checklist covering reception, clinical, documents, recalls, and finance views | No-go until accepted or explicitly waived |
| Data migration scope | Owner plus migration owner | Pending evidence | Included/excluded production data scope not finalised | Signed included/excluded data scope record | No-go until accepted |
| Opening-balance live-import decision | Owner | Blocked by owner decision | Live finance import remains unauthorised | Separate explicit owner approval for any live opening-balance import | No-go for finance import until approval |
| Patient data migration decision | Owner plus migration owner | Pending evidence | Patient import/cutover scope not finalised | Patient data inclusion/exclusion and duplicate/contact policy | No-go until accepted |
| Appointments/treatments/recalls migration decision | Owner plus migration owner | Pending evidence | Domain scope and accepted exclusions not finalised | Decision record for appointments, treatments, charting, and recalls | No-go until accepted |
| Monitoring/support readiness | Support owner | Pending evidence | Monitoring owner and support window not recorded | Monitoring checklist, support owner, escalation route, and first support window | No-go until accepted |
| Cutover communications | Owner plus support owner | Not started | Operator communication plan not recorded | Cutover communication plan for owner, operators, and support contacts | No-go until accepted |
| Final go/no-go approval | Owner | Blocked by owner decision | No production rehearsal, backup/restore proof, or final cutover approval recorded | Explicit go/no-go decision record | No-go until explicit approval |

## Immediate Fast-Track Actions

These actions are planning or inspection tasks only. They must not write live
data or start cutover.

1. Verify production environment health without writing data.
2. Resolve the blocked evidence in
   `docs/PRODUCTION_ENV_VERIFICATION_EVIDENCE_RECORD.md` by having the
   owner/operator supply non-sensitive evidence or by approving a separate
   non-invasive verification execution slice.
3. Define the UAT checklist for reception, clinical, document, recall, and
   finance-view workflows.
4. Define the exact data migration scope, including included and excluded
   domains.
5. Prepare a production rehearsal plan with target, scope, evidence, and
   rollback handling for separate approval.
6. Keep live import blocked until final go/no-go approval explicitly authorises
   it.

## Production Evidence Item Status

| Evidence item | Current status | Current value/evidence | Remaining gap |
| --- | --- | --- | --- |
| Production environment label | Partially verified | Documented production candidate on practice-server / single-practice Docker Compose deployment | Owner/operator confirmation required |
| Deployment target label | Partially verified | Documented Docker Compose deployment target and service ports | Owner/operator confirmation required |
| Frontend availability result | Verified | Read-only HTTP GET returned `200` at `2026-05-10T08:32:28Z` | Owner acceptance |
| Backend availability result | Verified | Read-only HTTP GET returned `200` at `2026-05-10T08:32:28Z` | Owner acceptance |
| App health check result | Verified | Read-only HTTP GET returned `200` at `2026-05-10T08:32:28Z` | Owner acceptance |
| Backup owner/role | Partially verified | Project owner / production operator role default | Owner/operator confirmation |
| Backup schedule/frequency | Partially verified | Repo docs define manual backup commands and systemd timer template | Current installed production schedule/frequency confirmation |
| Backup retention policy | Partially verified | Repo docs define `BACKUP_KEEP` default `14` files per stream | Current production override confirmation |
| Latest safe backup timestamp | Blocked | Unavailable | Owner/operator evidence or approved backup verification slice |
| Restore rehearsal target classification | Blocked | Unavailable | Owner/operator evidence or approved restore planning/execution slice |
| Restore rehearsal status | Blocked | Unavailable | Owner/operator evidence or approved restore proof slice |
| Monitoring/logging owner role | Partially verified | Project owner / production operator role default | Owner/operator confirmation |
| Support contact role | Partially verified | Project owner / support operator role default | Owner/operator confirmation |

## Explicit Blockers

- No production rehearsal has been completed.
- No backup/restore proof has been recorded.
- No final live import approval has been given.
- No cutover go/no-go approval has been given.
- R4 is still the live/main PMS.

## Still Unauthorised

The following remain unauthorised and require separate explicit owner approval:

- live/default PMS DB writes;
- actual PMS Postgres writes;
- production execution;
- production cutover;
- live finance import;
- invoice/payment/staging import;
- Dental PMS becoming the live/main PMS.

## Current Interpretation

Production readiness is not complete. The safe acceleration path is to close
the pending evidence gaps in parallel while keeping R4 live/main PMS and
keeping all live writes, imports, and cutover actions blocked behind a later
explicit go/no-go decision.
