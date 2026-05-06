# R4 Finance Opening-Balance Guarded Apply Design

Status date: 2026-05-06

Baseline: `master@78e02a0a53b13c3d8db9e24863398e857ef50581`

Safety: this document records the guarded scratch-only apply design and the
first CLI prototype. The prototype defaults to validation/no-write mode and can
write only manifest-scoped `PatientLedgerEntry` adjustment rows when an explicit
scratch/test target, `--apply`, `--confirm SCRATCH_OPENING_BALANCE_APPLY`, and
an audit actor ID are supplied. It does not authorise finance import, finance
staging models, R4 writes, invoice creation, payment creation, live/default PMS
writes, or live cutover.

R4 SQL Server remains strictly read-only / SELECT-only. This design does not
require live R4 access because it uses preserved evidence artefacts.

## Inputs

This design uses:

- `docs/STATUS.md`
- `docs/R4_MIGRATION_READINESS.md`
- `docs/r4/R4_FINANCE_SOURCE_DISCOVERY.md`
- `docs/r4/R4_FINANCE_SIGN_CANCELLATION_ALLOCATION_POLICY.md`
- `docs/r4/R4_FINANCE_REFUND_ALLOCATION_CHARGE_REF_DECISION.md`
- `docs/r4/R4_FINANCE_INVOICE_CHARGE_REF_SOURCE_DECISION.md`
- `docs/r4/R4_FINANCE_OPENING_BALANCE_SNAPSHOT_DESIGN.md`
- `docs/r4/R4_FINANCE_OPENING_BALANCE_SCRATCH_DRYRUN_DESIGN.md`
- `backend/app/services/r4_import/opening_balance_snapshot_plan.py`
- `backend/app/services/r4_import/opening_balance_snapshot_dry_run.py`
- `backend/app/services/r4_import/opening_balance_snapshot_apply_plan.py`
- `backend/app/services/r4_import/opening_balance_snapshot_guarded_apply.py`
- `backend/app/scripts/r4_opening_balance_snapshot_dry_run.py`
- `backend/app/scripts/r4_opening_balance_guarded_scratch_apply.py`
- `backend/app/models/ledger.py`
- `backend/app/models/invoice.py`
- `backend/app/routers/patients.py`
- `backend/app/routers/invoices.py`
- `/home/amir/dental-pms-opening-balance-live-proof/.run/opening_balance_reconciliation_20260504_083558/opening_balance_reconciliation.json`
- `/home/amir/dental-pms-opening-balance-dryrun-execution/.run/opening_balance_snapshot_dryrun_mapping_20260505_082233/opening_balance_snapshot_dryrun_report.json`
- `/home/amir/dental-pms-opening-balance-dryrun-execution/.run/opening_balance_snapshot_dryrun_mapping_20260505_082233/scratch_patient_mapping.json`

No live R4 query was run for this design. No PMS DB access or finance record
write occurred.

## Current Evidence

The live SELECT-only opening-balance proof recorded:

- `PatientStats` rows: `17012`
- non-zero balances: `1018`
- component checks: `0` mismatches
- raw positive balances: `291`
- raw negative balances: `727`
- zero balances: `15994`
- aged debt rows: `126`
- balance without aged debt: `892`
- R4 access: SELECT-only
- PMS DB writes: none
- finance records created or changed: none

The scratch-only dry-run/report execution recorded:

- source rows: `17012`
- non-zero opening-balance candidates: `1018`
- scratch mapping rows: `17012`
- non-zero mapping coverage: `1018/1018`
- unmapped non-zero candidates: `0`
- dry-run exit: `0`
- `dry_run=true`
- `import_ready=false`
- `finance_import_ready=false`
- manifest `no_write=true`
- manifest `apply_mode=false`
- eligible rows: `1018`
- no-op zero rows: `15820`
- component mismatches: `174`
- positive rows: `291`
- negative rows: `727`
- zero-sign rows: `15994`
- total balance: `-131742.13`
- source drift: `-400.00` versus the earlier live proof for total `Balance`,
  `TreatmentBalance`, and `PrivateBalance`
- scratch finance counts stayed `invoices=0`, `payments=0`, and
  `patient_ledger_entries=0`
- default/main `dental_pms` was not touched

The `174` component mismatches were zero-balance rows with missing/null
component fields. They remain no-write/manual-review evidence.

The scratch stack `dentalpms-obmap-20260505-082233` has been cleaned up and the
artefacts remain preserved.

## Apply Purpose and Scope

A future guarded scratch-only opening-balance apply prototype should prove that
the already planned non-zero `PatientStats` snapshot rows can create exactly one
manifest-scoped opening-balance representation per eligible mapped PMS patient
inside an isolated scratch database.

