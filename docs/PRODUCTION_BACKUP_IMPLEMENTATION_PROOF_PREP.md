# Production Backup Implementation Proof Prep

Status date: 2026-05-10

Baseline:
`origin/master@d6dea51d2e700c886924384b70cc8ebff13eb02d`

This is a docs-only preparation slice for production backup implementation
and proof evidence. It does not implement backups. It does not run backup
commands. It does not run restore commands. It does not access Google
Workspace. It does not connect to any production server, PMS database, local
scratch SQLite database, actual PMS Postgres database, R4 source, or real R4
artefact. It does not use patient data, create scratch-test finance records,
create live finance records, perform live/default PMS DB writes, perform
actual PMS Postgres writes, perform finance import, perform invoice/payment/
staging import, or perform production cutover.

R4 remains the live/main PMS. Dental PMS is not live/main PMS.
`finance_import_ready=false`. Live finance import, live/default PMS DB writes,
actual PMS Postgres writes, production execution, production cutover,
invoice/payment/staging import, and Dental PMS live/main PMS status remain
unauthorised. Production readiness is not complete.

No secrets, DSNs, tokens, passwords, private URLs, exact private filesystem
paths, raw database dumps, backup contents, credentials, or patient data
belong in this document or in later proof records.

## Discovery Summary

The current backup/restore discovery state is:

- repo-level backup helpers exist;
- repo-level backup documentation exists;
- repo-level scheduler templates exist;
- repo-level restore documentation and procedure exist;
- current production backup proof is absent;
- current production backup storage proof is absent;
- latest safe backup timestamp is absent;
- current non-live restore proof is absent;
- Google Workspace / owner-controlled online storage is owner-preferred
  candidate storage only, pending implementation and proof.

The existing repository helpers and docs are useful starting points, but they
do not prove that current production backups are configured, running, retained,
copied to owner-controlled online storage, or restorable.

## Fastest Safe Implementation Path

The fastest safe path is:

1. Choose the storage target.
   - Preferred candidate: Google Workspace / owner-controlled online storage.
   - This must remain a target label until a later authorised implementation
     proves the actual storage path and credential handling.
2. Confirm whether the repo helpers support the chosen storage target directly
   or require an integration setup.
   - Current repo evidence documents local backup helpers and scheduler
     templates.
   - Direct Google Workspace integration is not proven by this prep slice.
3. Create backup configuration in a later implementation slice.
   - That slice must avoid committing credentials, tokens, private paths, or
     backup contents.
4. Run the first backup in a later explicit execution slice.
   - This prep slice does not run it.
5. Record backup timestamp and redacted backup evidence.
   - Evidence should include only non-sensitive status, timestamp, storage
     classification, operator role, and integrity result if safe.
6. Run a non-live restore rehearsal in a later explicit execution slice.
   - Restore target must be confirmed as non-live before execution.
7. Record restore evidence.
   - Evidence should include target classification, pass/fail, timing, and
     redacted validation notes without patient-level contents or secrets.

## Required Owner/Operator Inputs

The following inputs are required before implementation can proceed:

| Input | Requirement |
| --- | --- |
| Google Workspace backup folder/location label | Non-secret label only; no private URL or exact path unless separately approved and safe to disclose. |
| Upload/integration method | Confirm service account, manual upload, or another process without committing credentials. |
| Credential handling plan | Confirm where credentials live, who controls them, and how they stay out of Git. |
| Backup encryption requirement | Confirm whether backups must be encrypted before upload or storage. |
| Backup schedule confirmation | Confirm daily schedule target and operating time window. |
| Retention confirmation | Confirm minimum 30 days retention and whether additional monthly retention is required. |
| Non-live restore target confirmation | Confirm safe target classification before any restore rehearsal. |
| Backup evidence owner | Confirm who records redacted timestamp and integrity evidence. |
| Restore evidence owner | Confirm who records redacted restore pass/fail evidence. |

## Implementation Stop Conditions

Stop before implementation or execution if any of the following applies:

- no safe storage target is confirmed;
- no credential handling plan exists;
- secrets, DSNs, tokens, passwords, private URLs, exact private filesystem
  paths, raw database dumps, backup contents, or patient data would be exposed;
- patient data would be committed;
- a production database write is required;
- live/default PMS DB writes are requested;
- actual PMS Postgres writes are requested;
- a restore target is not clearly non-live;
- Google Workspace access is requested without a separate authorised slice;
- live finance import or production cutover is requested.

## Evidence Needed Before Cutover

The following evidence is required before production cutover can be considered:

- backup created timestamp;
- backup storage classification;
- backup schedule confirmation;
- retention confirmation proving at least 30 days;
- backup integrity result or checksum if safe to disclose;
- restore rehearsal target classification;
- restore rehearsal result pass/fail;
- confirmation that no secrets, credentials, private paths, raw dumps, backup
  contents, or patient-level contents were committed;
- backup/restore owner sign-off;
- final go/no-go approval in a separate decision record.

## Tracker Status

Backup readiness and restore proof remain blocked/pending implementation
evidence. This prep document does not complete backup readiness, restore proof,
production readiness, production execution, live finance import, or cutover.

## Next Safe Slices

The next safe slices are:

1. Owner/operator supplies non-secret storage and credential-handling inputs.
2. Docs-only backup implementation design, if needed.
3. Separately authorised backup configuration implementation.
4. Separately authorised first backup execution evidence.
5. Separately authorised non-live restore rehearsal evidence.
6. Backup/restore sign-off.

Live import and production cutover remain blocked until backup and restore
proof pass and a later explicit owner go/no-go authorises the next production
step.
