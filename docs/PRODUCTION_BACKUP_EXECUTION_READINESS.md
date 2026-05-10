# Production Backup Execution Readiness

Status date: 2026-05-10

Baseline:
`origin/master@3f5c9a64cec1da8c270be050a6cb8294310ce128`

This is a docs-only execution-readiness plan for the first rclone-based backup
upload evidence slice. It does not run backup commands. It does not run
restore commands. It does not access Google Workspace. It does not create or
inspect credentials. It does not connect to production, any PMS database,
local scratch SQLite, actual PMS Postgres, R4, or any real R4 artefact. It
does not use patient data, perform finance import, perform
invoice/payment/staging import, perform live/default PMS DB writes, perform
actual PMS Postgres writes, or perform production cutover.

R4 remains the live/main PMS. Dental PMS is not live/main PMS.
`finance_import_ready=false`. Live finance import, live/default PMS DB writes,
actual PMS Postgres writes, production execution, production cutover,
invoice/payment/staging import, and Dental PMS live/main PMS status remain
unauthorised. Production readiness is not complete.

This plan binds to the merged rclone scaffolding in
`docs/PRODUCTION_BACKUP_RCLONE_SCAFFOLDING.md` from PR #655, merged at
`3f5c9a64cec1da8c270be050a6cb8294310ce128`. That scaffolding records rclone
as the candidate Google Workspace/Drive upload mechanism and rclone `crypt` as
the candidate client-side encryption mechanism.

No secrets, tokens, DSNs, passwords, private URLs, exact private filesystem
paths, raw database dumps, backup contents, generated rclone config, OAuth
material, service-account material, crypt passwords, or patient data are
included.

## First Backup Execution Prerequisites

Before any first backup upload execution slice can start, all of the following
must be true and must remain outside Git:

- external rclone config exists outside the repository;
- Google Workspace/Drive remote is configured outside the repository;
- rclone `crypt` remote is configured outside the repository;
- service-account or OAuth credentials are stored outside Git;
- rclone `crypt` passwords and salts are stored outside Git;
- backup helper source archive path is confirmed outside the repository;
- backup destination is confirmed as Google Workspace folder label
  `Dental PMS Production Backups`;
- daily schedule target is confirmed;
- minimum 30-day retention target is confirmed;
- evidence collection plan excludes secrets, credentials, DSNs, private URLs,
  exact private filesystem paths, raw dumps, backup contents, and patient data.

This readiness plan does not verify any of those prerequisites. It only defines
the gate for a later explicit execution slice.

## First Backup Execution Evidence To Collect Later

A later separately authorised first-backup execution evidence record should
capture only non-sensitive evidence:

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

The evidence must not include raw database dumps, backup contents, exact
private filesystem paths, generated rclone config, OAuth material,
service-account material, crypt passwords, tokens, DSNs, or patient data.

## First Backup Stop Conditions

Stop before execution if any of the following applies:

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

## Restore Rehearsal Prerequisites

Non-live restore rehearsal remains a separate later slice. Before any restore
rehearsal starts:

- backup exists;
- safe non-live restore target exists;
- restore command shape is redacted;
- target is not a live/default PMS database;
- target is not actual production PMS Postgres;
- evidence plan excludes patient data, raw dumps, backup contents, private
  paths, credentials, generated rclone config, and secrets;
- no patient data will be committed to docs or Git.

Restore proof is required before production cutover can be considered.

## Required Sequence

The safe sequence remains:

1. Confirm prerequisite evidence without committing sensitive data.
2. Separately authorise the first backup upload execution slice.
3. Run first backup upload only in that later slice.
4. Record redacted first-backup evidence.
5. Separately authorise non-live restore rehearsal.
6. Record non-live restore proof.
7. Record backup/restore sign-off.
8. Only then consider any production go/no-go planning.

## Current Status

Backup execution readiness is planned but not complete. First backup upload,
encryption proof, backup timestamp evidence, minimum 30-day retention proof,
non-live restore rehearsal, restore proof, backup/restore sign-off, live
finance import, and production cutover remain blocked.
