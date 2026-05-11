# Dental PMS Production Readiness Execution Tracker

Status date: 2026-05-10

Baseline:
`origin/master@719c5c8290950cc673d19e20528f5e3f6b2b293a`

This is a docs-only production readiness execution tracker and gap
assessment. It records classification-only production execution status, but it
does not itself perform live import, R4 access, real artefact access,
patient-data review, PMS database connection, validation/no-write, guarded
apply/write, finance import, or invoice/payment/staging import.

Dental PMS is recorded as live/main PMS after successful production smoke. R4
remains available for rollback.
`finance_import_ready=false`.

The R4 opening-balance full eligible-row non-live evidence track is complete
through signed-off guarded apply/write proof, and the independent
business/accounting reconciliation sign-off is recorded. That evidence track
does not authorise live finance import, opening-balance import,
invoice/payment/staging import, patient data import, or uncontrolled PMS DB
writes. Finance/import execution remains blocked until a live-safe guarded
process is available.

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

Consolidated production readiness evidence packet and final gate register is
recorded in
`docs/PRODUCTION_READINESS_EVIDENCE_PACKET_AND_FINAL_GATE_REGISTER.md`. That
packet indexes the existing evidence-request documents, defines the final gate
register, provides a copy-safe owner/operator response skeleton, and records
final go/no-go decision rules. It does not collect actual sensitive evidence,
verify production, verify backups, verify restore, access R4, access real
artefacts, use patient data, access production, connect to PMS databases,
query scratch SQLite, run backup/restore/rclone commands, run
migration/validation/import commands, run monitoring setup, run deployment,
access Google Workspace, access credentials, or claim production readiness is
complete.

Owner/operator readiness evidence status was recorded on 2026-05-10 using
classification-only values. Outside-Git rclone setup evidence is recorded as
`yes`; first backup execution is `blocked`; latest safe backup timestamp is
`pending`; minimum 30-day retention proof is `pending`; non-live restore
rehearsal/proof is `blocked`; backup/restore sign-off is `pending`.
Production target acceptance, user/access review, monitoring/support
readiness, cutover communications acceptance, and rollback owner acceptance
remain `pending`. UAT/practice workflow evidence and smoke/regression evidence
are `not checked`. Data migration scope decision is `yes`, patient data
migration decision is `approved by category`, and
appointments/treatments/recalls migration decision is `yes`; those decisions
do not run or authorise imports by themselves. Opening-balance/live finance
import decision and invoice/payment/staging import decision remain `pending`.
Final owner go/no-go approval remains `hold`.

First backup execution evidence status was updated on 2026-05-10 using
classification-only values. Outside-Git rclone setup evidence remains `yes`;
first backup execution evidence is recorded as `pass`; latest safe backup
timestamp is recorded as `2026-05-10T14:34:56Z`; minimum 30-day retention proof
remains `pending`; non-live restore rehearsal/proof remains `blocked`; and
backup/restore sign-off remains `pending`. This status records only safe
evidence classifications. It does not mark backup readiness complete, does not
mark production readiness complete, and does not authorise live finance import,
opening-balance import, patient data import, invoice/payment/staging import, or
production cutover.

Retention and non-live restore evidence status was updated on 2026-05-10 using
classification-only values. Minimum 30-day retention proof remains `pending`.
Non-live restore rehearsal/proof is recorded as `fail`. Backup/restore sign-off
is recorded as `no`. No secrets, patient data, private paths, or backup
contents were exposed in the evidence status. This status does not mark backup
readiness complete, does not mark production readiness complete, and does not
authorise live finance import, opening-balance import, patient data import,
invoice/payment/staging import, Dental PMS live/main PMS status, or production
cutover.

Restore remediation evidence status was updated on 2026-05-10 using
classification-only values. The restore failure classification is recorded as
`missing database role/user`. Remediation status is recorded as `missing
role/user remediated in non-live target`. Repeat non-live restore
rehearsal/proof is recorded as `pass`. Minimum 30-day retention proof remains
`pending`, and backup/restore sign-off remains `pending`. This status does not
mark backup readiness complete, does not mark production readiness complete,
and does not authorise live finance import, opening-balance import, patient
data import, invoice/payment/staging import, Dental PMS live/main PMS status,
or production cutover.

Retention sign-off evidence status was updated on 2026-05-10 using
classification-only values. Minimum 30-day retention proof is recorded as
`no`. Retention mechanism classification is recorded as `count-based`, and
retention target classification is recorded as `less than 30 days`.
Backup/restore sign-off remains `pending`. This status does not mark backup
readiness complete, does not mark production readiness complete, and does not
authorise live finance import, opening-balance import, patient data import,
invoice/payment/staging import, Dental PMS live/main PMS status, or production
cutover.

Backup retention minimum remediation was recorded on 2026-05-10. The
repo-controlled count-based retention defaults for database and attachments
backups and the daily systemd service template are raised to retain `30`
backups. This is a non-destructive configuration/template remediation only; it
does not run backup, restore, rclone, retention cleanup, production execution,
or cutover. Minimum 30-day retention proof is now classified as `yes` for the
repo-controlled count-based retention setup. Backup readiness remains
incomplete until backup/restore sign-off is recorded.

Backup/restore sign-off acceptance was recorded on 2026-05-10 using
classification-only owner/operator evidence. The accepted scope is Dental PMS
backup and restore readiness evidence, including the post-PR #670 minimum
30-day retention remediation. The decision is `accepted` for backup/restore
readiness tracking only. This sign-off does not authorise production cutover,
finance import, patient import, backup deletion, retention cleanup, R4
replacement, live/default PMS DB writes, actual PMS Postgres writes, or Dental
PMS live/main PMS status.

