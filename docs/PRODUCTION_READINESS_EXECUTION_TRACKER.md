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
`docs/PRODUCTION_ENV_VERIFICATION_EVIDENCE_COLLECTION.md`. It records
owner/operator-supplied production labels, roles, backup targets, and restore
target classification; verifies unauthenticated read-only frontend/backend/app
health availability; and keeps deployment target verification, latest safe
backup timestamp, and restore rehearsal execution blocked.

Backup/restore rehearsal and UAT/smoke readiness planning is recorded in
`docs/BACKUP_RESTORE_UAT_READINESS_PLAN.md`. That plan does not execute
backup, restore, UAT, smoke tests, production writes, PMS database
connections, or cutover.

Backup discovery and setup planning is recorded in
`docs/PRODUCTION_BACKUP_DISCOVERY_AND_SETUP_PLAN.md`. That plan records
repository-only discovery of backup/restore docs, helpers, and scheduler
templates; it also records owner-preferred candidate storage as Google
Workspace / owner-controlled online storage pending later implementation and
restore proof. It does not access production, run backups, run restores, access
Google Workspace, or claim backup readiness is complete.

Backup implementation/proof preparation is recorded in
`docs/PRODUCTION_BACKUP_IMPLEMENTATION_PROOF_PREP.md`. That document defines
the supplied owner/operator inputs, fastest safe backup proof path,
implementation stop conditions, and evidence required before cutover. It does
not implement backups, run backup commands, run restore commands, access Google
Workspace, connect to production, or claim backup readiness is complete.

Backup automation implementation readiness is recorded in
`docs/PRODUCTION_BACKUP_AUTOMATION_IMPLEMENTATION_READINESS.md`. That document
defines the proposed Google Workspace / owner-controlled online storage backup
architecture, credential handling rules, encryption approach, implementation
work needed, stop conditions, and evidence required before cutover. It does
not implement backup automation, run backups, run restores, access Google
Workspace, create or inspect credentials, or claim backup readiness is
complete.

Backup automation implementation gap analysis is recorded in
`docs/PRODUCTION_BACKUP_AUTOMATION_IMPLEMENTATION_GAP.md`. That record
inspected repository backup helpers, restore helpers, scheduler templates, and
non-secret documentation only. It found local database, files/media, archive,
scheduler, and restore foundations, but did not find Google Workspace upload
support or archive encryption support. It does not execute backups, run
restores, access Google Workspace, create or inspect credentials, connect to
production, or claim backup readiness is complete.

Rclone backup upload/encryption scaffolding is recorded in
`docs/PRODUCTION_BACKUP_RCLONE_SCAFFOLDING.md`. That record identifies rclone
as the candidate Google Workspace/Drive upload mechanism and rclone `crypt` as
the candidate client-side encryption mechanism. It adds non-secret placeholder
templates only; it does not run backups, run restores, access Google
Workspace, create or inspect credentials, connect to production, or claim
backup readiness is complete.

Backup execution readiness is recorded in
`docs/PRODUCTION_BACKUP_EXECUTION_READINESS.md`. That plan binds to the merged
rclone scaffolding and defines the prerequisites, later evidence to collect,
stop conditions, and restore rehearsal prerequisites for a future first-backup
execution slice. It does not run backups, run restores, access Google
Workspace, create or inspect credentials, connect to production, connect to
PMS databases, or claim backup readiness is complete.

Rclone backup runner scaffolding is recorded in
`docs/PRODUCTION_BACKUP_RCLONE_RUNNER.md`, with the non-secret runner scaffold
at `ops/backup_rclone_upload.sh`. The runner is env-driven, dry-run by
default, requires explicit `BACKUP_UPLOAD_CONFIRM` before calling rclone, and
prints only a redacted command shape. This tracker update does not run the
runner, upload backups, run restores, access Google Workspace, create or
inspect credentials, connect to production, or claim backup readiness is
complete.

Rclone credential/setup and first-backup evidence request is recorded in
`docs/PRODUCTION_BACKUP_RCLONE_CREDENTIAL_SETUP_AND_FIRST_BACKUP_REQUEST.md`.
That request defines outside-Git setup steps for the owner/operator and the
non-sensitive evidence to provide later. It does not create credentials,
inspect credentials, access Google Workspace, run backups, run restores,
connect to production, connect to PMS databases, or claim backup readiness is
complete.

