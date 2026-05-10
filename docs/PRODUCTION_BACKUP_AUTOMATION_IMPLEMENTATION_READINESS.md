# Production Backup Automation Implementation Readiness

Status date: 2026-05-10

Baseline:
`origin/master@1ce520d3e02171b9f6f2c36800edda126c6927c6`

This is a docs-only implementation-readiness plan for production backup
automation. It does not implement backup automation yet. It does not run
backup commands. It does not run restore commands. It does not access Google
Workspace. It does not create or inspect credentials. It does not connect to a
production server, any PMS database, local scratch SQLite, actual PMS
Postgres, R4, or any real R4 artefact. It does not use patient data, create
scratch-test finance records, create live finance records, perform
live/default PMS DB writes, perform actual PMS Postgres writes, perform
finance import, perform invoice/payment/staging import, or perform production
cutover.

R4 remains the live/main PMS. Dental PMS is not live/main PMS.
`finance_import_ready=false`. Live finance import, live/default PMS DB writes,
actual PMS Postgres writes, production execution, production cutover,
invoice/payment/staging import, and Dental PMS live/main PMS status remain
unauthorised. Production readiness is not complete.

No secrets, DSNs, tokens, passwords, private URLs, exact private filesystem
paths, raw database dumps, backup contents, credentials, or patient data
belong in this document or in later proof records.

## Proposed Automated Backup Architecture

| Area | Proposed target |
| --- | --- |
| Source | Dental PMS production database and uploaded files/media if used |
| Destination | Google Workspace / owner-controlled online storage |
| Folder label | Dental PMS Production Backups |
| Method | Automated service account preferred |
| Fallback | Manual upload only if automation is unavailable |
| Schedule | Daily |
| Retention | Minimum 30 days |
| Restore target | Local non-live restore rehearsal environment |
| Evidence owners | Project owner / production operator |

This architecture is selected for implementation readiness only. It is not
proof that backups are configured, running, uploaded, retained, encrypted, or
restorable.

## Credential Handling

Credential handling must follow these rules:

- no credentials in Git;
- no credentials in docs;
- no tokens, DSNs, private URLs, private paths, or backup contents committed;
- credentials only in a secret manager, environment variables, or external
  configuration outside the repository;
- service-account setup requires a separate implementation slice;
- manual-upload fallback must still avoid committing private paths,
  credentials, backup names, raw dumps, or backup contents.

The later implementation slice must define how credentials are provisioned,
rotated, and revoked without exposing them in repository history, logs, PRs, or
documentation.

## Encryption Approach

The intended encryption posture is:

- Google Workspace storage encryption is assumed as a provider-level baseline;
- backup archive encryption is required if the repo helpers support it;
- if backup archive encryption is not supported, record that as a blocker or
  implementation task before claiming encrypted backup package support;
- no passphrases, keys, tokens, or private encryption configuration may be
  committed.

Encryption support is not proven by this readiness plan.

## Implementation Work Needed

A later separately authorised implementation slice should:

1. Inspect existing backup helper capability without exposing secrets or
   backup contents.
2. Confirm whether the current helpers support:
   - Google Workspace destination integration;
   - archive encryption;
   - daily scheduling;
   - retention of at least 30 days;
   - attachments/uploads backup if media are used.
3. Configure Google Workspace / owner-controlled online storage destination
   without committing credentials.
4. Configure daily schedule and retention.
5. Generate first backup evidence in a separately authorised execution slice.
6. Record backup timestamp, storage classification, and integrity/checksum if
   safe.
7. Run a non-live restore rehearsal in a separately authorised execution
   slice.
8. Record restore target classification and restore pass/fail evidence.
9. Record backup/restore sign-off before any cutover decision.

## Stop Conditions

Stop before implementation or execution if any of the following applies:

- no credential handling plan exists;
- no safe storage target is confirmed;
- secrets, DSNs, tokens, passwords, private URLs, exact private filesystem
  paths, raw database dumps, backup contents, or patient data would be exposed;
- patient data would be committed;
- a production database write is required;
- live/default PMS DB writes are requested;
- actual PMS Postgres writes are requested;
- restore target is not clearly non-live;
- live finance import is requested;
- production cutover is requested.

## Evidence Required Before Cutover

Before any cutover can be considered, the project still needs:

- backup automation configuration proof or accepted manual fallback proof;
- backup created timestamp;
- backup storage classification;
- daily schedule proof;
- minimum 30 days retention proof;
- archive encryption support proof or accepted blocker/task;
- backup integrity result or checksum if safe to disclose;
- local non-live restore rehearsal target classification;
- restore rehearsal pass/fail evidence;
- confirmation that no secrets, private paths, raw dumps, backup contents, or
  patient-level contents were committed;
- backup/restore owner sign-off;
- separate final go/no-go approval.

## Current Status

Backup automation implementation readiness is planned. Backup implementation,
backup execution, backup upload, backup integrity proof, restore rehearsal,
restore proof, production readiness, live finance import, and production
cutover remain incomplete and unauthorised.