Production target/access/UAT evidence status was updated on 2026-05-10 using
classification-only values. Smoke/regression evidence is recorded as `pass`
from safe CI status only. Production target acceptance, user/access review,
monitoring/support readiness, cutover communications acceptance, and rollback
owner acceptance remain `pending`; UAT/practice workflow evidence remains `not
checked`; finance/import decisions remain `pending`; final owner go/no-go
approval remains `hold`. This status update does not access production, R4,
PMS databases, patient data, credentials, private paths, logs, screenshots, or
backup contents, and it does not authorise cutover or imports.

Production target, access, monitoring/support, cutover communications, and
rollback ownership evidence status was updated on 2026-05-10 using
classification-only owner/operator evidence. Production target acceptance,
user/access review, monitoring/support readiness, cutover communications
acceptance, and rollback owner acceptance are recorded as `yes` for readiness
tracking only. UAT/practice workflow evidence remains `not checked`;
opening-balance/live finance import and invoice/payment/staging import
decisions remain `pending`; final owner go/no-go approval remains `hold`. This
status update does not access production, R4, PMS databases, patient data,
credentials, private paths, private URLs, logs, screenshots, or backup
contents, and it does not authorise cutover or imports.

Final readiness gate evidence status was updated on 2026-05-10 using
classification-only owner/operator evidence. UAT/practice workflow evidence is
recorded as `pass`; opening-balance/live finance import and
invoice/payment/staging import decisions are recorded as `approved` for
readiness tracking; final owner go/no-go approval is recorded as `go` for
readiness status only. This status update does not run imports, execute
cutover, access production, access R4, connect to PMS databases, access patient
data, expose credentials, private paths, private URLs, logs, screenshots,
database output, or backup contents, and it does not make Dental PMS the
live/main PMS.

Production execution/cutover status was recorded on 2026-05-10 using
classification-only local-operator evidence. Production execution started,
production deployment result, and production smoke result are recorded as
`yes`/`pass`; cutover executed is recorded as `yes`; Dental PMS live/main PMS
is recorded as `yes`; R4 remains available for rollback is recorded as `yes`.
`finance_import_ready=false` remains in force. Finance/import execution result
is recorded as `blocked` because no live-safe guarded import process was
available. Rollback required is recorded as `no`, and rollback executed is
recorded as `not required`. No finance import, opening-balance import, patient
data import, invoice/payment/staging import, rollback, backup, restore, rclone,
or retention cleanup was performed by this status update.

Guarded finance/import execution readiness is recorded in
`docs/PRODUCTION_GUARDED_FINANCE_IMPORT_EXECUTION_READINESS.md`. The repo-only
readiness implementation adds a classification-only guarded executor for
opening-balance/live finance import execution readiness. It defaults to
dry-run/no-write, requires an execution manifest, requires a full eligible-row
opening-balance report, accepts only Dental PMS live/main PMS target
classification for live apply, requires explicit owner production
authorization, requires explicit apply confirmation before write mode, blocks
invoice/payment/staging categories, records counts/classifications only, and
did not run import in this PR. Guarded finance/import process availability is
recorded as `yes`; opening-balance/live finance import execution readiness is
recorded as `ready`; opening-balance/live finance import execution result is
`not checked`; invoice/payment/staging import execution readiness remains
`blocked`; `finance_import_ready=false` remains in force.

Guarded finance/import execution status was recorded on 2026-05-10 using
classification-only local-operator execution evidence. The guarded
opening-balance/live finance import execution slice accepted the production
execution gate and apply confirmation, confirmed the dry-run report and
eligible-row checks, then failed closed with blocker classification
`mapped_patient_missing_in_target`. Guarded finance/import process availability
is recorded as `yes`; opening-balance/live finance import execution readiness
is recorded as `blocked`; opening-balance/live finance import execution result
is recorded as `fail`; invoice/payment/staging import execution readiness and
result remain `blocked`; `finance_import_ready=false` remains in force.
Rollback required is recorded as `yes`, and rollback executed is recorded as
`no`.

Guarded finance/import mapped-patient target remediation was recorded on
2026-05-10. The failed guarded opening-balance import is now classified as
`no writes` because the mapped-patient target blocker occurred before ledger
row creation; rollback required is corrected to `no`, and rollback executed is
corrected to `not required`. The guarded executor now checks mapped-patient
target coverage before the write helper runs, so this blocker fails closed
before any apply/write path. Mapped patient target remediation remains
`blocked` because patient-level mapping remediation requires owner/operator
safe handling. `finance_import_ready=false` remains in force.

Opening-balance import mapping-blocker evidence was recorded on 2026-05-11
using Codex local operator / classification-only execution status. Guarded
finance/import process availability is recorded as `yes`;
opening-balance/live finance import execution readiness is `blocked`;
opening-balance/live finance import execution result is `blocked`; mapped
patient target remediation status is `blocked`; missing target mapping count
is `1017`; import write-state after the previous failed run remains
`no writes`; rollback required is `no`; rollback executed is `not required`;
invoice/payment/staging import execution readiness and result remain
`blocked`; `finance_import_ready=false` remains in force. Reason
classification: target legacy mapping incomplete; safe patient-preparation
evidence unavailable without R4 access; unresolved rows deferred pending
owner/operator mapping/preparation. Blocker classification: patient-level
target mapping requires owner/operator safe handling. Safety confirmations:
no secrets exposed, no patient data exposed, no private paths exposed, and no
backup contents exposed. No import or R4 access was run.

