# Production Backup Discovery And Setup Plan

Status date: 2026-05-10

Baseline:
`origin/master@22f22757befcbf5b62cab90c16596098fe2e66d7`

This is a docs-only backup discovery and setup planning slice. It records
repository-only discovery and the planned backup/restore setup path. It does
not execute backup, restore, production verification, production writes,
production cutover, live/default PMS DB writes, actual PMS Postgres writes,
PMS database connections, R4 access, real artefact access, validation/no-write,
guarded apply/write, finance import, or invoice/payment/staging import.

Codex inspected repository files and non-secret documentation only. No
production server was accessed. No PMS database was connected. No backup
command was run. No restore command was run. No Google Workspace access
occurred. No patient data was accessed. No secrets, DSNs, tokens, passwords,
private URLs, exact private filesystem paths, raw database dumps, or backup
contents are included in this record.

R4 remains the live/main PMS. Dental PMS is not live/main PMS.
`finance_import_ready=false`. Production writes, live finance import, and
production cutover remain unauthorised. Production cutover remains blocked
until current backup evidence and non-live restore proof are available,
accepted, and separately signed off.

## Discovery Scope

The repository-only inspection covered:

- backup and restore helper scripts under `ops/`;
- backup scheduler templates under `ops/systemd/`;
- `docs/OPS_BACKUPS.md`;
- `docs/BACKUP_RESTORE.md`;
- `docs/DEPLOY_RUNBOOK.md`;
- `docs/RELEASE_CHECKLIST.md`;
- `docs/OPERATIONS.md`;
- `docs/OPS_MONITORING.md`;
- production readiness tracker and backup/restore planning docs.

The inspection intentionally did not inspect production servers, production
backup storage, Google Workspace, database contents, raw dump files, private
paths, credentials, or patient data.

## Findings Classification

| Finding | Classification | Notes |
| --- | --- | --- |
| Backup configured and documented | Partially documented | Repo helpers and operator docs exist for database and attachments backups, and scheduler templates exist. Current production installation, current schedule, latest run, and backup integrity are not verified in this slice. |
| Backup partially documented | Yes | `docs/OPS_BACKUPS.md`, deploy/release docs, and ops helpers describe backup scope, run expectations, retention count controls, and success criteria. |
| Backup not found | Current production proof not found | Safe repo evidence does not prove that Dental PMS production backups are currently configured, running, retained, or stored off-host. |
| Restore documented | Yes, for procedure only | Repo docs and helpers describe restore paths, but restore is destructive unless targeted to a safe non-live environment. No restore command was run. |
| Restore not found | Current proof not found | Safe repo evidence does not provide current non-live restore rehearsal proof for this production readiness track. |
| Secrets risk | Present if raw outputs are copied | Backup helpers can emit paths and artefact names. Later evidence must redact private paths, credentials, raw dump names, and backup contents. |
| Production readiness blocker | Yes | Backup/restore proof is absent, latest safe backup timestamp is unavailable, and restore rehearsal has not been performed. |

Historical docs mention earlier backup and restore drills and backup hardening.
Those are useful context but are not treated here as current production
readiness proof for Dental PMS go-live. Current production readiness still
requires fresh non-sensitive backup evidence and non-live restore proof.

## Non-Sensitive Evidence Found

Repository evidence confirms that backup and restore tooling exists:

- combined database-plus-attachments backup helper;
- database logical backup helper;
- attachments backup helper;
- database restore helper;
- daily scheduler templates for backups;
- operator backup documentation;
- release checklist backup gate;
- monitoring notes that include backup checks.

This evidence is not complete enough for production readiness because it does
not prove the current production backup schedule, storage implementation,
latest safe backup timestamp, off-host copy, integrity check, or restore
rehearsal result.

The repo backup retention helper currently uses a retained-file-count setting.
The recommended production policy below requires at least 30 days of retained
backups, so a later implementation/evidence slice must prove the configured
retention meets that target.

## Owner-Preferred Candidate Backup Target

Owner-preferred candidate storage:
Google Workspace / owner-controlled online storage.

This is recorded only as a candidate backup storage option. It is not yet
implemented or verified for Dental PMS by this slice. This slice did not
access Google Workspace, upload backups, download backups, create backups, or
inspect backup contents.

Any future Google Workspace or owner-controlled online-storage implementation
must be performed in a separate authorised implementation/evidence slice. It
must not commit credentials, tokens, private paths, backup artefacts, raw dump
contents, or patient data.

## Recommended Target Policy

| Area | Target policy |
| --- | --- |
| Database backups | Daily production database backup. |
| Uploaded files/media | Include attachments/uploads if Dental PMS uses them. |
| Retention | Minimum 30 days. |
| Storage | Access-controlled owner-controlled online storage, candidate Google Workspace/Drive, plus provider/server snapshot if available. |
| Restore rehearsal | Required before production cutover. |
| Restore target | Non-live restore test environment only. |
| Restore evidence PR | Required before go-live. |
| Production cutover | Blocked until backup and restore proof pass. |

## Setup Plan

The backup scope for production readiness should cover:

- production database;
- uploaded files/media if used;
- deployment/config documentation without secrets;
- code, which is already covered by GitHub but is not sufficient alone for
  operational recovery.

Planned ownership and targets:

| Item | Target |
| --- | --- |
| Backup owner | Project owner / production operator |
| Backup schedule target | Daily |
| Retention target | Minimum 30 days |
| Storage target | Access-controlled owner-controlled online storage, candidate Google Workspace/Drive, pending implementation proof |
| Restore rehearsal target | Non-live restore test only |
| Restore rehearsal requirement | Must prove restore works before production cutover |

## Blockers

The current blockers are:

- current production backup evidence is unknown or incomplete;
- latest safe backup timestamp is unavailable;
- current production backup storage implementation is not verified;
- off-host or owner-controlled online-storage copy is not verified;
- current retention policy evidence is not verified;
- restore rehearsal has not been performed;
- backup/restore sign-off has not been recorded.

Live import and production cutover remain blocked while these items are open.

## Next Execution Slices

The next safe execution slices are:

1. Backup implementation or configuration evidence.
2. Backup timestamp evidence.
3. Non-live restore rehearsal evidence.
4. Backup/restore sign-off.

Each later slice must keep evidence redacted and non-sensitive unless the owner
explicitly authorises a narrower implementation step. No later evidence should
include secrets, credentials, DSNs, exact private paths, raw database dumps,
backup contents, or patient-level contents.

## Non-Authorisation

This plan does not authorise:

- live/default PMS DB writes;
- actual PMS Postgres writes;
- production execution;
- production cutover;
- live finance import;
- invoice/payment/staging import;
- Dental PMS becoming the live/main PMS;
- backup execution;
- restore execution;
- Google Workspace access.
