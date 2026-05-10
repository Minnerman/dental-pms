# Dental PMS Production Data Migration Scope and Import Decision Request

Status date: 2026-05-10

Baseline:
`origin/master@b1f95a18abd7d3c504b1ce26f9fc80cfa8a259d0`

## Scope / Non-Authorisation

This is evidence-request documentation only. It does not access R4,
production, PMS databases, scratch SQLite, real artefacts, patient data,
backups, Google Workspace, or credentials.

This request does not run migration, validation/no-write, guarded apply/write,
finance import, opening-balance import, invoice import, payment import, staging
import, backup, restore, rclone, deployment, or cutover commands.

R4 remains the live/main PMS. Dental PMS is not live/main PMS.
`finance_import_ready=false`.

Live/default PMS DB writes, actual PMS Postgres writes, production execution,
production cutover, live finance import, invoice/payment/staging import, and
patient data import remain unauthorised. Production readiness remains
incomplete.

## Evidence Redaction Policy

Evidence must use non-sensitive role, decision, timestamp, category,
classification, and yes/no/pending formats only.

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
- live import logs containing sensitive data.

## Data Migration Scope Decision Evidence

Accept only:

- included data category: yes/no/pending;
- excluded data category: yes/no/pending;
- owner decision role;
- timestamp;
- reason classification;
- duplicate/contact policy classification;
- no patient data exposed confirmation;
- no secrets exposed confirmation.

Required categories:

- patients/demographics;
- appointments;
- recalls;
- documents;
- charting/clinical view data;
- finance/opening balance;
- invoices;
- payments;
- staged/import-only data;
- settings/admin configuration;
- users/access roles.

## Opening-Balance and Finance Import Decision Evidence

`finance_import_ready=false` remains in force. Live finance import is
unauthorised. Opening-balance import is unauthorised unless separately
approved. Invoice/payment/staging import is unauthorised unless separately
approved.

Finance-view UAT does not authorise finance import. Backup/restore proof does
not authorise finance import. Final go/no-go must explicitly state whether
finance import remains blocked or is approved.

Accept only:

- decision state: blocked / pending / approved / rejected;
- approver role;
- timestamp;
- finance category classification;
- no patient data exposed confirmation;
- no secrets exposed confirmation.

## Patient Data Migration Decision Evidence

No patient data may be included in Git, docs, comments, logs, or screenshots.
No patient import may run from the repo agent. Any patient data import requires
separate explicit owner approval and final go/no-go gating. Duplicate/contact
policy must be classification-only.

Accept only:

- patient migration scope: excluded / pending / approved by category;
- approver role;
- timestamp;
- duplicate policy classification;
- contact policy classification;
- consent/retention/legal review classification if supplied by owner;
- no patient data exposed confirmation.

## Import Decision Table

| Area | Current authorisation state | Required evidence | Acceptable format | Required approver role | Blocker if missing |
| --- | --- | --- | --- | --- | --- |
| Patient demographics import | Unauthorised | Included/excluded category decision, duplicate/contact policy classification, no patient data exposed confirmation | yes/no/pending, role, timestamp, classification | Owner plus migration owner | No patient import until approved |
| Appointment import | Unauthorised | Included/excluded category decision and reason classification | yes/no/pending, role, timestamp, classification | Owner plus migration owner | No appointment import until approved |
| Recall import | Unauthorised | Included/excluded category decision and reason classification | yes/no/pending, role, timestamp, classification | Owner plus migration owner | No recall import until approved |
| Document import | Unauthorised | Included/excluded category decision and no patient data exposed confirmation | yes/no/pending, role, timestamp, classification | Owner plus migration owner | No document import until approved |
| Charting/clinical view import | Unauthorised | Included/excluded category decision and no patient data exposed confirmation | yes/no/pending, role, timestamp, classification | Owner plus clinical workflow owner | No clinical import until approved |
| Opening-balance import | Unauthorised | Explicit finance/opening-balance import decision | blocked/pending/approved/rejected, role, timestamp, classification | Owner plus finance owner | `finance_import_ready=false` remains in force |
| Invoice import | Unauthorised | Explicit invoice import decision | blocked/pending/approved/rejected, role, timestamp, classification | Owner plus finance owner | No invoice import until approved |
| Payment import | Unauthorised | Explicit payment import decision | blocked/pending/approved/rejected, role, timestamp, classification | Owner plus finance owner | No payment import until approved |
| Staging import | Unauthorised | Explicit staging/import-only data decision | blocked/pending/approved/rejected, role, timestamp, classification | Owner plus finance owner | No staging import until approved |
| Settings/admin configuration import | Unauthorised | Included/excluded category decision and owner acceptance | yes/no/pending, role, timestamp, classification | Owner plus ops owner | No settings import until approved |
| User/access role import | Unauthorised | Included/excluded category decision and access review evidence | yes/no/pending, role, timestamp, classification | Owner plus access owner | No user/access import until approved |
| Final production cutover | Unauthorised | Final go/no-go after all evidence gates | go/no-go/hold, role, timestamp, reason classification | Final go/no-go owner | No cutover until explicit final approval |

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
- raw dumps or backup contents would be exposed;
- Google Workspace access is requested;
- backup, restore, or rclone execution is requested;
- migration, validation, or import execution is requested;
- live finance import is requested;
- opening-balance import is requested;
- invoice/payment/staging import is requested;
- patient data import is requested;
- Dental PMS live/main PMS status is requested without final go/no-go approval;
- production cutover is requested;
- evidence cannot be recorded safely without sensitive detail.

## Current Status

This request is recorded as a planning and evidence-intake aid only. Patient
and import scope decisions, opening-balance/live finance import approval,
invoice/payment/staging import approval, backup/restore proof, UAT/access
evidence, rollback owner acceptance, and final go/no-go approval remain
unavailable.