No patient-level contents, raw artefact contents, exact artefact paths, DSNs,
production passwords, live credentials, or secrets belong in this tracker.

## Workstream Tracker

| Workstream | Owner | Status | Blocker | Target Evidence | Go/No-Go Impact |
| --- | --- | --- | --- | --- | --- |
| Business reconciliation closure | Owner/business | Complete | None for non-live evidence closure | Business reconciliation sign-off record | Required input is complete for readiness planning; does not authorise live import or cutover |
| Production environment readiness | Ops owner | Production deployment and smoke passed / cutover recorded | Environment label supplied and read-only frontend/backend/app health checks passed; owner/operator production target acceptance is recorded as yes; final go is recorded; production deployment and smoke are recorded as pass; cutover executed and Dental PMS live/main PMS are recorded as yes | `docs/PRODUCTION_ENV_VERIFICATION_EVIDENCE_COLLECTION.md`, `docs/PRODUCTION_TARGET_USER_ACCESS_UAT_EVIDENCE_REQUEST.md`, final readiness gate record, then production execution status record | Production execution evidence recorded; finance/import remains blocked |
| Backup readiness | Ops owner | Backup/restore evidence accepted / readiness go recorded | Repo backup helpers, backup docs, and scheduler templates exist; backup owner/role supplied; storage label supplied as Dental PMS Production Backups; automated service account preferred; daily backup and minimum 30 days retention target confirmed; local backup, archive, scheduler, and restore foundations exist; rclone is recorded as the candidate Google Workspace/Drive upload mechanism; rclone crypt is recorded as the candidate client-side encryption mechanism; first-backup prerequisites and evidence plan are recorded; non-secret runner scaffolding is recorded; credential/setup and first-backup evidence request is recorded; backup/restore evidence intake and sign-off template is recorded; first encrypted backup upload evidence is recorded as pass with a latest safe backup timestamp; restore failure was classified as missing database role/user and remediated in the non-live target; repeat non-live restore proof is recorded as pass; repo count-based retention now retains 30 backups and minimum 30-day retention proof is classified as yes; backup/restore sign-off is accepted for readiness tracking only; final go is recorded for readiness status only | `docs/PRODUCTION_BACKUP_DISCOVERY_AND_SETUP_PLAN.md`, `docs/PRODUCTION_BACKUP_IMPLEMENTATION_PROOF_PREP.md`, `docs/PRODUCTION_BACKUP_AUTOMATION_IMPLEMENTATION_READINESS.md`, `docs/PRODUCTION_BACKUP_AUTOMATION_IMPLEMENTATION_GAP.md`, `docs/PRODUCTION_BACKUP_RCLONE_SCAFFOLDING.md`, `docs/PRODUCTION_BACKUP_EXECUTION_READINESS.md`, `docs/PRODUCTION_BACKUP_RCLONE_RUNNER.md`, `docs/PRODUCTION_BACKUP_RCLONE_CREDENTIAL_SETUP_AND_FIRST_BACKUP_REQUEST.md`, `docs/PRODUCTION_BACKUP_RESTORE_EVIDENCE_INTAKE_AND_SIGNOFF.md`, then final readiness gate record | Readiness input accepted; cutover execution still requires separate instruction |
| Restore proof | Ops owner | Repeat non-live restore passed / readiness go recorded | Restore procedure is documented; supplied restore target classification is local non-live restore rehearsal environment; original failure classified as missing database role/user; remediation was applied in the non-live target; repeat non-live restore rehearsal/proof is recorded as pass; backup/restore sign-off is accepted for readiness tracking only; final go is recorded for readiness status only | `docs/PRODUCTION_BACKUP_IMPLEMENTATION_PROOF_PREP.md`, `docs/BACKUP_RESTORE_UAT_READINESS_PLAN.md`, then final readiness gate record | Readiness input accepted; cutover execution still requires separate instruction |
| Rollback plan | Owner plus ops owner | Owner acceptance recorded / readiness go recorded | Rollback owner acceptance is recorded as yes for readiness tracking only; final go is recorded for readiness status only | `docs/PRODUCTION_ROLLBACK_GO_NO_GO_COMMUNICATIONS_PLAN.md`, then final readiness gate record | Readiness input accepted; cutover execution still requires separate instruction |
| User/access readiness | Practice owner | Access review accepted / readiness go recorded | User/access review is recorded as yes for readiness tracking only; final go is recorded for readiness status only | `docs/PRODUCTION_TARGET_USER_ACCESS_UAT_EVIDENCE_REQUEST.md`, then final readiness gate record | Readiness input accepted; cutover execution still requires separate instruction |
| Smoke/regression testing | Technical owner | Safe CI evidence recorded / accepted for readiness tracking | Safe non-production CI smoke/regression status is recorded as pass; production target acceptance is recorded as yes | `docs/BACKUP_RESTORE_UAT_READINESS_PLAN.md`, `docs/PRODUCTION_TARGET_USER_ACCESS_UAT_EVIDENCE_REQUEST.md`, then final readiness gate record | Required input accepted for readiness tracking; cutover execution still requires separate instruction |
| UAT/practice workflow testing | Practice owner | Passed / accepted for readiness tracking | UAT/practice workflow evidence is recorded as pass using classification-only owner/operator evidence | `docs/BACKUP_RESTORE_UAT_READINESS_PLAN.md`, `docs/PRODUCTION_TARGET_USER_ACCESS_UAT_EVIDENCE_REQUEST.md`, then final readiness gate record | Required input accepted for readiness tracking; cutover execution still requires separate instruction |
| Data migration scope | Owner plus migration owner | Accepted for readiness tracking | Data migration scope decision is recorded as yes using classification-only evidence | `docs/PRODUCTION_DATA_MIGRATION_SCOPE_AND_IMPORT_DECISION_REQUEST.md`, then final readiness gate record | Readiness input accepted; execution still requires separate instruction |
| Opening-balance live-import decision | Owner | Approved for readiness tracking / target mapping blocked | Opening-balance/live finance import decision is recorded as approved for readiness tracking only; a classification-only guarded executor is available; explicit guarded opening-balance execution failed closed before write; follow-up classification-only evidence records target legacy mapping incomplete, missing target mapping count `1017`, and unresolved rows deferred pending owner/operator mapping/preparation; failed-run write state is classified as `no writes`; rollback is not required; `finance_import_ready=false` remains in force | `docs/PRODUCTION_DATA_MIGRATION_SCOPE_AND_IMPORT_DECISION_REQUEST.md`, `docs/PRODUCTION_GUARDED_FINANCE_IMPORT_EXECUTION_READINESS.md`, then guarded execution status record | Patient-level target mapping requires owner/operator safe handling before another guarded opening-balance execution slice |
| Patient data migration decision | Owner plus migration owner | Approved by category for readiness tracking / execution not run | Patient data migration decision is recorded as approved by category; no patient data import has run | `docs/PRODUCTION_DATA_MIGRATION_SCOPE_AND_IMPORT_DECISION_REQUEST.md`, then separate explicit execution instruction before any import | Import execution still requires separate instruction |
| Appointments/treatments/recalls migration decision | Owner plus migration owner | Accepted for readiness tracking / execution not run | Appointments/treatments/recalls migration decision is recorded as yes; no migration/import execution has run | `docs/PRODUCTION_DOMAIN_MIGRATION_SUPPORT_CUTOVER_EVIDENCE_REQUEST.md`, then separate explicit execution instruction before any import | Import execution still requires separate instruction |
| Monitoring/support readiness | Support owner | Accepted / readiness go recorded | Monitoring/support readiness is recorded as yes for readiness tracking only; final go is recorded for readiness status only | `docs/PRODUCTION_DOMAIN_MIGRATION_SUPPORT_CUTOVER_EVIDENCE_REQUEST.md`, then final readiness gate record | Readiness input accepted; cutover execution still requires separate instruction |
| Cutover communications | Owner plus support owner | Accepted / readiness go recorded | Cutover communications acceptance is recorded as yes for readiness tracking only; final go is recorded for readiness status only | `docs/PRODUCTION_DOMAIN_MIGRATION_SUPPORT_CUTOVER_EVIDENCE_REQUEST.md`, then final readiness gate record | Readiness input accepted; cutover execution still requires separate instruction |
| Final go/no-go approval | Owner | Go recorded / cutover executed | Final owner go/no-go approval is recorded as go for readiness status; production deployment and smoke passed; cutover executed is recorded as yes; Dental PMS live/main PMS is recorded as yes | Explicit go/no-go decision record and production execution status record | Cutover recorded; finance/import execution remains blocked |

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
| Deployment target label | Accepted | Production target acceptance recorded as yes for readiness tracking only | Final go/no-go |
| Frontend availability result | Verified by read-only check / pending owner acceptance | Read-only HTTP GET returned `200` at `2026-05-10T08:32:28Z`; owner/operator independent result not yet verified | Owner acceptance if required |
| Backend availability result | Verified by read-only check / pending owner acceptance | Read-only HTTP GET returned `200` at `2026-05-10T08:32:28Z`; owner/operator independent result not yet verified | Owner acceptance if required |
| App health check result | Verified by read-only check / pending owner acceptance | Read-only HTTP GET returned `200` at `2026-05-10T08:32:28Z`; owner/operator independent result not yet verified | Owner acceptance if required |
| Backup owner/role | Verified | Project owner / production operator | None for role |
| Backup schedule/frequency | Owner confirmed / pending implementation proof | Daily; repo scheduler template exists but current production installation is unverified | Actual production schedule evidence |
| Backup retention policy | Remediated / sign-off accepted | Minimum 30 days target is confirmed; previous retention evidence recorded count-based retention as less than 30 days; repo count-based retention defaults and daily service template are now raised to 30 backups | Final go/no-go |
| Backup/restore evidence intake and sign-off template | Recorded / backup evidence accepted | `docs/PRODUCTION_BACKUP_RESTORE_EVIDENCE_INTAKE_AND_SIGNOFF.md`; outside-Git setup evidence, first backup evidence, latest safe backup timestamp, retention proof, non-live restore proof, and backup/restore sign-off are accepted for readiness tracking | Cutover execution still requires separate instruction |
| First backup execution evidence | Recorded / sign-off accepted | pass at `2026-05-10T14:34:56Z` | Final go/no-go approval |
| Latest safe backup timestamp | Recorded / sign-off accepted | `2026-05-10T14:34:56Z` | Final go/no-go approval |
| Restore rehearsal target classification | Owner confirmed / pending implementation proof | Local non-live restore rehearsal environment | Specific non-live target evidence before execution |
| Restore rehearsal status | Recorded / passed after remediation | pass | Final go/no-go |
| Restore failure classification | Recorded | missing database role/user | None for classification; final go/no-go still pending |
| Restore remediation status | Recorded | missing role/user remediated in non-live target | None for remediation status; final go/no-go still pending |
| Backup/restore sign-off | Accepted | accepted by owner/operator for backup/restore readiness tracking only | None for readiness evidence; cutover execution still requires separate instruction |
| Monitoring/logging owner role | Verified | Project owner / production operator | None for role |
| Support contact role | Verified | Project owner | None for role |
| Rollback/go-no-go communications plan | Owner acceptance recorded / readiness gate accepted | Rollback owner acceptance `yes`; final owner go/no-go approval `go` for readiness status only | Cutover execution still requires separate instruction |
| Production target, user/access, and UAT evidence request | Evidence recorded / readiness gate accepted | Smoke/regression evidence `pass`; production target acceptance `yes`; user/access review `yes`; UAT/practice workflow evidence `pass` | Cutover execution still requires separate instruction |
| Data migration scope and import-decision evidence request | Evidence recorded / import decisions approved for readiness tracking | Data migration scope decision `yes`; patient data migration decision `approved by category`; opening-balance/live finance import decision `approved`; invoice/payment/staging import decision `approved` | Import execution still requires separate instruction |
| Domain migration, monitoring/support, and cutover communications evidence request | Evidence recorded / readiness gate accepted | Monitoring/support readiness `yes`; cutover communications acceptance `yes`; appointments/treatments/recalls migration decision `yes` | Cutover execution still requires separate instruction |
| Consolidated production readiness evidence packet and final gate register | Recorded / readiness gate evidence accepted | `docs/PRODUCTION_READINESS_EVIDENCE_PACKET_AND_FINAL_GATE_REGISTER.md`; final owner go/no-go approval `go` for readiness status only | Superseded by production execution status for cutover; finance/import execution remains blocked |
| Owner/operator readiness evidence status | Recorded / incomplete gates remain | Outside-Git rclone setup evidence `yes`; first backup `blocked`; latest safe backup timestamp `pending`; retention proof `pending`; non-live restore `blocked`; backup/restore sign-off `pending`; data migration scope `yes`; patient data migration `approved by category`; appointments/treatments/recalls migration `yes`; finance/import decisions `pending`; final go/no-go `hold` | First backup, retention, restore, production target, access, UAT, smoke, monitoring/support, cutover communications, rollback acceptance, finance/import approval, and final go/no-go remain unresolved |
| First backup execution evidence status | Recorded / incomplete gates remain | Outside-Git rclone setup evidence `yes`; first backup execution evidence `pass`; latest safe backup timestamp `2026-05-10T14:34:56Z`; retention proof `pending`; non-live restore `blocked`; backup/restore sign-off `pending` | Minimum 30-day retention proof, non-live restore proof, backup/restore sign-off, production target, access, UAT, smoke, monitoring/support, cutover communications, rollback acceptance, finance/import approval, and final go/no-go remain unresolved |
| Retention/restore evidence status | Recorded / restore failed | Minimum 30-day retention proof `pending`; non-live restore rehearsal/proof `fail`; backup/restore sign-off `no` | Retention proof, restore remediation, repeat non-live restore proof, backup/restore sign-off, and final go/no-go remain unresolved |
| Restore remediation evidence status | Recorded / pending sign-off | Restore failure classification `missing database role/user`; restore remediation status `missing role/user remediated in non-live target`; repeat non-live restore rehearsal/proof `pass`; backup/restore sign-off `pending` | Minimum 30-day retention proof, backup/restore sign-off, production target, access, UAT, smoke, monitoring/support, cutover communications, rollback acceptance, finance/import approval, and final go/no-go remain unresolved |
| Retention sign-off evidence status | Recorded / retention proof failed | Minimum 30-day retention proof `no`; retention mechanism classification `count-based`; retention target classification `less than 30 days`; backup/restore sign-off `pending` | Retention remediation, backup/restore sign-off, production target, access, UAT, smoke, monitoring/support, cutover communications, rollback acceptance, finance/import approval, and final go/no-go remain unresolved |
| Backup retention remediation | Recorded / sign-off accepted | Minimum 30-day retention proof `yes`; retention mechanism classification `count-based`; retention target classification `at least 30 days`; backup/restore sign-off `yes` | Production target, access, UAT, smoke, monitoring/support, cutover communications, rollback acceptance, finance/import approval, and final go/no-go remain unresolved |
| Backup/restore sign-off status | Recorded / accepted for readiness tracking only | Backup upload evidence, minimum 30-day retention remediation, and non-live restore proof accepted by owner/operator | Production cutover, finance import, patient import, backup deletion, retention cleanup, R4 replacement, Dental PMS live/main PMS status, and final go/no-go remain unauthorised |
| Production target/access/UAT evidence status | Partial evidence recorded / superseded by final gate status | Production target acceptance `yes`; user/access review `yes`; UAT/practice workflow evidence `not checked`; smoke/regression evidence `pass`; monitoring/support readiness `yes`; cutover communications acceptance `yes`; rollback owner acceptance `yes`; final owner go/no-go `hold` | Superseded by final readiness gate evidence status |
| Final readiness gate evidence status | Recorded / go for readiness status only | UAT/practice workflow evidence `pass`; opening-balance/live finance import decision `approved`; invoice/payment/staging import decision `approved`; final owner go/no-go approval `go` | Production cutover, import execution, Dental PMS live/main PMS status, deployment, and live/default writes still require separate explicit execution instruction |
| Production execution/cutover status | Recorded / cutover complete, finance blocked | Production execution started `yes`; deployment `pass`; smoke `pass`; cutover executed `yes`; Dental PMS live/main PMS `yes`; R4 remains available for rollback `yes`; `finance_import_ready=false`; finance/import execution `blocked`; rollback required `no`; rollback executed `not required` | Finance/import execution still requires a separate explicit execution slice |
| Guarded finance/import execution readiness path | Recorded / opening-balance executor ready | Guarded finance/import process available `yes`; opening-balance/live finance import execution readiness `ready`; opening-balance/live finance import execution result `not checked`; invoice/payment/staging import execution readiness `blocked`; `finance_import_ready=false` | Import execution has not run; invoice/payment/staging import remains unsupported by this guarded path |
| Guarded finance/import execution status | Recorded / opening-balance execution blocked before write | Evidence packet date `2026-05-11`; responder role Codex local operator / classification-only execution status; guarded finance/import process available `yes`; opening-balance/live finance import execution readiness `blocked`; opening-balance/live finance import execution result `blocked`; mapped patient target remediation status `blocked`; missing target mapping count `1017`; import write-state after previous failed run `no writes`; rollback required `no`; rollback executed `not required`; invoice/payment/staging import execution readiness `blocked`; invoice/payment/staging import execution result `blocked`; `finance_import_ready=false`; no secrets, patient data, private paths, or backup contents exposed | Reason classification: target legacy mapping incomplete; safe patient-preparation evidence unavailable without R4 access; unresolved rows deferred pending owner/operator mapping/preparation. Blocker classification: patient-level target mapping requires owner/operator safe handling; invoice/payment/staging remains unsupported by this guarded path |