It must prove operational mechanics only:

- target DB refusal for default/live PMS;
- dry-run artefact acceptance;
- manifest construction;
- row-level write planning;
- write counts and refusal counts;
- idempotency on rerun;
- manifest-scoped rollback, if rollback is included in the same prototype.

It must stay scratch-only because an opening balance changes patient account
debt and immediately affects patient balances, outstanding reports, and finance
reporting. The existing evidence proves planning and mapping, not operator
acceptance, rollback, double-counting safety, or live cutover readiness.

This is not historical invoice import. No explicit R4 patient invoice or
statement source is proven, allocation charge refs are absent, and
`PatientStats` is a balance snapshot rather than invoice/payment chronology.

This is not normal payment import. It must not create `Payment` rows, apply
payments to invoices, infer payment methods, or use `vwPayments`/`Adjustments`
cash-event rows.

`finance_import_ready` remains `false` until a scratch apply proof passes and
the remaining live/default blockers are resolved. Even a passing scratch apply
prototype would prove only an opening-balance mechanism, not full finance
import.

## Write Representation Decision

Selected representation: existing `PatientLedgerEntry` rows with
`entry_type=adjustment`.

Why this is the safest current representation:

- PMS patient balances and outstanding reports are already ledger-derived from
  `PatientLedgerEntry.amount_pence`.
- The ledger already supports `adjustment` rows independently of invoices.
- `Payment` rows require an `Invoice`, so payment rows are unsuitable for an
  opening balance snapshot.
- Creating `Invoice` or `InvoiceLine` rows would imply historical invoice truth
  that R4 evidence does not prove.
- No dedicated opening-balance audit/import-run model exists today, and adding
  one would be finance staging/import-model work outside this design slice.

Future scratch apply rows should use:

- `patient_id`: mapped PMS patient ID from the accepted mapping artefact;
- `entry_type`: `LedgerEntryType.adjustment`;
- `amount_pence`: exact pence value from combined `PatientStats.Balance`;
- `method`: `NULL`;
- `related_invoice_id`: `NULL`;
- `reference`: strict manifest marker, for example
  `R4OB:<manifest_id>:<PatientCode>`;
- `note`: bounded metadata containing the source name, source `PatientCode`,
  raw `Balance`, component fields, aged-debt fields, raw sign, proof direction,
  dry-run report hash, mapping artefact hash, source artefact hash, and
  manifest ID;
- `created_by_user_id`: explicit scratch operator/admin actor ID;
- `updated_by_user_id`: same actor ID at creation time.

The manifest ID should be short and stable enough for the existing
`reference` length, for example `ob-YYYYMMDDHHMMSS-<12hex>`. The full manifest
must be stored in the apply artefacts, not squeezed into the ledger row.

The future prototype may also write audit log entries if it uses existing audit
infrastructure, but audit rows must be derived from the exact same manifest and
must not be the primary rollback marker. The primary rollback marker is the
ledger `reference` prefix plus manifest ID.

This representation must not create:

- `Invoice`
- `InvoiceLine`
- `Payment`
- payment allocations
- finance staging rows
- dedicated opening-balance import tables

## Amount and Sign Policy

Financial effect uses only combined `PatientStats.Balance`.

Raw fields preserved as metadata:

- `Balance`
- `TreatmentBalance`
- `SundriesBalance`
- `NHSBalance`
- `PrivateBalance`
- `DPBBalance`
- aged-debt fields
- raw sign
- proof-only PMS direction
- source artefact path

Sign mapping:

- positive raw `Balance` maps to positive `amount_pence` and increases debt;
- negative raw `Balance` maps to negative `amount_pence` and decreases debt or
  represents credit;
- zero raw `Balance` creates no row;
- no blind sign inversion is allowed.

Exact pence conversion is required. Any amount that cannot be represented
exactly in pence must be refused.

Component checks must pass for every would-write row. A component mismatch
among would-write rows blocks the apply. The known `174` mismatches are
zero-balance rows and should remain manual-review/no-write evidence.

Source drift must be reported in the apply manifest. The current dry-run source
drift of `-400.00` against the earlier live proof is known evidence, not an
automatic approval. Any future source extraction with unapproved drift outside
the declared tolerance should fail closed or require a new no-write dry-run
report before apply.

## Eligibility and Refusal Policy

Eligible rows:

- source is `PatientStats`;
- raw `Balance` is non-zero;
- `PatientCode` is present and valid;
- PMS patient mapping is present;
- amount converts exactly to pence;
- raw sign is clear;
- component checks pass;
- no existing opening-balance marker exists for the same patient or
  `PatientCode`;
