# Production Backup Automation Implementation Gap

Status date: 2026-05-10

Baseline:
`origin/master@0e5831397caac5a163e7a01e2ee915e05fb4da52`

This is a repository-only backup automation implementation gap record. It
inspected existing backup helpers, restore helpers, scheduler templates, and
non-secret documentation only. It did not run backup commands, run restore
commands, access Google Workspace, create or inspect credentials, connect to a
production server, connect to any PMS database, access R4, use patient data,
perform finance import, perform invoice/payment/staging import, or perform
production cutover.

No secrets, DSNs, tokens, passwords, private URLs, exact private filesystem
paths, raw database dumps, backup contents, credentials, or patient data are
included.

R4 remains the live/main PMS. Dental PMS is not live/main PMS.
`finance_import_ready=false`. Live finance import, live/default PMS DB writes,
actual PMS Postgres writes, production execution, production cutover,
invoice/payment/staging import, and Dental PMS live/main PMS status remain
unauthorised. Production readiness is not complete.

## Inspection Scope

The inspection covered:

- local backup orchestration helper;
- logical database backup helper;
- uploaded files/media backup helper;
- legacy database backup helper;
- volume backup helper;
- database restore helper;
- volume restore helper;
- systemd backup service and timer templates;
- backup and restore operator docs;
- production readiness backup planning docs.

The inspection did not execute any helper. It did not inspect runtime
environment files, credentials, backup storage, backup artefacts, production
servers, Google Workspace, PMS databases, or patient data.

## Capability Findings

| Capability | Finding | Readiness impact |
| --- | --- | --- |
| Database dump creation | Found local logical database backup helper using a PostgreSQL dump inside the compose database service. | Local helper exists, but no current production execution evidence is recorded. |
| File/media backup | Found uploaded files/media backup helper with an explicit source override and container mount fallback. | Local helper exists, but no current production execution evidence is recorded. |
| Archive creation | Found compressed database and uploaded files/media artefact creation. | Local archive creation exists, but backup package encryption is not proven. |
| Archive encryption | Not found in the inspected helper scripts. | Blocker until implemented or explicitly accepted as a documented gap. |
| Google Workspace upload | Not found in the inspected helper scripts. | Blocker for the owner-selected automated Google Workspace / owner-controlled online storage target. |
| Generic remote upload | Not found in the inspected helper scripts. | Blocker until an upload integration is selected and implemented. |
| Scheduling template | Found daily systemd timer template and backup service template. | Template exists, but current production installation and schedule evidence are absent. |
| Retention control | Found count-based retention control. | Configurable retention exists, but production proof of minimum 30 days is absent. |
| Restore helper/procedure | Found database restore helper and documented restore procedure. | Restore procedure exists, but non-live restore rehearsal proof is absent. |

## Implementation Decision

The repo has suitable local backup and restore foundations, but it does not
currently show enough support for the owner-selected automation target because
Google Workspace upload support and archive encryption support were not found.

For that reason, this slice records an implementation gap instead of adding
backup automation scaffolding that would assume an unproven upload or
encryption path.

## Required Next Implementation Task

A later separately authorised implementation slice should add or select a
non-secret remote upload and archive encryption approach without committing
credentials or backup contents.

Minimum implementation decisions required:

1. Select Google Workspace upload mechanism.
   - Preferred method: automated service account.
   - Fallback: manual upload only if automation is unavailable.
   - Credentials must stay outside Git and outside docs.
2. Add or configure archive encryption support.
   - Required before claiming encrypted backup package support.
   - If unsupported, record the exact blocker and do not claim completion.
3. Align retention with the owner target.
   - Target: daily backups, minimum 30 days.
   - Production evidence must later prove the effective setting.
4. Record first backup execution evidence in a separate execution slice.
   - Evidence must be redacted and non-sensitive.
   - Evidence must not include private paths, raw dumps, backup contents, or
     patient data.
5. Run non-live restore rehearsal in a separate execution slice.
   - Restore target: local non-live restore rehearsal environment.
   - Restore proof must be recorded before cutover can be considered.

## Stop Conditions

Stop before implementation or execution if any of these applies:

- no safe Google Workspace or owner-controlled storage target is confirmed;
- no credential handling plan exists;
- credentials, tokens, DSNs, private URLs, exact private filesystem paths, raw
  database dumps, backup contents, or patient data would be exposed;
- archive encryption is required but unsupported and not explicitly tracked as
  a blocker;
- a production database write is required;
- a backup or restore command would run without a separate explicit execution
  approval;
- the restore target is not clearly non-live;
- live finance import or production cutover is requested.

## Evidence Still Needed Before Cutover

Before production cutover can be considered, the project still needs:

- remote backup storage implementation proof;
- archive encryption support proof or accepted blocker/task;
- credential handling proof without exposing credentials;
- first backup timestamp;
- backup integrity or checksum evidence if safe to disclose;
- production schedule evidence proving daily execution;
- retention evidence proving at least 30 days;
- local non-live restore rehearsal pass/fail evidence;
- backup/restore owner sign-off;
- separate final go/no-go approval.

## Current Status

Backup automation implementation remains blocked by missing Google Workspace
upload support, missing archive encryption support, absent production execution
evidence, absent latest safe backup timestamp, and absent non-live restore
proof.

Live finance import and production cutover remain blocked.