Backup/restore evidence intake and sign-off matrix is recorded in
`docs/PRODUCTION_BACKUP_RESTORE_EVIDENCE_INTAKE_AND_SIGNOFF.md`. That template
defines redaction policy, acceptable evidence formats, intake sections,
sign-off rows, and stop conditions. It does not run backups, run restores, run
rclone, access Google Workspace, access credentials, connect to production,
connect to PMS databases, access R4, use patient data, or claim backup
readiness is complete.

Rollback/go-no-go communications planning is recorded in
`docs/PRODUCTION_ROLLBACK_GO_NO_GO_COMMUNICATIONS_PLAN.md`. That plan defines
role-only authority placeholders, go/no-go gates, rollback triggers,
communications matrix, acceptable evidence records, and stop conditions. It
does not execute rollback, execute cutover, access production, access R4,
connect to PMS databases, access patient data, run backup/restore/rclone
commands, access Google Workspace, access credentials, or claim production
readiness is complete.

Production target, user/access, and UAT evidence request is recorded in
`docs/PRODUCTION_TARGET_USER_ACCESS_UAT_EVIDENCE_REQUEST.md`. That request
defines redacted evidence formats for production target acceptance,
user/access review, UAT/practice workflow readiness, and smoke/regression
result classification. It does not verify production, access production,
access R4, connect to PMS databases, query scratch SQLite, access patient
data, access real artefacts, access Google Workspace, access credentials, run
deployment/migration/import/backup/restore/rclone commands, or claim
production readiness is complete.

Data migration scope and import-decision evidence request is recorded in
`docs/PRODUCTION_DATA_MIGRATION_SCOPE_AND_IMPORT_DECISION_REQUEST.md`. That
request defines redacted decision evidence for production data scope,
patient-data migration decisions, opening-balance/live finance import
decisions, invoice/payment/staging import decisions, and final cutover
boundaries. It does not access R4, access real artefacts, use patient data,
access production, connect to PMS databases, query scratch SQLite, run
migration/validation/import commands, run backup/restore/rclone commands,
access Google Workspace, access credentials, or claim production readiness is
complete.

Domain migration, monitoring/support, and cutover communications evidence
request is recorded in
`docs/PRODUCTION_DOMAIN_MIGRATION_SUPPORT_CUTOVER_EVIDENCE_REQUEST.md`. That
request defines redacted decision evidence for appointments/treatments/recalls
migration decisions, monitoring/support readiness, and cutover communications
readiness. It does not access R4, access real artefacts, use patient data,
access production, connect to PMS databases, query scratch SQLite, run
migration/validation/import commands, run monitoring setup, run deployment,
run backup/restore/rclone commands, access Google Workspace, access
credentials, or claim production readiness is complete.

No patient-level contents, raw artefact contents, exact artefact paths, DSNs,
production passwords, live credentials, or secrets belong in this tracker.

## Workstream Tracker