- selected representation is supported by the current schema.

Refused/manual-review rows:

- unmapped non-zero row;
- missing or blank `PatientCode`;
- component mismatch;
- invalid or non-pence amount;
- ambiguous or conflicting sign;
- source drift outside approved tolerance;
- duplicate source `PatientCode`;
- duplicate mapped PMS patient where uniqueness cannot be explained;
- duplicate existing opening-balance marker from the same or another manifest;
- unsupported source;
- unsupported write representation;
- any attempt to create invoices, payments, allocations, or finance staging
  rows.

Zero balances:

- no-op;
- no write;
- report count and samples;
- preserve metadata only in artefacts, not ledger rows.

## Scratch Apply Safety Gates

A future apply command must fail before opening a write session unless all gates
pass.

Target gates:

- target DB must be scratch/test only;
- default/live DB must be refused before session creation;
- DB name and connection label must be written to the manifest;
- scratch DB name must be explicit and must not be `dental_pms`;
- no R4 connection is required when preserved artefacts are used.

Operator gates:

- explicit confirmation token, for example
  `--confirm SCRATCH_OPENING_BALANCE_APPLY`;
- no environment default should imply apply mode;
- command must print target DB, manifest ID, and dry-run report path before
  writing.

Dry-run artefact gates:

- require prior dry-run report JSON;
- require `dry_run=true`;
- require `manifest.no_write=true`;
- require `manifest.apply_mode=false`;
- require `finance_import_ready=false`;
- require `import_ready=false` from the dry-run report as expected no-write
  evidence;
- require mapping coverage for all non-zero candidates;
- require `unmapped_nonzero_candidates=0`;
- require `eligible_opening_balance=1018` for the current artefact unless a
  newer approved dry-run records explained drift;
- require no component mismatches among would-write rows;
- require source, mapping, and dry-run report SHA256 values in the apply
  manifest.

Repo and manifest gates:

- record both `dry_run_repo_sha` and `apply_repo_sha`;
- require a stable apply manifest ID before writes;
- require the same manifest ID on idempotency and rollback;
- fail if the same manifest has a partial or mismatched existing application;
- fail if a different manifest already created an opening-balance marker for
  the same patient or source `PatientCode`;
- require before-counts for `patient_ledger_entries`, `invoices`, and
  `payments`;
- require `invoices` and `payments` before/after counts to remain unchanged.

The apply-specific report may have an `apply_ready` or `scratch_apply_ready`
field for the prototype, but `finance_import_ready` must remain `false`.

## Idempotency Design

Rows are already applied when an existing `PatientLedgerEntry` has:

- `entry_type=adjustment`;
- `reference` equal to `R4OB:<manifest_id>:<PatientCode>`;
- `patient_id` equal to the mapped PMS patient ID;
- `amount_pence` equal to the planned amount.

Expected rerun for the current dry-run evidence:

- `created=0`;
- `updated=0`;
- `skipped=1018`;
- refused/manual-review counts unchanged;
- invoice count unchanged;
- payment count unchanged.

The apply must never update existing ledger rows during idempotency. If an
existing marker has the same manifest but different patient, amount, source
code, or metadata hash, the run must fail closed as manifest corruption.

Duplicate `PatientCode` values in the input should fail before writes. Duplicate
mapped patient IDs among non-zero candidates should fail unless a prior mapping
policy explicitly approves the duplicate relationship. Duplicate opening-balance
markers from any previous manifest should fail before writes because a second
opening balance can double count patient debt.

## Rollback Design

Rollback must be manifest-scoped and scratch-only.

Rollback target rows:

- `PatientLedgerEntry.entry_type=adjustment`;
- `reference` starts with `R4OB:<manifest_id>:` or equals the exact per-row
  reference set in the apply report;
- optional metadata hash in `note` matches the apply manifest.

Rollback must not delete:

- manually entered ledger rows;
- invoice charge rows;
- payment rows;
- invoice-linked ledger rows;
- rows from another opening-balance manifest;
- rows where the reference prefix is absent or malformed.

Rollback proof should capture:

- manifest ID;
- apply report path and hash;
- before counts for ledger, invoices, and payments;
- candidate rollback row count;
- bounded rollback row samples;
- deleted row count or reversed row count, depending on chosen scratch rollback
  mechanism;
- after counts;
- remaining rows for the manifest, expected `0` if delete rollback is used;
- invoices and payments unchanged;
- stdout, stderr, exit code, and JSON report.

For scratch proof, deleting exact manifest-created rows is acceptable because
the scratch DB is disposable and rollback evidence needs to prove containment.
For any future live/default design, rollback must be revisited separately and
may require reversal entries, backup/restore points, and owner signoff.

