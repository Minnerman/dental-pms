# Production Backup Rclone Credential Setup And First Backup Request

Status date: 2026-05-10

Baseline:
`origin/master@1ad024b823142d3fa7202ad97e565312ba2c0918`

This is a docs-only credential/setup and first-backup evidence request. It
does not create credentials. It does not inspect credentials. It does not
access Google Workspace. It does not run backup commands. It does not run
restore commands. It does not connect to production, any PMS database, local
scratch SQLite, actual PMS Postgres, R4, or any real R4 artefact. It does not
use patient data, perform finance import, perform invoice/payment/staging
import, perform live/default PMS DB writes, perform actual PMS Postgres writes,
or perform production cutover.

R4 remains the live/main PMS. Dental PMS is not live/main PMS.
`finance_import_ready=false`. Live finance import, live/default PMS DB writes,
actual PMS Postgres writes, production execution, production cutover,
invoice/payment/staging import, and Dental PMS live/main PMS status remain
unauthorised. Production readiness is not complete.

This request binds to the merged rclone runner scaffold in
`docs/PRODUCTION_BACKUP_RCLONE_RUNNER.md` and `ops/backup_rclone_upload.sh`.
The runner is non-secret scaffolding only. First backup execution remains a
later explicit owner/operator execution slice.

No secrets, tokens, DSNs, passwords, private URLs, exact private filesystem
paths, raw database dumps, backup contents, generated rclone config, OAuth
material, service-account material, crypt passwords, or patient data should be
included in any response to this request.

## Outside-Git Setup Steps For Owner/Operator

The owner/operator should complete these steps outside Git and outside this
documentation request:

1. Install or confirm rclone on the intended execution host.
2. Configure the Google Workspace/Drive remote outside the repository.
3. Configure the rclone `crypt` remote outside the repository.
4. Store the rclone config outside the repository.
5. Store service-account or OAuth credentials outside the repository.
6. Store rclone `crypt` passwords and salts outside the repository.
7. Confirm the backup destination folder label:
   `Dental PMS Production Backups`.
8. Set `BACKUP_UPLOAD_CONFIRM=UPLOAD_TO_OWNER_CONTROLLED_STORAGE` only during
   a separately authorised first-backup execution slice.
9. Keep all credentials, generated config, tokens, DSNs, private URLs, exact
   private filesystem paths, raw dumps, backup contents, and patient data out
   of Git and docs.

This document does not verify those steps. It only defines the non-sensitive
evidence to request after the setup is complete.

## Credential Setup Evidence To Provide Later

After setup, provide only non-sensitive yes/no or classification evidence:

- rclone installed: yes/no;
- Google Workspace/Drive remote configured: yes/no;
- rclone `crypt` remote configured: yes/no;
- rclone config stored outside Git: yes/no;
- service-account or OAuth credentials stored outside Git: yes/no;
- crypt passwords and salts stored outside Git: yes/no;
- backup destination classification;
- folder label: `Dental PMS Production Backups`;
- no secrets exposed confirmation;
- no private paths exposed confirmation;
- no backup contents exposed confirmation;
- no patient data exposed or committed confirmation.

Do not provide generated rclone config, credential material, private URLs,
exact private paths, raw dumps, backup contents, checksums of sensitive backup
contents, or patient-level data.

## First Backup Execution Evidence Request

In a later separately authorised first-backup execution slice, collect only
non-sensitive evidence:

- timestamp;
- actor/owner role;
- redacted command shape;
- source archive classification;
- destination classification;
- upload result pass/fail;
- rclone `crypt` / encryption confirmation without exposing credentials,
  passwords, salts, generated config, private paths, or backup contents;
- backup size if safe to disclose;
- checksum if safe and non-sensitive;
- confirmation that no patient data was committed;
- confirmation that no secrets were committed.

The later execution evidence should confirm whether
`BACKUP_UPLOAD_CONFIRM=UPLOAD_TO_OWNER_CONTROLLED_STORAGE` was used, but must
not include secrets or exact private paths.

## Stop Conditions

Stop before setup evidence recording or first-backup execution if any of the
following applies:

- rclone config is missing;
- Google Workspace/Drive remote is missing;
- rclone `crypt` remote is missing;
- credentials, generated config, crypt passwords, tokens, DSNs, private URLs,
  exact private filesystem paths, raw dumps, backup contents, or patient data
  would be exposed;
- patient data would be committed;
- production database write is requested;
- live/default PMS DB write is requested;
- actual PMS Postgres write is requested;
- backup archive path is unsafe to disclose;
- Google Workspace access fails;
- backup upload result cannot be recorded without sensitive detail;
- live finance import or production cutover is requested.

## Restore Rehearsal Boundary

Restore rehearsal remains separate. Before any restore proof slice:

- a backup must exist;
- a safe non-live restore target must be confirmed;
- restore command shape must be redacted;
- target must not be a live/default PMS database;
- target must not be actual production PMS Postgres;
- no patient data, raw dumps, backup contents, private paths, generated
  config, credentials, or secrets may be committed to docs or Git.

Restore proof is required before production cutover can be considered.

## Current Status

Credential/setup evidence is requested but not complete. First backup upload,
encryption proof, backup timestamp evidence, minimum 30-day retention proof,
non-live restore rehearsal, restore proof, backup/restore sign-off, live
finance import, and production cutover remain blocked.