| Workstream | Owner | Status | Blocker | Target Evidence | Go/No-Go Impact |
| --- | --- | --- | --- | --- | --- |
| Business reconciliation closure | Owner/business | Complete | None for non-live evidence closure | Business reconciliation sign-off record | Required input is complete for readiness planning; does not authorise live import or cutover |
| Production environment readiness | Ops owner | Evidence request recorded / pending target acceptance | Environment label supplied and read-only frontend/backend/app health checks passed; deployment target remains pending verification and owner/operator independent availability status was not yet verified | `docs/PRODUCTION_ENV_VERIFICATION_EVIDENCE_COLLECTION.md`, `docs/PRODUCTION_TARGET_USER_ACCESS_UAT_EVIDENCE_REQUEST.md`, then deployment target acceptance | No-go until accepted |
| Backup readiness | Ops owner | Evidence intake/sign-off template recorded / blocked on first backup proof | Repo backup helpers, backup docs, and scheduler templates exist; backup owner/role supplied; storage label supplied as Dental PMS Production Backups; automated service account preferred; daily backup and minimum 30 days retention confirmed; local backup, archive, scheduler, and restore foundations exist; rclone is recorded as the candidate Google Workspace/Drive upload mechanism; rclone crypt is recorded as the candidate client-side encryption mechanism; first-backup prerequisites and evidence plan are recorded; non-secret runner scaffolding is recorded; credential/setup and first-backup evidence request is recorded; backup/restore evidence intake and sign-off template is recorded; credentials, upload execution, encryption proof, current production schedule implementation, storage implementation, latest safe backup timestamp, and backup integrity evidence are unavailable | `docs/PRODUCTION_BACKUP_DISCOVERY_AND_SETUP_PLAN.md`, `docs/PRODUCTION_BACKUP_IMPLEMENTATION_PROOF_PREP.md`, `docs/PRODUCTION_BACKUP_AUTOMATION_IMPLEMENTATION_READINESS.md`, `docs/PRODUCTION_BACKUP_AUTOMATION_IMPLEMENTATION_GAP.md`, `docs/PRODUCTION_BACKUP_RCLONE_SCAFFOLDING.md`, `docs/PRODUCTION_BACKUP_EXECUTION_READINESS.md`, `docs/PRODUCTION_BACKUP_RCLONE_RUNNER.md`, `docs/PRODUCTION_BACKUP_RCLONE_CREDENTIAL_SETUP_AND_FIRST_BACKUP_REQUEST.md`, `docs/PRODUCTION_BACKUP_RESTORE_EVIDENCE_INTAKE_AND_SIGNOFF.md`, then latest safe backup timestamp and backup integrity evidence | No-go until accepted |
| Restore proof | Ops owner | Restore target supplied / pending execution evidence | Restore procedure is documented; supplied restore target classification is local non-live restore rehearsal environment; restore rehearsal is not yet performed | `docs/PRODUCTION_BACKUP_IMPLEMENTATION_PROOF_PREP.md`, `docs/BACKUP_RESTORE_UAT_READINESS_PLAN.md`, then non-live restore rehearsal status/evidence | No-go until accepted |
| Rollback plan | Owner plus ops owner | Template recorded / pending owner acceptance | Rollback owner, triggers, and communication path not accepted | `docs/PRODUCTION_ROLLBACK_GO_NO_GO_COMMUNICATIONS_PLAN.md`, then owner-accepted rollback/go-no-go evidence | No-go until accepted |
| User/access readiness | Practice owner | Evidence request recorded / pending access evidence | User roles and access review not recorded | `docs/PRODUCTION_TARGET_USER_ACCESS_UAT_EVIDENCE_REQUEST.md`, then role/access review for admin, reception, clinical, finance, and support users | No-go for live use until accepted |
| Smoke/regression testing | Technical owner | Evidence request recorded / pending execution evidence | Production-readiness smoke/regression pass not recorded | `docs/BACKUP_RESTORE_UAT_READINESS_PLAN.md`, `docs/PRODUCTION_TARGET_USER_ACCESS_UAT_EVIDENCE_REQUEST.md`, then smoke checklist with pass/fail thresholds | No-go until accepted or explicitly waived |
| UAT/practice workflow testing | Practice owner | Evidence request recorded / pending UAT evidence | UAT checklist and acceptance not recorded | `docs/BACKUP_RESTORE_UAT_READINESS_PLAN.md`, `docs/PRODUCTION_TARGET_USER_ACCESS_UAT_EVIDENCE_REQUEST.md`, then practice workflow checklist covering reception, clinical, documents, recalls, and finance views | No-go until accepted or explicitly waived |
| Data migration scope | Owner plus migration owner | Evidence request recorded / pending evidence | Included/excluded production data scope not finalised | `docs/PRODUCTION_DATA_MIGRATION_SCOPE_AND_IMPORT_DECISION_REQUEST.md`, then signed included/excluded data scope record | No-go until accepted |
| Opening-balance live-import decision | Owner | Evidence request recorded / blocked by owner decision | Live finance import remains unauthorised and `finance_import_ready=false` remains in force | `docs/PRODUCTION_DATA_MIGRATION_SCOPE_AND_IMPORT_DECISION_REQUEST.md`, then separate explicit owner approval for any live opening-balance import | No-go for finance import until approval |
| Patient data migration decision | Owner plus migration owner | Evidence request recorded / pending evidence | Patient import/cutover scope not finalised | `docs/PRODUCTION_DATA_MIGRATION_SCOPE_AND_IMPORT_DECISION_REQUEST.md`, then patient data inclusion/exclusion and duplicate/contact policy classification | No-go until accepted |
| Appointments/treatments/recalls migration decision | Owner plus migration owner | Evidence request recorded / pending evidence | Domain scope and accepted exclusions not finalised | `docs/PRODUCTION_DOMAIN_MIGRATION_SUPPORT_CUTOVER_EVIDENCE_REQUEST.md`, then decision record for appointments, treatments, charting, recalls, and workflow dependencies | No-go until accepted |
| Monitoring/support readiness | Support owner | Evidence request recorded / pending evidence | Monitoring owner acceptance, support window, escalation route, and alert/log review are not recorded | `docs/PRODUCTION_DOMAIN_MIGRATION_SUPPORT_CUTOVER_EVIDENCE_REQUEST.md`, then monitoring/support readiness evidence | No-go until accepted |
| Cutover communications | Owner plus support owner | Evidence request recorded / pending acceptance | Operator communication plan not accepted | `docs/PRODUCTION_DOMAIN_MIGRATION_SUPPORT_CUTOVER_EVIDENCE_REQUEST.md`, then cutover communications acceptance evidence | No-go until accepted |
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
6. Use `docs/BACKUP_RESTORE_UAT_READINESS_PLAN.md` as the next checklist for
   backup/restore rehearsal, UAT, and smoke-readiness execution candidates.