## Artefacts and Audit Requirements

Future apply proof should preserve:

- accepted dry-run report path and SHA256;
- PatientStats source artefact path and SHA256;
- mapping artefact path and SHA256;
- apply report JSON;
- stdout log;
- stderr log;
- exit code file;
- manifest JSON;
- `dry_run_repo_sha`;
- `apply_repo_sha`;
- scratch DB name;
- confirmation token label used, not secrets;
- before and after counts for `patient_ledger_entries`, `invoices`, and
  `payments`;
- created, skipped, refused, and no-op counts;
- bounded samples for created, skipped, and refused rows;
- idempotency report;
- rollback report, if rollback is included;
- final proof that default/live PMS DB was refused.

The apply report should include enough source identifiers to reconcile every
created row:

- source name;
- source `PatientCode`;
- mapped PMS `patient_id`;
- raw `Balance`;
- raw component fields;
- raw aged-debt fields;
- raw sign;
- proposed PMS direction;
- `amount_pence`;
- ledger `reference`;
- ledger row ID in scratch;
- manifest ID.

## Future Scratch Apply Success Criteria

A future scratch apply prototype succeeds only if:

- default/live DB refusal is proven before session creation;
- scratch DB target is explicitly confirmed;
- dry-run report is accepted and hashed into the manifest;
- all eligible rows create exactly one `PatientLedgerEntry` adjustment row;
- current expected first-run created count is `1018`;
- zero-balance rows create no rows;
- refused/manual-review rows create no rows;
- no invoices are created;
- no payments are created;
- no finance records outside the selected ledger adjustment representation are
  created;
- invoice and payment counts remain unchanged;
- patient ledger before/after delta equals created opening-balance rows;
- idempotency rerun creates `0`, updates `0`, and skips `1018`;
- rollback, if included, touches only exact manifest-created rows and proves no
  remaining manifest rows;
- `finance_import_ready` remains `false` for full finance import.

## Remaining Blockers Before Live or Default Use

Before live/default PMS use, the project still needs:

- clinical/accounting owner acceptance of the raw sign interpretation;
- cutover timestamp policy;
- final source snapshot policy;
- manifest ID and retention policy;
- decision on whether a dedicated import-run model is needed before live use;
- rollback policy suitable for live data, not just scratch deletion;
- full patient mapping closure and duplicate mapping review;
- double-counting controls against any later cash-event staging;
- decision on how opening-balance rows interact with current patient-ledger UI
  and reporting;
- operator approval and backup/restore plan;
- complete scratch rehearsal transcript with idempotency and rollback evidence.

## Open Questions and Risks

- The current dry-run source drifted by `-400.00` from the earlier live proof.
  The future apply must decide whether the dry-run artefact is the selected
  source snapshot or whether to rerun a no-write dry-run from a newer
  PatientStats extraction.
- Patient-level statement examples are still needed before live/default use to
  confirm signs with the practice.
- `PatientLedgerEntry` has no dedicated import-run foreign key, so the initial
  scratch design depends on a strict `reference` prefix and manifest artefact.
- Existing patient ledger rows in a scratch target could already contain manual
  or test adjustments; the apply must count and report them without touching
  unrelated rows.
- A live design may need a stronger model than a ledger `reference` marker.
- Any later cash-event staging could double count if it overlaps the
  opening-balance cutover point.
- Aged-debt metadata has no PMS write representation in this design.

## Guarded Scratch Apply CLI Prototype

The current prototype adds:

- `backend/app/services/r4_import/opening_balance_snapshot_guarded_apply.py`
- `backend/app/scripts/r4_opening_balance_guarded_scratch_apply.py`
- `backend/tests/r4_import/test_opening_balance_guarded_scratch_apply_cli.py`

Prototype behaviour:

- consumes the existing opening-balance dry-run report JSON shape;
- computes and reports the dry-run report SHA256;
- accepts optional expected report SHA256, total balance, eligible count, and
  dry-run repo SHA guards;
- refuses non-scratch/non-test, default `dental_pms`, and production/live-looking
  database URLs before opening a session;
- defaults to validation/no-write mode;
- requires both `--apply` and
  `--confirm SCRATCH_OPENING_BALANCE_APPLY` before any scratch write;
- requires `--actor-id` for scratch audit fields when applying;
- runs the PR #612 preflight helper before applying;
- creates only `PatientLedgerEntry` rows with `entry_type=adjustment`,
  `related_invoice_id=NULL`, and references shaped
  `R4OB:<manifest_id>:<PatientCode>`;