## Owner/Operator Evidence Status Record - 2026-05-10

Classification-only status:

| Gate | Recorded status |
| --- | --- |
| Outside-Git rclone setup evidence | yes |
| First backup execution evidence | blocked |
| Latest safe backup timestamp | pending |
| Minimum 30-day retention proof | pending |
| Non-live restore rehearsal/proof | blocked |
| Backup/restore sign-off | pending |
| Production target acceptance | pending |
| User/access review | pending |
| UAT/practice workflow evidence | not checked |
| Smoke/regression evidence | not checked |
| Data migration scope decision | yes |
| Patient data migration decision | approved by category |
| Opening-balance/live finance import decision | pending |
| Invoice/payment/staging import decision | pending |
| Appointments/treatments/recalls migration decision | yes |
| Monitoring/support readiness | pending |
| Cutover communications acceptance | pending |
| Rollback owner acceptance | pending |
| Final owner go/no-go approval | hold |

Reason classification: outside-Git rclone setup present; optional crypt salt
not configured; first backup blocked; external readiness gates incomplete.

Blocker classification: first backup execution blocked, latest safe backup
timestamp unavailable, retention proof pending, non-live restore blocked, UAT
and smoke not checked, monitoring/support pending, cutover communications
pending, rollback acceptance pending, finance/import decisions pending, and
final go/no-go on hold.

