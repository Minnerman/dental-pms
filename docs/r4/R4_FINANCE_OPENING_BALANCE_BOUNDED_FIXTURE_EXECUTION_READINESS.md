# R4 Finance Opening-Balance Bounded Fixture Execution Readiness

Status date: 2026-05-08

Baseline: `origin/master@7a83543dd657a6ecbe4cad640b9f7429996265c6`

Safety: this is a verification and readiness document only. It does not execute
guarded scratch apply, run CLI validation, access R4, open a real R4 artefact,
use real patient data, connect to a PMS database, write PMS Postgres rows,
create scratch-test finance records, authorise finance import, or authorise
live/default PMS use.

`finance_import_ready=false`. Finance import remains out of scope.

Validation/no-write evidence for this approved package is recorded in:

- `docs/r4/R4_FINANCE_OPENING_BALANCE_BOUNDED_FIXTURE_VALIDATION_NOWRITE_EVIDENCE.md`

That evidence did not use `--apply` or `--confirm`, did not connect to a PMS
database, did not create a SQLite scratch/test database file, and did not create
ledger rows or finance records.

## Readiness Status

Status: ready for a later separately authorised scratch/test-only
preserved-evidence execution slice, starting with validation/no-write.

This readiness status applies only to the approved bounded fixture package:

- manifest ID: `ob-bounded-fixture-20260507-000001`
- fixture/source hash:
  `2afabfcb903b0f4e5a94702ae93b7752e9309e30116a4d01e1f55ec84465b53d`
- manifest checksum:
  `66cc1c7ac16a4e677dfea6994cef86a5b7c496a00fbfec10336fa7641d98bb67`
- row count: `3`
- eligible count: `3`
- expected total: `7.35`
- target classification: scratch/test only

The approval record is:

- `docs/r4/fixtures/opening_balance_bounded_fixture/APPROVAL_RECORD_20260507.md`

The approval is not transferable to other fixtures, hashes, manifests,
artefacts, row counts, expected totals, or live/default data.

## Verification Summary

Verified inputs:

- `docs/r4/fixtures/opening_balance_bounded_fixture/fixture.json`
- `docs/r4/fixtures/opening_balance_bounded_fixture/manifest.json`
- `docs/r4/fixtures/opening_balance_bounded_fixture/APPROVAL_CHECKLIST.md`
- `docs/r4/fixtures/opening_balance_bounded_fixture/APPROVAL_RECORD_20260507.md`
- `docs/r4/R4_FINANCE_OPENING_BALANCE_BOUNDED_FIXTURE_PACKAGE.md`
- `docs/r4/R4_FINANCE_OPENING_BALANCE_PRESERVED_EVIDENCE_SCRATCH_EXECUTION_PLAN.md`
- `docs/r4/R4_FINANCE_OPENING_BALANCE_GUARDED_APPLY_DESIGN.md`
- `backend/app/scripts/r4_opening_balance_guarded_scratch_apply.py`
- `backend/app/services/r4_import/opening_balance_snapshot_guarded_apply.py`
- `backend/tests/r4_import/test_opening_balance_guarded_scratch_apply_cli.py`
- `backend/tests/r4_import/test_opening_balance_guarded_scratch_apply_synthetic_proof.py`

Verification results:

- approval record exists on current `origin/master`;
- approval is limited to the exact fixture hash and manifest checksum;
- approval is limited to future scratch/test-only preserved-evidence execution
  package use;
- approval does not authorise execution by this readiness slice;
- `fixture.json` and `manifest.json` are unchanged from the approved hashes;
- both JSON files parse successfully;
- fixture data uses only synthetic `TEST-R4OB-BF-*` identifiers;
- no real patient names, DOBs, addresses, phone numbers, emails, clinical
  details, real R4 patient codes, real account numbers, unredacted DSNs,
  secrets, or real artefact contents are committed in the package;
- future evidence fields and stop conditions are defined;
- code inspection confirms the guarded CLI supports the required safety gates.

## Guard Support By Inspection

The guarded CLI and service support:

- validation/no-write default when `--apply` is absent;
- explicit `--apply` guard before any scratch write;
- exact `--confirm SCRATCH_OPENING_BALANCE_APPLY` confirmation requirement for
  apply mode;
- `--actor-id` requirement for apply mode;
- rejection of `dental_pms`, production/live-looking, and database names that
  do not clearly contain `scratch` or `test`;
- dry-run report SHA256 guard through `--expected-report-sha256`;
- expected total guard through `--expected-total-balance`;
- eligible count guard through `--expected-eligible-count`;
- dry-run repo SHA guard through `--expected-repo-sha`;
- source-drift acknowledgement gate when applicable;
- manifest-scoped ledger references of the form
  `R4OB:<manifest_id>:<PatientCode>`;
