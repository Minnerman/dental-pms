# Dental PMS Production Readiness Evidence Packet and Final Gate Register

Status date: 2026-05-10

Baseline:
`origin/master@0448c82309120d31a89531ad99bbf00984e48c87`

## Scope / Non-Authorisation

This is a consolidated evidence packet and final gate register only. It does
not collect actual sensitive evidence, verify production, verify backups, or
verify restore.

This register does not access R4, production, PMS databases, scratch SQLite,
real artefacts, patient data, backups, Google Workspace, or credentials.

This register does not run backup, restore, rclone, migration,
validation/no-write, guarded apply/write, finance import, opening-balance
import, invoice import, payment import, staging import, patient data import,
monitoring setup, deployment, or cutover commands.

R4 remains the live/main PMS. Dental PMS is not live/main PMS.
`finance_import_ready=false`.

Live/default PMS DB writes, actual PMS Postgres writes, production execution,
production cutover, live finance import, invoice/payment/staging import,
patient data import, and Dental PMS live/main PMS status remain unauthorised.
Production readiness remains incomplete.

## Evidence Redaction Policy

Evidence references and owner/operator responses must use non-sensitive
status, role, timestamp, classification, and yes/no/pending formats only.

Do not include:

- credentials;
- tokens;
- DSNs;
- passwords;
- private URLs;
- exact private filesystem paths;
- raw dumps;
- backup contents;
- generated rclone config;
- OAuth material;
- service-account material;
- crypt passwords or salts;
- patient data;
- patient-level identifiers;
- private staff contact details;
- private infrastructure details;
- R4 artefact paths;
- source database paths;
- monitoring logs containing secrets or patient data;
- support contact private details;
- cutover channels containing private contact details;
- sensitive import logs;
- screenshots containing secrets, private infrastructure, patient data, or
  private contacts.

## Consolidated Source-Doc Index

| Gate area | Source document | Evidence type | Current status | Required approver role | Go/no-go impact |
| --- | --- | --- | --- | --- | --- |
| Rclone runner scaffold | `docs/PRODUCTION_BACKUP_RCLONE_RUNNER.md` and `ops/backup_rclone_upload.sh` | Non-secret runner scaffold and runbook | Recorded; not executed | Project owner / production operator | No-go until outside-Git setup and first backup evidence pass |
| Rclone credential/setup and first-backup request | `docs/PRODUCTION_BACKUP_RCLONE_CREDENTIAL_SETUP_AND_FIRST_BACKUP_REQUEST.md` | Outside-Git setup evidence request | Recorded; evidence pending | Project owner / production operator | No-go until setup evidence and first backup evidence pass |
| Backup/restore evidence intake and sign-off | `docs/PRODUCTION_BACKUP_RESTORE_EVIDENCE_INTAKE_AND_SIGNOFF.md` | Backup, retention, restore, and sign-off intake matrix | Recorded; evidence pending | Backup/restore evidence owners | No-go until signed off |
| Rollback/go-no-go communications | `docs/PRODUCTION_ROLLBACK_GO_NO_GO_COMMUNICATIONS_PLAN.md` | Rollback authority, go/no-go gates, communications matrix | Recorded; owner acceptance pending | Final go/no-go owner plus rollback owner | No-go until accepted |
| Production target/user/access/UAT evidence | `docs/PRODUCTION_TARGET_USER_ACCESS_UAT_EVIDENCE_REQUEST.md` | Production target, access review, UAT, smoke evidence request | Recorded; evidence pending | Project owner, access owner, workflow owners | No-go until accepted |
| Data migration scope/import decision | `docs/PRODUCTION_DATA_MIGRATION_SCOPE_AND_IMPORT_DECISION_REQUEST.md` | Data scope and import decision evidence request | Recorded; decisions pending | Owner, migration owner, finance owner | No-go until decisions are explicit |
| Domain migration/support/cutover evidence | `docs/PRODUCTION_DOMAIN_MIGRATION_SUPPORT_CUTOVER_EVIDENCE_REQUEST.md` | Domain migration, monitoring/support, and communications evidence request | Recorded; evidence pending | Owner, migration owner, support owner | No-go until accepted |
| Production readiness tracker | `docs/PRODUCTION_READINESS_EXECUTION_TRACKER.md` | Consolidated readiness status and blocker tracker | Active; blockers remain | Final go/no-go owner | No-go until all required gates are accepted |

