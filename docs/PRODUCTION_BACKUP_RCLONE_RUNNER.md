# Production Backup Rclone Runner

Status date: 2026-05-10

Baseline:
`origin/master@044ec5ed3afd395781e496078d8bc6bcdd7eb663`

This PR adds non-secret runner scaffolding only. It does not execute backup
uploads, run restore commands, access Google Workspace, create or inspect
credentials, connect to production, connect to any PMS database, access R4,
use patient data, perform finance import, perform invoice/payment/staging
import, perform live/default PMS DB writes, perform actual PMS Postgres writes,
or perform production cutover.

R4 remains the live/main PMS. Dental PMS is not live/main PMS.
`finance_import_ready=false`. Live finance import, live/default PMS DB writes,
actual PMS Postgres writes, production execution, production cutover,
invoice/payment/staging import, and Dental PMS live/main PMS status remain
unauthorised. Production readiness is not complete.

No secrets, tokens, DSNs, passwords, private URLs, exact private filesystem
paths, raw database dumps, backup contents, generated rclone config, OAuth
material, service-account material, crypt passwords, or patient data are
included.

## Runner Scope

The runner scaffold is:

- `ops/backup_rclone_upload.sh`

It is an env-driven wrapper around the already documented candidate rclone /
rclone `crypt` path. It is not production configuration and is not proof that
backup upload, archive encryption, retention, or restore works.

The runner refuses to proceed unless these environment variables are set:

- `RCLONE_CONFIG`
- `BACKUP_SOURCE_ARCHIVE`
- `BACKUP_DESTINATION`

The runner is dry-run by default. It prints only a redacted command shape and
refuses real upload unless this explicit confirmation is supplied:

- `BACKUP_UPLOAD_CONFIRM=UPLOAD_TO_OWNER_CONTROLLED_STORAGE`

When confirmation is not supplied, the runner exits before checking local file
existence or calling rclone. When confirmation is supplied, the runner checks
for rclone, checks the external config/archive files without printing their
paths, and then calls:

```sh
rclone copy "$BACKUP_SOURCE_ARCHIVE" "$BACKUP_DESTINATION" --config "$RCLONE_CONFIG"
```

Do not run the runner without a separate explicit owner/operator execution
approval.

## Setup Prerequisites

Before a later first-backup execution slice, the operator must confirm:

- rclone is installed by the operator;
- rclone config exists outside the repository;
- Google Workspace/Drive remote is configured outside the repository;
- rclone `crypt` remote is configured outside the repository;
- service-account or OAuth credentials are stored outside the repository;
- rclone `crypt` passwords and salts are stored outside the repository;
- source archive location is confirmed outside the repository;
- destination is owner-controlled Google Workspace storage labelled
  `Dental PMS Production Backups`;
- daily schedule target remains selected;
- minimum 30-day retention target remains selected;
- evidence collection excludes secrets, private paths, raw dumps, backup
  contents, generated config, and patient data.

## First Backup Evidence Expectations

A later separately authorised first-backup execution record should capture only
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

## Stop Conditions

Stop before any runner execution if any of the following applies:

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
- restore target is not clearly non-live;
- live finance import or production cutover is requested.

## Remaining Gates

First backup execution remains a later explicit slice. Non-live restore
rehearsal remains a later explicit slice. Production cutover remains blocked
until backup execution evidence, non-live restore proof, backup/restore
sign-off, and final owner go/no-go approval are recorded.