Safety confirmations: no secrets exposed, no patient data exposed, no private
paths exposed, and no backup contents exposed.

## First Backup Execution Evidence Status Record - 2026-05-10

Classification-only status:

| Gate | Recorded status |
| --- | --- |
| Outside-Git rclone setup evidence | yes |
| First backup execution evidence | pass |
| Latest safe backup timestamp | 2026-05-10T14:34:56Z |
| Minimum 30-day retention proof | pending |
| Non-live restore rehearsal/proof | blocked |
| Backup/restore sign-off | pending |

Reason classification: first encrypted backup upload completed; optional crypt
salt not configured; retention proof and restore proof still pending.

Blocker classification: minimum 30-day retention proof pending; non-live
restore rehearsal blocked; backup/restore sign-off pending.

Safety confirmations: no secrets exposed, no patient data exposed, no private
paths exposed, and no backup contents exposed.

This evidence-status update does not mark backup readiness complete, does not
mark production readiness complete, and does not authorise finance import,
opening-balance import, patient data import, invoice/payment/staging import, or
production cutover.

## Retention and Restore Evidence Status Record - 2026-05-10

Classification-only status:

| Gate | Recorded status |
| --- | --- |
| Outside-Git rclone setup evidence | yes |
| First backup execution evidence | pass |
| Latest safe backup timestamp | 2026-05-10T14:34:56Z |
| Minimum 30-day retention proof | pending |
| Non-live restore rehearsal/proof | fail |
| Backup/restore sign-off | no |

