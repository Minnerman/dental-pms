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
| Guarded finance/import process available | yes |
| Opening-balance/live finance import execution readiness | ready |
| Invoice/payment/staging import execution readiness | blocked |
| finance_import_ready | false |

Reason classification: repo now includes a classification-only guarded
finance/import execution preflight path for opening-balance import readiness.
It defaults to dry-run/no-write, requires an execution manifest, requires
explicit production target gating for live/default targets, requires an
explicit apply confirmation before any future write mode can be requested, and
does not connect to databases or run import in this readiness slice.

Blocker classification: invoice/payment/staging import remains unsupported by
this guarded path; import execution has not run; `finance_import_ready=false`
remains in force until a later explicit execution slice records safe execution
evidence.

Safety confirmations: no secrets exposed, no patient data exposed, no private
paths exposed, and no backup contents exposed.

## Added Guard Boundary

The added preflight command is
`python -m app.scripts.r4_guarded_finance_import_execution`. It records only
classification values and intentionally omits manifest paths, output paths,
DSNs, private URLs, logs, screenshots, configs, patient identifiers, database
output, and backup details from command output.

The current opening-balance guarded scratch apply path remains intentionally
non-production. The new path does not reinterpret that scratch apply command as
a live production writer. It adds a separate fail-closed gate that must be
satisfied before any later explicitly authorised import execution slice can be
considered.

The new guard model:

- defaults to dry-run/no-write;
- requires a manifest object and clear import category;
- supports opening-balance readiness only;
- blocks invoice, payment, and staging import categories;
- requires a target classification rather than a DSN in safe output;
- refuses live/default/production target classifications unless the explicit
  production execution gate is supplied;
- requires an explicit apply confirmation before future write mode can be
  requested;
- requires explicit no-secrets, no-patient-data, no-private-paths, and
  no-backup-contents confirmations;
- keeps `finance_import_ready=false`;
- does not connect to PMS databases or run import.

This guard model is useful for the next execution slice, but it must not be
reinterpreted as import execution evidence, finance import completion, or
authorisation for uncontrolled PMS database writes.

## Required Future Execution Slice

A future live-safe guarded finance/import execution slice must still be
separate and explicit. It must provide all of the following before any
execution:

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

Guarded opening-balance finance/import execution readiness is now available as
a repo-only classification preflight path, but finance/import execution has
not run. Invoice/payment/staging import execution remains blocked. No finance
import, opening-balance import, invoice import, payment import, staging import,
patient data import, R4 access, PMS DB connection, production access,
migration, backup, restore, rclone, rollback, deployment, or cutover action
was performed by this readiness record.
