# Production Guarded Finance Import Execution Readiness

Status date: 2026-05-10

Baseline:
`origin/master@f23655b02cabb91ea834e215f35f5f1b9f55dcec`

## Scope

This is a repo-only readiness path and blocker record for live finance/import
execution. It does not run import, migration, backup, restore, rclone,
deployment, rollback, or cutover commands. It does not access R4, production,
PMS databases, scratch SQLite, patient data, real artefacts, credentials,
private paths, private URLs, configs, logs, screenshots, raw dumps, database
output, or backup contents.

Dental PMS production cutover status is recorded separately. Dental PMS is
recorded as live/main PMS, and R4 remains available for rollback.
`finance_import_ready=false` remains in force.

## Current Classification

| Gate | Status |
| --- | --- |
| Guarded finance/import process available | no |
| Opening-balance/live finance import execution readiness | blocked |
| Invoice/payment/staging import execution readiness | blocked |

Reason classification: existing repository finance apply tooling is
scratch/test guarded only, refuses default/live-looking PMS database targets,
writes only manifest-scoped patient ledger adjustment rows, and refuses
invoice, payment, staging, balance-mutation, or other finance record intents.

Blocker classification: live-safe guarded finance/import execution process is
missing; opening-balance/live finance import and invoice/payment/staging import
execution remain blocked.

Safety confirmations: no secrets exposed, no patient data exposed, no private
paths exposed, and no backup contents exposed.

## Existing Guard Boundary

The current opening-balance guarded apply path is intentionally not a live
production import path. It requires a scratch/test target classification,
requires explicit apply and confirmation gates for scratch writes, refuses
default/live-looking targets, and keeps `finance_import_ready=false`.

The current guard model is useful evidence for a future live-safe design, but
it must not be reinterpreted as authorising live/default PMS writes or actual
production PMS Postgres writes.

## Required Future Live-Safe Path

A future live-safe guarded finance/import execution path must be a separate
explicit slice and must provide all of the following before any execution:

- explicit owner/operator execution instruction for the specific import
  category;
- confirmed backup, retention, restore, and rollback status still green;
- production target classification that is safe to record without private
  details;
- dry-run/preflight classification that does not expose patient data,
  credentials, private paths, logs, screenshots, or database output;
- exact import category selected: opening-balance, invoice, payment, or
  staging;
- fail-closed confirmation gates for the selected category;
- idempotency and duplicate handling classification;
- rollback and post-import verification classification;
- redacted evidence-only output format.

## Stop Conditions

Stop before any finance/import execution if:

- R4 access is required;
- production or PMS database access would expose sensitive detail;
- patient data, patient-level identifiers, raw dumps, database output, logs,
  screenshots, credentials, private paths, private URLs, configs, or backup
  contents would be exposed;
- the selected import category is ambiguous;
- the process would bypass fail-closed confirmation gates;
- the process would perform uncontrolled PMS DB writes;
- rollback is unavailable;
- `finance_import_ready=false` would be changed without a live-safe guarded
  process and explicit execution evidence.

## Current Result

Finance/import execution remains blocked. No finance import, opening-balance
import, invoice import, payment import, staging import, patient data import,
R4 access, PMS DB connection, production access, migration, backup, restore,
rclone, rollback, or cutover action was performed by this readiness record.