7. Use `docs/PRODUCTION_BACKUP_DISCOVERY_AND_SETUP_PLAN.md` to close the
   backup setup gaps without exposing secrets, private paths, raw dumps, or
   patient data.
8. Use the supplied inputs in
   `docs/PRODUCTION_BACKUP_IMPLEMENTATION_PROOF_PREP.md` to prepare a later
   implementation/proof slice without committing credentials, private paths,
   backup contents, or patient data.
9. Use `docs/PRODUCTION_BACKUP_AUTOMATION_IMPLEMENTATION_READINESS.md` as the
   readiness gate for any later backup automation implementation slice.
10. Use `docs/PRODUCTION_BACKUP_AUTOMATION_IMPLEMENTATION_GAP.md` to close the
   missing Google Workspace upload and archive encryption implementation gaps
   before claiming automated backup readiness.
11. Use `docs/PRODUCTION_BACKUP_RCLONE_SCAFFOLDING.md` as the non-secret
   placeholder basis for a later separately authorised rclone credential setup
   and upload execution slice.
12. Use `docs/PRODUCTION_BACKUP_EXECUTION_READINESS.md` as the gate for any
   later first-backup upload evidence slice.
13. Use `docs/PRODUCTION_BACKUP_RCLONE_RUNNER.md` and
   `ops/backup_rclone_upload.sh` only in a later explicitly authorised
   first-backup execution slice after external credentials and rclone remotes
   are configured outside Git.
14. Use
   `docs/PRODUCTION_BACKUP_RCLONE_CREDENTIAL_SETUP_AND_FIRST_BACKUP_REQUEST.md`
   to collect non-sensitive owner/operator setup evidence before any
   first-backup execution slice.
15. Use `docs/PRODUCTION_BACKUP_RESTORE_EVIDENCE_INTAKE_AND_SIGNOFF.md` as
   the redacted evidence intake and sign-off matrix for backup setup, first
   backup, retention, restore rehearsal, and final go/no-go inputs.
16. Use `docs/PRODUCTION_ROLLBACK_GO_NO_GO_COMMUNICATIONS_PLAN.md` as the
   role-only rollback, go/no-go, and communications plan before any owner
   cutover decision.
17. Use `docs/PRODUCTION_TARGET_USER_ACCESS_UAT_EVIDENCE_REQUEST.md` to
   collect redacted production target acceptance, user/access review,
   UAT/practice workflow, and smoke/regression evidence before final go/no-go.
18. Use
   `docs/PRODUCTION_DATA_MIGRATION_SCOPE_AND_IMPORT_DECISION_REQUEST.md` to
   collect redacted data migration scope, patient/import, opening-balance/live
   finance import, invoice/payment/staging import, and final cutover decision
   evidence.
19. Use
   `docs/PRODUCTION_DOMAIN_MIGRATION_SUPPORT_CUTOVER_EVIDENCE_REQUEST.md` to
   collect redacted domain migration, monitoring/support, and cutover
   communications readiness evidence before final go/no-go.
20. Keep live import blocked until final go/no-go approval explicitly authorises
   it.

## Production Evidence Item Status

