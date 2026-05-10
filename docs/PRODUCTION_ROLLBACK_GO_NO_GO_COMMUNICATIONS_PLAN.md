# Production Rollback Go/No-Go Communications Plan

Status date: 2026-05-10

Baseline:
`origin/master@be3ae6062f3b3c93e936c855c6178a6b01b0ef53`

This is rollback/go-no-go/communications documentation only. It does not
execute rollback. It does not execute cutover. It does not access production,
R4, PMS databases, patient data, backups, Google Workspace, credentials, real
artefacts, local scratch SQLite, actual PMS Postgres, raw dumps, or backup
contents. It does not run backup, restore, rclone, migration, import, or
deployment commands. It does not perform finance import,
invoice/payment/staging import, live/default PMS DB writes, actual PMS
Postgres writes, or production cutover.

R4 remains the live/main PMS. Dental PMS is not live/main PMS.
`finance_import_ready=false`. Live finance import, live/default PMS DB writes,
actual PMS Postgres writes, production execution, production cutover,
invoice/payment/staging import, and Dental PMS live/main PMS status remain
unauthorised. Production readiness remains incomplete.

## Rollback Owner And Authority Model

Use roles only. Do not include private names, phone numbers, email addresses,
credentials, private URLs, private paths, or patient data unless already
intentionally public and safe.

| Authority area | Role placeholder | Current status |
| --- | --- | --- |
| Final go/no-go owner | Final owner/go-no-go approver | Pending assignment/acceptance |
| Rollback decision owner | Rollback decision owner | Pending assignment/acceptance |
| Ops executor role | Ops/support executor | Pending assignment/acceptance |
| Practice communications owner | Practice communications owner | Pending assignment/acceptance |
| Finance decision owner | Finance owner | Pending assignment/acceptance |
| Clinical/reception workflow owner | Clinical/reception workflow owner | Pending assignment/acceptance |
| Escalation contact role | Escalation contact role | Pending assignment/acceptance |

## Go/No-Go Gates

Required go inputs:

- outside-Git rclone setup evidence accepted;
- first backup execution evidence accepted;
- latest safe backup timestamp recorded;
- minimum 30-day retention proof accepted;
- non-live restore rehearsal passed;
- backup/restore sign-off accepted;
- production environment target accepted;
- user/access review accepted;
- UAT/practice workflow evidence accepted;
- rollback plan accepted;
- final owner go/no-go approval recorded.

Hard no-go conditions:

- no latest safe backup timestamp;
- no restore proof;
- missing backup/restore sign-off;
- missing production target acceptance;
- unresolved credential/security evidence;
- unresolved user/access review;
- unresolved UAT/practice workflow evidence;
- any request to expose secrets or patient data;
- any request for unauthorised live finance import;
- any request for cutover without final owner approval.

## Rollback Triggers

These are non-executing trigger definitions only:

- login/access failure;
- appointment/workflow-blocking failure;
- finance/invoice/payment discrepancy;
- data integrity concern;
- backup/restore evidence concern;
- performance/availability failure;
- security/credential concern;
- owner/operator no-go decision.

## Rollback Action Boundary

This document describes decision and evidence requirements only. It does not
include executable rollback commands. It does not include private
infrastructure details. It does not include production paths, credentials,
DSNs, backup locations, generated rclone config, OAuth material,
service-account material, crypt passwords, salts, raw dumps, backup contents,
or patient data.

Any later rollback or cutover execution requires a separate explicit
owner-approved slice with its own safety gates.

## Communications Matrix

| Audience | Trigger | Message owner role | Timing | Approved channel classification | Required content | Forbidden content |
| --- | --- | --- | --- | --- | --- | --- |
| Practice owner/business | Go/no-go, hold, rollback, or evidence gap | Practice communications owner | Before decision and after outcome | Owner-approved business channel | Decision state, reason classification, next decision owner | Secrets, credentials, patient data, private paths, backup contents, raw dumps, private URLs, DSNs |
| Reception/front desk | Workflow change, hold, or rollback affecting booking/reception | Practice communications owner | Before workflow change where feasible | Internal operational channel | Affected workflow classification, expected user action, support role | Secrets, credentials, patient data, private paths, backup contents, raw dumps, private URLs, DSNs |
| Clinical users | Clinical workflow hold or no-go | Clinical/reception workflow owner | Before clinical workflow change where feasible | Internal clinical workflow channel | Affected workflow classification, use/hold instruction, escalation role | Secrets, credentials, patient data, private paths, backup contents, raw dumps, private URLs, DSNs |
| Finance/admin users | Finance workflow hold, finance no-go, or import remains blocked | Finance owner | Before finance workflow change where feasible | Internal finance/admin channel | Finance decision state, blocked/import status, approval boundary | Secrets, credentials, patient data, private paths, backup contents, raw dumps, private URLs, DSNs |
| Ops/support | Environment issue, rollback trigger, or go/no-go decision | Ops/support owner | At trigger detection and after decision | Internal ops/support channel | Trigger classification, decision owner, evidence needed, safe next action | Secrets, credentials, patient data, private paths, backup contents, raw dumps, private URLs, DSNs |
| Patients, if applicable | Patient-facing service impact | Practice communications owner | Only if owner approves patient-facing message | Owner-approved patient-facing channel | Generic service-impact wording and contact route classification | Secrets, credentials, patient data, private paths, backup contents, raw dumps, private URLs, DSNs |
| External vendor/support, if applicable | Owner-approved external support need | Escalation contact role | Only after owner approval | Owner-approved external support channel | Issue classification and non-sensitive request | Secrets, credentials, patient data, private paths, backup contents, raw dumps, private URLs, DSNs |

## Evidence Records

Acceptable rollback/go-no-go evidence:

- timestamp;
- approver role;
- decision state: go/no-go/rollback/hold;
- reason classification;
- affected workflow classification;
- communication sent: yes/no;
- rollback outcome: pass/fail/not executed;
- no secrets exposed confirmation;
- no patient data exposed confirmation.

Do not record private names, personal contact details, credentials, private
URLs, exact private paths, raw dumps, backup contents, generated rclone config,
OAuth material, service-account material, crypt passwords, salts, or patient
data.

## Stop Conditions

Stop if:

- rollback or cutover execution is requested from the repo agent;
- production access is required;
- R4 access is required;
- PMS database access is required;
- patient data would be exposed;
- credentials, secrets, or private paths would be exposed;
- backup contents or raw dumps would be exposed;
- Google Workspace access is requested;
- live finance import is requested without explicit final approval;
- Dental PMS live/main PMS status is requested without final go/no-go approval;
- evidence cannot be recorded safely without sensitive detail.

## Current Status

The rollback/go-no-go communications plan is recorded, but owner acceptance,
production target acceptance, user/access review, UAT/practice workflow
evidence, backup/restore proof, backup/restore sign-off, and final go/no-go
approval remain unavailable.