- never creates `Invoice`, `InvoiceLine`, `Payment`, or finance staging rows;
- writes no rows in validation mode and does not open a DB session in that mode;
- supports idempotent rerun by exact manifest/reference/patient/amount match;
- fails closed on invalid artefacts, mismatched checksum/expected totals,
  missing guards, incomplete row artefacts, unsafe targets, or mismatched
  existing manifest rows.

Safe validation command shape:

```bash
python -m app.scripts.r4_opening_balance_guarded_scratch_apply \
  --dry-run-report-json /path/to/opening_balance_snapshot_dryrun_report.json \
  --database-url postgresql+psycopg://user:pass@host:5432/dental_pms_opening_balance_apply_scratch \
  --manifest-id ob-YYYYMMDDHHMMSS-abcdef123456 \
  --output-json /path/to/opening_balance_guarded_apply_validate.json \
  --expected-report-sha256 <sha256> \
  --expected-total-balance -131742.13 \
  --expected-eligible-count 1018 \
  --expected-repo-sha <dry-run-repo-sha> \
  --acknowledge-source-drift
```

Scratch apply command shape, for an explicitly isolated scratch/test DB only:

```bash
python -m app.scripts.r4_opening_balance_guarded_scratch_apply \
  --dry-run-report-json /path/to/opening_balance_snapshot_dryrun_report.json \
  --database-url postgresql+psycopg://user:pass@host:5432/dental_pms_opening_balance_apply_scratch \
  --manifest-id ob-YYYYMMDDHHMMSS-abcdef123456 \
  --output-json /path/to/opening_balance_guarded_apply_report.json \
  --expected-report-sha256 <sha256> \
  --expected-total-balance -131742.13 \
  --expected-eligible-count 1018 \
  --expected-repo-sha <dry-run-repo-sha> \
  --acknowledge-source-drift \
  --apply \
  --confirm SCRATCH_OPENING_BALANCE_APPLY \
  --actor-id <scratch-admin-user-id>
```

Current limitation: the prototype can apply only when the accepted dry-run
report contains every eligible row under `samples.eligible_opening_balance`.
The preserved execution report used bounded samples, so a future scratch apply
execution still needs either a full eligible-row dry-run artefact or a narrower
prototype fixture. This branch does not execute a scratch apply against the
preserved evidence artefacts.

`finance_import_ready` remains `false`. The prototype is not authorised for
live/default PMS data and is not a full finance import path.

## Recommended Next Slice

PR #612 completed the previously recommended backend-only guarded scratch apply
planning/preflight helper and tests.

Completed helper proof:

- implemented no-write preflight decisions for DB target, confirmation token,
  dry-run report, eligibility, mapping, before-counts, write plan, idempotency,
  rollback, and reason codes;
- refused missing target, default `dental_pms`, non-scratch/non-test targets,
  missing or wrong confirmation token, invalid dry-run report flags,
  incomplete non-zero mapping coverage, component mismatch among would-write
  rows, unacknowledged source drift, unsupported representation, invoice,
  payment, staging, balance-mutation intent, partial duplicate manifests, and
  broad ledger deletion;
- planned only `patient_ledger_entry_adjustment` rows and kept
  `finance_import_ready=false`;
- stayed backend-only/pure-helper/test-only, with no CLI, no DB session, no
  importer/apply behaviour change, no apply execution, no finance import, no
  finance staging models, no finance records created or changed, no PMS DB
  writes, and no R4 access or writes.

Selected next target after this prototype: docs/status refresh after merge, then
an explicit guarded scratch-only apply execution proof only if authorised.

Why this remains separate:

- this branch proves the command surface, guard logic, checksum/expected-total
  checks, validation mode, scratch-only write mechanics, and idempotency in
  deterministic tests;
- it does not execute against the preserved scratch artefacts;
- it does not prove full `1018`-row scratch application because the preserved
  dry-run report has bounded eligible samples;
- live/default PMS writes and full finance import remain out of scope.

Likely validation for the next execution-proof slice, if explicitly
authorised:

- regenerate or provide a full eligible-row dry-run artefact in isolated
  scratch/test context;
- run validation mode first;
- prove default/live refusal before session/open;
- apply only to an isolated scratch/test PMS DB;
- rerun idempotently;
- verify invoices/payments remain unchanged;
- preserve stdout/stderr/exit-code/report artefacts.

## Stop Point

This document records the guarded scratch-only apply decision and CLI
prototype. It does not implement finance import, finance staging models,
invoice creation, payment creation, R4 writes, live/default PMS writes,
frontend changes, Docker changes, or runtime changes. No scratch apply
execution against preserved evidence artefacts has started.