| Evidence item | Current status | Current value/evidence | Remaining gap |
| --- | --- | --- | --- |
| Production environment label | Verified | Dental PMS production candidate | None for label; deployment still needs verification |
| Deployment target label | Blocked | Production server / hosting environment pending verification | Owner/operator target verification |
| Frontend availability result | Verified by read-only check / pending owner acceptance | Read-only HTTP GET returned `200` at `2026-05-10T08:32:28Z`; owner/operator independent result not yet verified | Owner acceptance if required |
| Backend availability result | Verified by read-only check / pending owner acceptance | Read-only HTTP GET returned `200` at `2026-05-10T08:32:28Z`; owner/operator independent result not yet verified | Owner acceptance if required |
| App health check result | Verified by read-only check / pending owner acceptance | Read-only HTTP GET returned `200` at `2026-05-10T08:32:28Z`; owner/operator independent result not yet verified | Owner acceptance if required |
| Backup owner/role | Verified | Project owner / production operator | None for role |
| Backup schedule/frequency | Owner confirmed / pending implementation proof | Daily; repo scheduler template exists but current production installation is unverified | Actual production schedule evidence |
| Backup retention policy | Owner confirmed / pending implementation proof | Minimum 30 days; repo retention control exists but current production setting is unverified | Actual retention evidence proving minimum 30 days |
| Backup/restore evidence intake and sign-off template | Recorded / pending evidence | `docs/PRODUCTION_BACKUP_RESTORE_EVIDENCE_INTAKE_AND_SIGNOFF.md` | Outside-Git setup evidence, first backup evidence, latest safe backup timestamp, retention proof, non-live restore proof, backup/restore sign-off, and final go/no-go approval |
| Latest safe backup timestamp | Blocked | Unavailable | Owner/operator evidence or approved backup verification slice |
| Restore rehearsal target classification | Owner confirmed / pending implementation proof | Local non-live restore rehearsal environment | Specific non-live target evidence before execution |
| Restore rehearsal status | Blocked | not yet performed | Approved restore proof slice |
| Monitoring/logging owner role | Verified | Project owner / production operator | None for role |
| Support contact role | Verified | Project owner | None for role |
| Rollback/go-no-go communications plan | Recorded / pending owner acceptance | `docs/PRODUCTION_ROLLBACK_GO_NO_GO_COMMUNICATIONS_PLAN.md` | Owner acceptance, production target acceptance, UAT/access evidence, backup/restore proof, and final go/no-go approval |
| Production target, user/access, and UAT evidence request | Recorded / pending evidence | `docs/PRODUCTION_TARGET_USER_ACCESS_UAT_EVIDENCE_REQUEST.md` | Production target acceptance, access review, UAT/practice workflow evidence, smoke/regression evidence, backup/restore proof, rollback owner acceptance, and final go/no-go approval |
| Data migration scope and import-decision evidence request | Recorded / pending evidence | `docs/PRODUCTION_DATA_MIGRATION_SCOPE_AND_IMPORT_DECISION_REQUEST.md` | Patient/import scope decisions, opening-balance/live finance import approval, invoice/payment/staging import approval, backup/restore proof, UAT/access evidence, rollback owner acceptance, and final go/no-go approval |
| Domain migration, monitoring/support, and cutover communications evidence request | Recorded / pending evidence | `docs/PRODUCTION_DOMAIN_MIGRATION_SUPPORT_CUTOVER_EVIDENCE_REQUEST.md` | Domain migration decisions, monitoring/support readiness, cutover communications acceptance, backup/restore proof, production target acceptance, UAT/access evidence, rollback owner acceptance, and final go/no-go approval |

## Explicit Blockers

- No production rehearsal has been completed.
- No backup/restore proof has been recorded.
- No latest safe backup timestamp has been recorded.
- No current production backup storage implementation evidence has been
  recorded.
- No Google Workspace / owner-controlled online storage implementation proof
  has been recorded.
- Rclone remote-upload and crypt scaffolding is recorded, but no upload or
  encryption execution evidence has been recorded.
- Backup execution readiness is recorded, but first backup execution evidence
  has not been recorded.
- Rclone backup runner scaffolding is recorded, but the runner has not been
  executed and no backup upload evidence has been recorded.
- Rclone credential/setup evidence has been requested, but outside-Git setup
  evidence has not been recorded.
- No backup automation credential handling proof has been recorded.
- No non-live restore rehearsal has been executed.
- No UAT/practice workflow execution evidence has been recorded.
- No production smoke execution evidence has been recorded.
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
