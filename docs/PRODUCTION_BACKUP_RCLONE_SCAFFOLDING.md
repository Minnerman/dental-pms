# Production Backup Rclone Scaffolding

Status date: 2026-05-10

Baseline:
`origin/master@2543716f57ed2848b5560b6d18bd03e18340ed40`

This is non-secret scaffolding for a candidate rclone-based Google
Workspace/Drive backup upload and encryption integration. This PR does not run
backups. It does not run restores. It does not access Google Workspace. It
does not create or inspect credentials. It does not connect to production. It
does not connect to any PMS database, local scratch SQLite, actual PMS
Postgres, R4, or any real R4 artefact. It does not use patient data, perform
finance import, perform invoice/payment/staging import, perform live/default
PMS DB writes, perform actual PMS Postgres writes, or perform production
cutover.

R4 remains the live/main PMS. Dental PMS is not live/main PMS.
`finance_import_ready=false`. Live finance import, live/default PMS DB writes,
actual PMS Postgres writes, production execution, production cutover,
invoice/payment/staging import, and Dental PMS live/main PMS status remain
unauthorised. Production readiness is not complete.

No secrets, tokens, DSNs, passwords, private URLs, exact private filesystem
paths, backup contents, raw database dumps, generated rclone config, OAuth
material, service-account material, crypt passwords, or patient data are
included.

## Candidate Mechanism

The candidate remote-upload mechanism is rclone targeting Google
Workspace/Drive. The candidate client-side encryption mechanism is rclone
`crypt`, wrapping the Google Workspace/Drive remote.

This scaffolding uses placeholders only:

- `RCLONE_CONFIG=/path/outside/repo/rclone.conf`
- `RCLONE_REMOTE_NAME=dental_pms_gworkspace`
- `RCLONE_CRYPT_REMOTE_NAME=dental_pms_gworkspace_crypt`
- `BACKUP_FOLDER_LABEL="Dental PMS Production Backups"`
- `BACKUP_SOURCE_ARCHIVE=/path/outside/repo/latest-backup.tar`
- `BACKUP_DESTINATION="dental_pms_gworkspace_crypt:Dental PMS Production Backups/"`
- `BACKUP_RETENTION_DAYS=30`
- `BACKUP_SCHEDULE="daily"`

The placeholder values are not proof that rclone is installed, configured,
authenticated, encrypted, uploaded, retained, or restorable.

## Template Files

Non-secret templates are provided at:

- `ops/templates/rclone-google-workspace-backup.env.example`
- `ops/templates/rclone-google-workspace-backup-command.example`
- `ops/templates/rclone-google-workspace-backup-schedule.example`

These are examples only. They are not production configuration. They must not
be copied into place with real credentials inside Git. Generated rclone config
must remain outside the repository.

## Credential Handling

Credential handling must follow these rules:

- rclone config lives outside the repository;
- service-account or OAuth credentials live outside the repository;
- rclone `crypt` passwords and salts live outside the repository;
- no generated rclone config may be committed;
- no credentials, tokens, DSNs, private URLs, private paths, raw dumps, backup
  contents, or patient data may be committed;
- credential setup requires a later explicit owner/operator implementation
  slice.

The owner-selected preference is automated service-account operation, with
manual upload only as a fallback if automation is unavailable.

## Encryption Approach

The intended encryption posture is:

1. Google Workspace/Drive provider-level storage encryption is treated as the
   storage baseline.
2. rclone `crypt` is the candidate client-side encryption layer.
3. The `crypt` remote should wrap the Google Workspace/Drive remote.
4. `crypt` credentials must be stored outside Git.
5. Encryption proof remains pending until a later authorised execution evidence
   slice verifies encrypted upload behaviour without exposing secrets.

This PR does not prove encryption support. It only records a candidate
approach.

## Backup Flow

The intended future flow is:

1. Existing local backup helpers create local database and uploaded files/media
   backup artefacts.
2. A later approved implementation slice selects or prepares the archive source
   represented by `BACKUP_SOURCE_ARCHIVE`.
3. rclone uploads through the `crypt` remote to owner-controlled Google
   Workspace storage labelled `Dental PMS Production Backups`.
4. The schedule target is daily.
5. The retention target is minimum 30 days.
6. A later execution evidence slice records redacted upload status, timestamp,
   storage classification, integrity/checksum if safe, and retention evidence.

This PR does not run that flow.

## Restore Flow

The intended future restore proof flow is:

1. Download/decrypt only into the approved local non-live restore rehearsal
   environment.
2. Do not restore into production.
3. Do not commit backup contents, raw dumps, private paths, credentials, or
   patient data.
4. Record redacted restore evidence and pass/fail status.
5. Require restore proof before any production cutover can be considered.

This PR does not run restore or download commands.

## Blockers

The following remain blocked:

- rclone credentials are not configured;
- Google Workspace access is not tested;
- rclone `crypt` remote is not proven;
- backup upload has not been executed;
- archive encryption has not been proven;
- latest safe backup timestamp is not recorded;
- minimum 30-day retention evidence is not recorded;
- non-live restore rehearsal is not performed;
- backup/restore sign-off is not recorded;
- production cutover and live finance import remain blocked.

## Next Execution Slice

A later explicit owner-approved slice may:

1. Configure rclone credentials outside Git.
2. Configure a Google Workspace/Drive remote outside Git.
3. Configure a rclone `crypt` remote outside Git.
4. Run the first backup upload.
5. Record redacted evidence without secrets, private paths, raw dumps, backup
   contents, or patient data.
6. Run a non-live restore rehearsal.
7. Record restore proof and backup/restore sign-off.

Until that happens, backup automation implementation remains incomplete.