Reason classification: database restore rehearsal failed in non-live target.

Blocker classification: non-live restore rehearsal failed; backup/restore
sign-off not accepted.

Safety confirmations: no secrets exposed, no patient data exposed, no private
paths exposed, and no backup contents exposed.

This evidence-status update does not mark backup readiness complete, does not
mark production readiness complete, and does not authorise finance import,
opening-balance import, patient data import, invoice/payment/staging import,
Dental PMS live/main PMS status, or production cutover.

## Retention Sign-Off Evidence Status Record - 2026-05-10

Classification-only status:

| Gate | Recorded status |
| --- | --- |
| Minimum 30-day retention proof | no |
| Retention mechanism classification | count-based |
| Retention target classification | less than 30 days |
| Backup/restore sign-off | pending |

Reason classification: daily schedule is confirmed but count-based retention is
less than 30.

Blocker classification: minimum 30-day retention proof failed; backup/restore
sign-off pending.

Safety confirmations: no secrets exposed, no patient data exposed, no private
paths exposed, and no backup contents exposed.

This evidence-status update does not mark backup readiness complete, does not
mark production readiness complete, and does not authorise finance import,
opening-balance import, patient data import, invoice/payment/staging import,
Dental PMS live/main PMS status, or production cutover.

## Restore Remediation Evidence Status Record - 2026-05-10

Classification-only status:

| Gate | Recorded status |
| --- | --- |
| Outside-Git rclone setup evidence | yes |
| First backup execution evidence | pass |
| Latest safe backup timestamp | 2026-05-10T14:34:56Z |
| Minimum 30-day retention proof | pending |
| Non-live restore rehearsal/proof | pass |
| Backup/restore sign-off | pending |
| Restore failure classification | missing database role/user |
| Restore remediation status | missing role/user remediated in non-live target |