## Final Gate Register

| Gate | Required evidence | Acceptable format | Current status | Required owner/approver role | Blocker if missing | Final go/no-go impact |
| --- | --- | --- | --- | --- | --- | --- |
| Outside-Git rclone setup evidence | rclone installed, Drive remote configured, crypt remote configured, config and credentials stored outside Git | yes/no/pending, role, timestamp, classification | Pending | Project owner / production operator | Cannot prove backup upload path | No-go |
| First backup execution evidence | Timestamp, actor role, redacted command shape, source/destination classification, upload result, crypt confirmation | pass/fail/blocked, role, timestamp, classification | Pending | Project owner / production operator | No first backup proof | No-go |
| Latest safe backup timestamp | Latest safe backup timestamp without private paths or contents | timestamp, role, classification | Pending | Backup owner | No current backup proof | No-go |
| Minimum 30-day retention proof | Retention target and evidence classification | yes/no/pending, role, timestamp, classification | Pending | Backup owner | Retention not proven | No-go |
| Non-live restore rehearsal/proof | Non-live target classification, redacted restore command shape, result, no sensitive data committed | pass/fail/blocked, role, timestamp, classification | Pending | Restore rehearsal owner | Restore not proven | No-go |
| Backup/restore sign-off | Backup and restore evidence accepted | yes/no/pending, role, timestamp | Pending | Backup/restore evidence owners | Backup/restore not accepted | No-go |
| Production target acceptance | Production target classification and owner/operator acceptance | yes/no/pending, role, timestamp, classification | Pending | Project owner / production operator | Target not accepted | No-go |
| User/access review | Admin, reception, clinical, finance/admin, support/ops access review | yes/no/pending, role, timestamp, classification | Pending | Access owner | Access not accepted | No-go |
| UAT/practice workflow evidence | Reception, clinical, documents, recalls, finance-view workflow evidence | pass/fail/blocked, role, timestamp, classification | Pending | Practice workflow owners | Practice workflows not accepted | No-go |
| Smoke/regression evidence | Smoke/regression result classification | pass/fail/blocked, role, timestamp | Pending | Technical owner | Baseline behavior not accepted | No-go |
| Data migration scope decision | Included/excluded category decisions | yes/no/pending, role, timestamp, classification | Pending | Owner plus migration owner | Scope not finalised | No-go |
| Patient data migration decision | Patient migration scope and duplicate/contact policy classification | excluded/pending/approved, role, timestamp, classification | Pending | Owner plus migration owner | Patient import remains unauthorised | No-go |
| Opening-balance/live finance import decision | Explicit category-specific finance decision | blocked/pending/approved/rejected, role, timestamp | Blocked | Owner plus finance owner | `finance_import_ready=false` remains in force | No-go for finance import |
| Invoice/payment/staging import decision | Explicit category-specific invoice/payment/staging decision | blocked/pending/approved/rejected, role, timestamp | Blocked | Owner plus finance owner | Import remains unauthorised | No-go for invoice/payment/staging import |
| Appointments/treatments/recalls migration decision | Domain decisions and dependency classifications | yes/no/pending, role, timestamp, classification | Pending | Owner plus migration owner | Domain scope not accepted | No-go |
| Monitoring/support readiness | Monitoring owner, support owner, support window, escalation, alert/log review classification | yes/no/pending, role, timestamp, classification | Pending | Support owner | Support not accepted | No-go |
| Cutover communications acceptance | Audience, timing, channel, message classification and owner acceptance | yes/no/pending, role, timestamp, classification | Pending | Communication owner plus owner/business | Communications not accepted | No-go |
| Rollback owner acceptance | Rollback triggers, authority, communication boundaries accepted | yes/no/pending, role, timestamp | Pending | Rollback owner | Rollback path not accepted | No-go |
| Final owner go/no-go approval | Explicit go/no-go/hold decision after gate review | go/no-go/hold, role, timestamp, reason classification | Pending | Final go/no-go owner | No final decision | No-go |

