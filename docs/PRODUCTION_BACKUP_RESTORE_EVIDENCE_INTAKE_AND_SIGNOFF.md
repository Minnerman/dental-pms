# Production Backup Restore Evidence Intake And Signoff

Status date: 2026-05-10

Baseline:
`origin/master@5ecf5b6dfb4b62ba496c0b0c12a1013896549c22`

This is evidence intake/sign-off documentation only. It does not execute or
verify setup. It does not run backup, restore, or rclone commands. It does not
access Google Workspace or credentials. It does not access production, R4, PMS
databases, patient data, real artefacts, local scratch SQLite, actual PMS
Postgres, backup contents, or raw dumps. It does not perform finance import,
invoice/payment/staging import, live/default PMS DB writes, actual PMS
Postgres writes, or production cutover.

R4 remains the live/main PMS. Dental PMS is not live/main PMS.
`finance_import_ready=false`. Live finance import, live/default PMS DB writes,
actual PMS Postgres writes, production execution, production cutover,
invoice/payment/staging import, and Dental PMS live/main PMS status remain
unauthorised. Production readiness remains incomplete.

## Evidence Redaction Policy

Do not include any of the following in evidence records, PRs, docs, comments,
logs, or screenshots:

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
- sensitive checksums where unsafe.

Use only yes/no, role, timestamp, classification, pass/fail, and redacted
command-shape evidence. If a useful fact cannot be recorded without sensitive
detail, mark it blocked rather than including the sensitive detail.

## Evidence Intake Sections

### Outside-Git Rclone Setup Evidence

Acceptable fields:

- rclone installed: yes/no;
- Google Workspace/Drive remote configured: yes/no;
- rclone `crypt` remote configured: yes/no;
- rclone config stored outside Git: yes/no;
- credentials stored outside Git: yes/no;
- crypt passwords/salts stored outside Git: yes/no;
- destination classification;
- folder label: `Dental PMS Production Backups`;
- no secrets exposed: yes/no;
- no private paths exposed: yes/no;
- no backup contents exposed: yes/no;
- no patient data committed: yes/no.

### First Backup Execution Evidence

Acceptable fields:

- timestamp;
- actor/owner role;
- redacted command shape;
- source archive classification;
- destination classification;
- upload result pass/fail;
- rclone `crypt` / encryption confirmation without exposing secrets;
- backup size if safe;
- checksum if safe and non-sensitive;
- no patient data committed confirmation;
- no secrets committed confirmation.

### Latest Safe Backup Timestamp Evidence

Acceptable fields:

- latest safe backup timestamp;
- source of timestamp by role or classification;
- backup destination classification;
- no private paths exposed: yes/no;
- no backup contents exposed: yes/no;
- no patient data committed: yes/no.

### Retention Proof Evidence

Acceptable fields:

- retention target: minimum 30 days;
- daily schedule target;
- storage classification;
- latest safe backup timestamp;
- retention evidence pass/fail;
- no private paths exposed: yes/no;
- no backup contents exposed: yes/no.

### Non-Live Restore Rehearsal Evidence

Acceptable fields:

- backup selected classification only;
- restore target classification: non-live;
- target is not live/default PMS DB: yes/no;
- target is not production PMS Postgres: yes/no;
- restore command shape redacted;
- restore result pass/fail;
- data exposure confirmation;
- no secrets committed confirmation;
- no patient data committed confirmation.

### Backup/Restore Sign-Off Evidence

Acceptable fields:

- approver role;
- evidence area;
- sign-off state;
- timestamp;
- blocker if missing;
- confirmation that sign-off does not authorise live finance import or
  production cutover unless separately stated.

### Final Go/No-Go Inputs

Acceptable fields:

- backup setup evidence accepted: yes/no;
- first backup evidence accepted: yes/no;
- retention proof accepted: yes/no;
- non-live restore proof accepted: yes/no;
- backup/restore sign-off accepted: yes/no;
- UAT/practice workflow evidence accepted: yes/no;
- final owner go/no-go decision: not recorded / go / no-go;
- explicit live import approval: yes/no;
- explicit Dental PMS live/main PMS approval: yes/no.

## Sign-Off Matrix

| Area | Required evidence | Current status | Required approver | Approval state | Blocker if missing |
| --- | --- | --- | --- | --- | --- |
| Owner/business | Backup/restore evidence accepted for business continuity planning | Pending evidence | Owner/business | Not signed off | Backup/restore proof not recorded |
| Ops owner | Outside-Git setup, first backup, retention, and restore evidence | Pending evidence | Ops owner | Not signed off | Setup and execution evidence not recorded |
| Restore rehearsal owner | Non-live restore target and restore pass/fail evidence | Pending evidence | Restore rehearsal owner | Not signed off | Non-live restore rehearsal not performed |
| Security/credentials owner | Credentials, generated config, and crypt secrets kept outside Git/docs | Pending evidence | Security/credentials owner | Not signed off | Credential handling evidence not recorded |
| Practice workflow/UAT owner | UAT and workflow readiness accepted after backup/restore proof | Pending evidence | Practice workflow/UAT owner | Not signed off | UAT evidence not recorded |
| Finance owner | Finance import remains blocked unless separately approved | Pending decision | Finance owner | Not signed off | Live finance import not authorised |
| Final go/no-go owner | Final cutover approval after all required evidence | Blocked | Final go/no-go owner | Not signed off | No final go/no-go approval |

## Stop Conditions

Stop before evidence recording or any execution if:

- credentials would be exposed;
- generated config would be exposed;
- private paths would be exposed;
- backup contents would be exposed;
- patient data would be exposed or committed;
- raw dumps would be exposed;
- production database write is requested;
- live/default PMS DB write is requested;
- actual PMS Postgres write is requested;
- Google Workspace access is requested from the repo agent;
- rclone, backup, or restore execution is requested from the repo agent;
- live finance import is requested;
- production cutover is requested;
- restore target is not clearly non-live;
- evidence cannot be recorded without sensitive detail.

## Current Status

The backup/restore evidence intake and sign-off template is recorded. Outside-
Git rclone setup evidence, first backup execution evidence, latest safe backup
timestamp, minimum 30-day retention proof, non-live restore rehearsal/proof,
backup/restore sign-off, UAT/practice workflow sign-off, live finance import
approval, and final go/no-go approval remain unavailable or blocked.