Reason classification: repeat non-live restore completed after role/user
remediation; retention proof still pending.

Blocker classification: minimum 30-day retention proof pending; backup/restore
sign-off pending.

Safety confirmations: no secrets exposed, no patient data exposed, no private
paths exposed, and no backup contents exposed.

This evidence-status update does not mark backup readiness complete, does not
mark production readiness complete, and does not authorise finance import,
opening-balance import, patient data import, invoice/payment/staging import,
Dental PMS live/main PMS status, or production cutover.

## Backup Retention Remediation Evidence Status Record - 2026-05-10

Classification-only status:

| Gate | Recorded status |
| --- | --- |
| Minimum 30-day retention proof | yes |
| Retention mechanism classification | count-based |
| Retention target classification | at least 30 days |
| Backup/restore sign-off | pending |

Reason classification: repo-controlled daily backup template and count-based
retention defaults are set to retain 30 backups.

Blocker classification: backup/restore sign-off pending; production target,
access, UAT, smoke, monitoring/support, cutover communications, rollback
acceptance, finance/import approvals, and final go/no-go remain unresolved.

Safety confirmations: no secrets exposed, no patient data exposed, no private
paths exposed, and no backup contents exposed.

This evidence-status update does not mark backup readiness complete, does not
mark production readiness complete, and does not authorise finance import,
opening-balance import, patient data import, invoice/payment/staging import,
Dental PMS live/main PMS status, or production cutover.

## Backup Restore Sign-Off Evidence Status Record - 2026-05-10

Classification-only status:

| Gate | Recorded status |
| --- | --- |
| Backup/restore sign-off | yes |
| Accepted by | Owner/operator |
| Scope accepted | Dental PMS backup and restore readiness evidence, including post-PR #670 minimum 30-day retention remediation |
| Decision | accepted |

Reason classification: backup upload evidence, minimum 30-day retention
remediation, and non-live restore proof accepted for backup/restore readiness
tracking only.

Blocker classification: production target, access, UAT, smoke,
monitoring/support, cutover communications, rollback acceptance, finance/import
approvals, and final go/no-go remain unresolved.

Safety confirmations: no secrets exposed, no patient data exposed, no private
paths exposed, and no backup contents exposed.

This sign-off does not authorise production cutover, finance import, patient
import, backup deletion, retention cleanup, R4 replacement, live/default PMS DB
writes, actual PMS Postgres writes, Dental PMS live/main PMS status, or final
go/no-go approval.

## Production Target Access UAT Evidence Status Record - 2026-05-10

Classification-only status:

| Gate | Recorded status |
| --- | --- |
| Production target acceptance | pending |
| User/access review | pending |
| UAT/practice workflow evidence | not checked |
| Smoke/regression evidence | pass |
| Monitoring/support readiness | pending |
| Cutover communications acceptance | pending |
| Rollback owner acceptance | pending |
| Data migration scope decision | yes |
| Patient data migration decision | approved by category |
| Opening-balance/live finance import decision | pending |
| Invoice/payment/staging import decision | pending |
| Appointments/treatments/recalls migration decision | yes |
| Final owner go/no-go approval | hold |

Reason classification: safe CI smoke/regression status is pass; production
target, access, UAT, monitoring/support, cutover communications, rollback,
finance/import approvals, and final go/no-go evidence remain incomplete.

Blocker classification: production target acceptance pending; user/access
review pending; UAT not checked; monitoring/support readiness pending; cutover
communications acceptance pending; rollback owner acceptance pending;
finance/import approvals pending; final go/no-go hold.

Safety confirmations: no secrets exposed, no patient data exposed, no private
paths exposed, and no backup contents exposed.

This evidence-status update does not mark production readiness complete and
does not authorise finance import, opening-balance import, patient data import,
invoice/payment/staging import, Dental PMS live/main PMS status, deployment,
or production cutover.

## Target Access Monitoring Rollback Evidence Status Record - 2026-05-10

Classification-only status:

| Gate | Recorded status |
| --- | --- |
| Production target acceptance | yes |
| User/access review | yes |
| Monitoring/support readiness | yes |
| Cutover communications acceptance | yes |
| Rollback owner acceptance | yes |
| UAT/practice workflow evidence | not checked |
| Opening-balance/live finance import decision | pending |
| Invoice/payment/staging import decision | pending |
| Final owner go/no-go approval | hold |

Reason classification: owner/operator accepts production target, user/access
review, monitoring/support readiness, cutover communications, and rollback
ownership for readiness tracking only.

Blocker classification: UAT/practice workflow evidence, finance/import
decisions, and final go/no-go remain unresolved.

Safety confirmations: no secrets exposed, no patient data exposed, no private
paths exposed, and no backup contents exposed.

This evidence-status update does not mark production readiness complete and
does not authorise finance import, opening-balance import, patient data import,
invoice/payment/staging import, Dental PMS live/main PMS status, deployment,
or production cutover.

## Final Readiness Gate Evidence Status Record - 2026-05-10

Classification-only status:

| Gate | Recorded status |
| --- | --- |
| UAT/practice workflow evidence | pass |
| Opening-balance/live finance import decision | approved |
| Invoice/payment/staging import decision | approved |
| Final owner go/no-go approval | go |

Reason classification: owner/operator accepts UAT/practice workflow evidence
and approves remaining finance/import decisions for readiness tracking; final
go/no-go is go for readiness status only.

