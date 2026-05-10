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

The fastest safe path, using the supplied owner/operator inputs, is:

1. Choose the storage target.
   - Supplied target label: Dental PMS Production Backups.
   - Target class: Google Workspace / owner-controlled online storage.
   - This must remain a target label until a later authorised implementation
     proves the actual storage path and credential handling.
2. Confirm whether the repo helpers support the chosen storage target directly
   or require an integration setup.
   - Current repo evidence documents local backup helpers and scheduler
     templates.
   - Direct Google Workspace integration is not proven by this prep slice.
3. Confirm archive encryption support.
   - Owner requires Google Workspace/Drive storage encryption plus backup
     archive encryption if supported by the repo helpers.
   - Archive encryption support is not proven by this prep slice. If the
     helpers do not support archive encryption, record that as an
     implementation blocker instead of claiming encryption is complete.
4. Create backup configuration in a later implementation slice.
   - That slice must avoid committing credentials, tokens, private paths, or
     backup contents.
5. Run the first backup in a later explicit execution slice.
   - This prep slice does not run it.
6. Record backup timestamp and redacted backup evidence.
   - Evidence should include only non-sensitive status, timestamp, storage
     classification, operator role, and integrity result if safe.
7. Run a non-live restore rehearsal in a later explicit execution slice.
   - Restore target must be confirmed as non-live before execution.
8. Record restore evidence.
   - Evidence should include target classification, pass/fail, timing, and
     redacted validation notes without patient-level contents or secrets.

## Owner/Operator Inputs Supplied

The following non-secret owner/operator inputs have been supplied for planning:

| Input | Supplied value |
| --- | --- |
| Google Workspace backup folder/location label | Dental PMS Production Backups |
| Backup method preference | Automated service account preferred; manual upload fallback only if automation is not yet implemented |
| Credential handling plan | Credentials must be stored outside Git through environment/secret storage only; no credentials, tokens, DSNs, private URLs, or private paths may be committed |
| Encryption requirement | Google Workspace/Drive storage encryption plus backup archive encryption if supported by the repo helpers; if archive encryption is not supported, record it as an implementation blocker |
| Backup schedule confirmation | Daily |
| Retention confirmation | Minimum 30 days |
| Safe non-live restore target | Local non-live restore rehearsal environment |
| Backup evidence owner | Project owner / production operator |
| Restore evidence owner | Project owner / production operator |

These inputs are sufficient to prepare the next implementation design or
implementation-proof slice, but they are not implementation proof. Current
backup storage setup, archive encryption support, latest safe backup
timestamp, backup integrity, and non-live restore proof are still absent.

## Implementation Stop Conditions

Stop before implementation or execution if any of the following applies:

- no safe storage target is confirmed;
- no credential handling plan exists;
- archive encryption is required but unsupported or unplanned;
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
- archive encryption support or explicit accepted blocker;
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

1. Confirm the supplied non-secret storage and credential-handling inputs remain
   accepted at implementation time.
2. Docs-only backup implementation design, if needed.
3. Separately authorised backup configuration implementation.
4. Separately authorised first backup execution evidence.
5. Separately authorised non-live restore rehearsal evidence.
6. Backup/restore sign-off.

Live import and production cutover remain blocked until backup and restore
proof pass and a later explicit owner go/no-go authorises the next production
step.