- idempotency by skipping existing matching manifest rows;
- fail-closed handling for mismatched existing manifest rows;
- invoice and payment count unchanged checks;
- output summaries that keep `finance_import_ready=false`.

## Required Future Command Shape

Future validation/no-write command shape, with secrets redacted:

```bash
python -m app.scripts.r4_opening_balance_guarded_scratch_apply \
  --dry-run-report-json docs/r4/fixtures/opening_balance_bounded_fixture/fixture.json \
  --database-url '<scratch-or-test-dsn-redacted>' \
  --manifest-id ob-bounded-fixture-20260507-000001 \
  --output-json '<redacted-evidence-dir>/opening_balance_guarded_apply_validate.json' \
  --expected-report-sha256 2afabfcb903b0f4e5a94702ae93b7752e9309e30116a4d01e1f55ec84465b53d \
  --expected-total-balance 7.35 \
  --expected-eligible-count 3 \
  --expected-repo-sha 5817a99bf14ec389b93fc169a9ddc536b54ba239
```

Future guarded scratch apply command shape, only after validation/no-write is
reviewed and a later execution slice separately authorises apply:

```bash
python -m app.scripts.r4_opening_balance_guarded_scratch_apply \
  --dry-run-report-json docs/r4/fixtures/opening_balance_bounded_fixture/fixture.json \
  --database-url '<scratch-or-test-dsn-redacted>' \
  --manifest-id ob-bounded-fixture-20260507-000001 \
  --output-json '<redacted-evidence-dir>/opening_balance_guarded_apply_report.json' \
  --expected-report-sha256 2afabfcb903b0f4e5a94702ae93b7752e9309e30116a4d01e1f55ec84465b53d \
  --expected-total-balance 7.35 \
  --expected-eligible-count 3 \
  --expected-repo-sha 5817a99bf14ec389b93fc169a9ddc536b54ba239 \
  --apply \
  --confirm SCRATCH_OPENING_BALANCE_APPLY \
  --actor-id '<safe-non-sensitive-actor-id>'
```

These command shapes are documentation only. They were not executed in this
readiness slice.

## Required Future Execution Sequence

The future execution slice must proceed in this order:

1. Preflight verification: confirm approval record, fixture hash, manifest
   checksum, row count, eligible count, expected total, repo SHA, target
   classification, redacted evidence path, and preserved operational diff
   state.
2. Validation/no-write: run the guarded CLI without `--apply` against a clearly
   isolated scratch/test target only.
3. Review no-write evidence: confirm validation output, target refusal gates,
   report identity, before-counts, fixture rows, and no-write result.
4. Separately authorised guarded apply: run with `--apply`,
   `--confirm SCRATCH_OPENING_BALANCE_APPLY`, and `--actor-id` only if the
   future slice explicitly authorises apply after reviewing validation output.
5. Second-run idempotency proof: rerun the same manifest against the same
   scratch/test target and confirm `created=0`, `updated=0`, `skipped=3`, and
   no duplicate ledger rows.
6. Evidence report: preserve redacted validation, first-run, second-run,
   stdout/stderr/exit-code, before/after counts, command shape, cleanup or
   rollback decision, and safety confirmations.

## Required Future Evidence Fields

The future execution report must include:

- manifest ID;
- manifest checksum;
- fixture/source hash;
- row count;
- eligible count;
- expected total;
- validation/no-write result;
- first guarded apply result, if separately authorised;
- second-run idempotency result, if apply is separately authorised;
- created, updated, skipped, and refused counts;
- invoice and payment before/after counts;
- target classification;
- repo SHA;
- redacted command shape;
- timestamp;
- safe non-sensitive actor/operator ID where applicable;
- cleanup or rollback decision;
- explicit statement that finance import remains out of scope.

## Stop Conditions

Stop before execution if any of these occur:

- target is not clearly scratch/test;
- target resembles live, default, production, or operational PMS;
- approval record is missing or mismatched;
- fixture SHA256 mismatch;
- manifest SHA256 mismatch;
- expected-total mismatch;
- eligible-count mismatch;
- repo-SHA mismatch;
- required guards are missing;
- unexpected write path appears;
- sensitive output would be logged or committed;
- idempotency cannot be proven;
- rollback or cleanup is ambiguous;
- invoice, payment, or staging intent appears;
- any finance import request appears;
- R4 access, real R4 artefact access, real patient data, or a real/default PMS
  target appears necessary.

## Explicit Non-Authorisations

This readiness verification does not authorise:

- guarded scratch apply execution;
- guarded scratch apply CLI validation;
- PMS database connection;
- live/default PMS database writes;
- actual PMS Postgres writes;
- scratch-test finance record creation;
- R4 access;
- real R4 artefact access;
- real patient data use;
- finance import;
- finance import or staging models;
- invoice, payment, or staging import;
- production execution.

Live finance import remains unauthorised. Migration/import is not complete.
Production readiness is not implied.