## Owner/Operator Response Packet Skeleton

Use this copy-safe skeleton only with non-sensitive values. Do not include
credentials, private paths, URLs, dumps, logs, screenshots, backup contents, or
patient data.

```text
Evidence packet date:
Responder role:

Outside-Git rclone setup evidence: yes/no/pending
First backup execution evidence: pass/fail/blocked/not checked
Latest safe backup timestamp: timestamp or pending
Minimum 30-day retention proof: yes/no/pending
Non-live restore rehearsal/proof: pass/fail/blocked/not checked
Backup/restore sign-off: yes/no/pending

Production target acceptance: yes/no/pending
User/access review: yes/no/pending
UAT/practice workflow evidence: pass/fail/blocked/not checked
Smoke/regression evidence: pass/fail/blocked/not checked

Data migration scope decision: yes/no/pending
Patient data migration decision: excluded/pending/approved by category
Opening-balance/live finance import decision: blocked/pending/approved/rejected
Invoice/payment/staging import decision: blocked/pending/approved/rejected
Appointments/treatments/recalls migration decision: yes/no/pending

Monitoring/support readiness: yes/no/pending
Cutover communications acceptance: yes/no/pending
Rollback owner acceptance: yes/no/pending
Final owner go/no-go approval: go/no-go/hold

Reason classification:
Blocker classification:
No secrets exposed: yes/no
No patient data exposed: yes/no
No private paths exposed: yes/no
No backup contents exposed: yes/no
```

## Final Go/No-Go Decision Template

A `go` decision cannot be inferred. Silence is no-go. Evidence acceptance does
not authorise cutover unless final owner go/no-go explicitly says `go`.
Finance/import approvals must be explicit and category-specific.

```text
Decision state: go / no-go / hold
Decision timestamp:
Final owner role:

Required evidence accepted:
- Outside-Git rclone setup evidence: yes/no
- First backup execution evidence: yes/no
- Latest safe backup timestamp: yes/no
- Minimum 30-day retention proof: yes/no
- Non-live restore rehearsal/proof: yes/no
- Backup/restore sign-off: yes/no
- Production target acceptance: yes/no
- User/access review: yes/no
- UAT/practice workflow evidence: yes/no
- Smoke/regression evidence: yes/no
- Data migration scope decision: yes/no
- Patient data migration decision: yes/no
- Opening-balance/live finance import decision: yes/no
- Invoice/payment/staging import decision: yes/no
- Appointments/treatments/recalls migration decision: yes/no
- Monitoring/support readiness: yes/no
- Cutover communications acceptance: yes/no
- Rollback owner acceptance: yes/no

Explicit live finance import approval: yes/no/blocked
Explicit invoice/payment/staging import approval: yes/no/blocked
Explicit patient data import approval: yes/no/blocked
Explicit Dental PMS live/main PMS approval: yes/no/blocked
Rollback owner acceptance: yes/no
No secrets exposed: yes/no
No patient data exposed: yes/no
```

## Stop Conditions

Stop before recording evidence or proceeding to any execution if:

- R4 access is required;
- real artefact access is required;
- production access is required;
- PMS database access is required;
- scratch SQLite access is required;
- patient data would be exposed;
- credentials, secrets, or private paths would be exposed;
- private infrastructure details would be exposed;
- private support/contact details would be exposed;
- raw dumps or backup contents would be exposed;
- Google Workspace access is requested;
- backup, restore, or rclone execution is requested;
- migration, validation, or import execution is requested;
- monitoring setup execution is requested;
- deployment execution is requested;
- live finance import is requested;
- opening-balance import is requested;
- invoice/payment/staging import is requested;
- patient data import is requested;
- Dental PMS live/main PMS status is requested without final go/no-go approval;
- production cutover is requested;
- patient-facing communication is requested without owner approval;
- evidence cannot be recorded safely without sensitive detail.

## Current Status

The consolidated packet and final gate register is recorded. All external
evidence gates remain pending until owner/operator evidence is supplied and
final go/no-go approval is explicitly recorded.