Blocker classification: no remaining readiness evidence blocker recorded;
production cutover still requires separate explicit execution instruction.

Safety confirmations: no secrets exposed, no patient data exposed, no private
paths exposed, and no backup contents exposed.

This evidence-status update does not run imports, does not execute cutover,
does not access production, R4, PMS databases, patient data, credentials,
private paths, private URLs, logs, screenshots, database output, or backup
contents, and does not make Dental PMS the live/main PMS. R4 remains the
live/main PMS. `finance_import_ready=false` remains in force until a separate
explicit execution slice changes it.

## Production Execution Cutover Status Record - 2026-05-10

Classification-only status:

| Gate | Recorded status |
| --- | --- |
| Production execution started | yes |
| Production deployment result | pass |
| Production smoke result | pass |
| Cutover executed | yes |
| Dental PMS live/main PMS | yes |
| R4 remains available for rollback | yes |
| finance_import_ready | false |
| Finance/import execution result | blocked |
| Rollback required | no |
| Rollback executed | not required |

Reason classification: production deployment and smoke passed; live/main
status changed after smoke; finance/import execution blocked because no
live-safe guarded import process was available.

Blocker classification: finance/import execution remains blocked; separate
guarded import execution still required.

Safety confirmations: no secrets exposed, no patient data exposed, no private
paths exposed, and no backup contents exposed.

This production execution status record does not record credentials, patient
data, private paths, private URLs, logs, screenshots, configs, database output,
raw dumps, or backup contents. No finance import, opening-balance import,
patient data import, invoice/payment/staging import, backup deletion,
retention cleanup, R4 modification, or rollback was performed by this status
record. `finance_import_ready=false` remains in force.

## Guarded Finance Import Execution Readiness Record - 2026-05-10

Classification-only status:

| Gate | Recorded status |
| --- | --- |
| Guarded finance/import process available | no |
| Opening-balance/live finance import execution readiness | blocked |
| Invoice/payment/staging import execution readiness | blocked |

Reason classification: existing repository finance apply tooling is
scratch/test guarded only, refuses default/live-looking PMS database targets,
writes only manifest-scoped patient ledger adjustment rows, and refuses
invoice, payment, staging, balance-mutation, or other finance record intents.

Blocker classification: live-safe guarded finance/import execution process is
missing; opening-balance/live finance import and invoice/payment/staging import
execution remain blocked.

Safety confirmations: no secrets exposed, no patient data exposed, no private
paths exposed, and no backup contents exposed.

This readiness record does not run import, connect to PMS databases, access
R4, access production, access patient data, expose credentials, private paths,
private URLs, logs, screenshots, configs, raw dumps, database output, or backup
contents.

## Explicit Blockers

- Production cutover execution is recorded as complete after successful
  production smoke.
- Dental PMS live/main PMS is recorded as yes.
- R4 remains available for rollback.
- Backup/restore proof is accepted for backup/restore readiness tracking.
- First backup execution evidence and latest safe backup timestamp are
  recorded, and repo retention is remediated to retain 30 backups.
- No Google Workspace / owner-controlled online storage implementation proof
  has been recorded.
- Rclone remote-upload and crypt scaffolding is recorded, and first encrypted
  upload evidence is recorded as pass; retention proof was recorded as no
  before repo retention remediation, and repeat non-live restore proof is
  recorded as pass.
- Backup execution readiness is recorded, and first backup execution evidence
  is now recorded as pass.
- Rclone backup runner scaffolding is recorded, and first backup upload
  evidence is now recorded as pass.
- Rclone credential/setup evidence has been requested, and outside-Git setup
  evidence is recorded as yes.
- No backup automation credential handling proof has been recorded.
- Non-live restore rehearsal/proof is recorded as pass after remediation, and
  backup/restore sign-off is accepted for readiness tracking only.
- UAT/practice workflow evidence is recorded as pass for readiness tracking.
- Safe CI smoke/regression evidence is recorded as pass, but production target
  acceptance and owner/operator production target/access/support/rollback
  acceptance are now recorded for readiness tracking only.
- Opening-balance/live finance import and invoice/payment/staging import
  decisions are approved for readiness tracking. A classification-only guarded
  opening-balance executor is recorded as available. The first guarded
  opening-balance execution is classified as no-write and blocked by
  `mapped_patient_missing_in_target`; invoice/payment/staging import remains
  blocked.
- Final owner go/no-go approval is recorded as go, and cutover execution is
  recorded as complete.
- R4 remains available for rollback.

## Still Unauthorised

The following remain blocked or unauthorised until target mapping remediation
is complete, the guarded process receives separate explicit execution
instruction, and safe execution evidence is recorded:

- live finance import execution;
- opening-balance import execution;
- invoice/payment/staging import execution;
- patient data import execution;
- uncontrolled PMS DB writes;
- unsafe R4 modification;
- backup deletion or destructive retention cleanup.

## Current Interpretation

Production deployment and smoke are recorded as passed, cutover is recorded as
executed, and Dental PMS is recorded as live/main PMS. R4 remains available for
rollback. A guarded opening-balance finance/import executor is recorded as
available. The first guarded opening-balance execution failed closed with
blocker classification `mapped_patient_missing_in_target`; the failed-run write
state is classified as `no writes`, rollback is not required, and
`finance_import_ready=false` remains in force. A 2026-05-11
classification-only blocker record confirms target legacy mapping incomplete,
missing target mapping count `1017`, safe patient-preparation evidence
unavailable without R4 access, and unresolved rows deferred pending
owner/operator mapping/preparation. The next step must remediate patient-level
target mapping through owner/operator safe handling before another explicit
guarded execution slice.
