# R4 Finance Opening-Balance Bounded Fixture Package

Status date: 2026-05-07

Baseline: `origin/master@20dbbd06d27c5041ce916038ae7b5bff32ac4c98`

Safety: this is package preparation only. It does not execute guarded scratch
apply, run the CLI, access R4, open a real R4 artefact, use real patient data,
connect to a PMS database, write PMS Postgres rows, create finance records,
authorise finance import, or authorise live/default PMS use.

`finance_import_ready=false`. Finance import remains out of scope.

## Purpose

PR #617 selected Option B, an approved bounded fixture, as the next package type
for a future explicitly authorised scratch/test-only preserved-evidence
execution proof.

This document records the bounded fixture package prepared after that decision.
The package is deliberately small, synthetic, inspectable, and hashable. Owner
approval for this exact fixture hash and manifest checksum is recorded in the
package directory. The approval does not authorise execution by itself; any
future guarded scratch apply remains a separate explicitly authorised
scratch/test-only slice.

## Package Location

Package directory:

- `docs/r4/fixtures/opening_balance_bounded_fixture/`

Package files:

- `docs/r4/fixtures/opening_balance_bounded_fixture/README.md`
- `docs/r4/fixtures/opening_balance_bounded_fixture/fixture.json`
- `docs/r4/fixtures/opening_balance_bounded_fixture/manifest.json`
- `docs/r4/fixtures/opening_balance_bounded_fixture/APPROVAL_CHECKLIST.md`
- `docs/r4/fixtures/opening_balance_bounded_fixture/APPROVAL_RECORD_20260507.md`

Execution-readiness report:

- `docs/r4/R4_FINANCE_OPENING_BALANCE_BOUNDED_FIXTURE_EXECUTION_READINESS.md`

## Fixture Summary

- manifest ID: `ob-bounded-fixture-20260507-000001`
- approval status: approved for future scratch/test-only package use; execution
  still requires a separate explicitly authorised slice
- fixture type: synthetic non-R4 bounded fixture
- row count: `3`
- eligible count: `3`
- expected total: `7.35`
- target classification: scratch/test only
- base repo SHA: `5817a99bf14ec389b93fc169a9ddc536b54ba239`
- fixture SHA256:
  `2afabfcb903b0f4e5a94702ae93b7752e9309e30116a4d01e1f55ec84465b53d`
- manifest SHA256:
  `66cc1c7ac16a4e677dfea6994cef86a5b7c496a00fbfec10336fa7641d98bb67`

Synthetic source identifiers:

- `TEST-R4OB-BF-001`
- `TEST-R4OB-BF-002`
- `TEST-R4OB-BF-003`

The fixture includes two positive balances and one negative balance. Zero rows
are excluded because the guarded apply CLI consumes complete eligible rows for
the selected execution set, and zero/no-op rows do not create opening-balance
ledger adjustments.

## Acceptance Criteria Covered

The package records:

- stable manifest ID;
- fixture SHA256;
- manifest checksum command and current manifest SHA256;
- expected total;
- eligible count;
- base repo SHA;
- inclusion and exclusion rules;
- scratch/test target classification;
- redacted future command shapes;
- future evidence fields;
- approval checklist;
- external approval record for the exact fixture hash and manifest checksum.

The package contains no real patient names, DOBs, addresses, phone numbers,
emails, clinical details, real R4 patient codes, real account numbers, real R4
artefact contents, unredacted DSNs, or secrets.

## Approval Gate

The package is approved for future scratch/test-only package use by:

- `docs/r4/fixtures/opening_balance_bounded_fixture/APPROVAL_RECORD_20260507.md`

`fixture.json` and `manifest.json` are intentionally unchanged so the approved
fixture hash and manifest checksum remain valid. The manifest's original
candidate metadata is not the approval authority; the external approval record
is.

The approval does not authorise execution. Before any future run, the future
execution slice must explicitly authorise scratch/test-only guarded apply and
complete the remaining execution checks in the approval checklist.

Approval must confirm:

- the fixture is synthetic/non-sensitive;
- target remains scratch/test-only;
- validation/no-write runs before any apply;
- future apply uses `--apply`, `--confirm SCRATCH_OPENING_BALANCE_APPLY`, and
  `--actor-id`;
- fixture and manifest hashes match;
- expected total, eligible count, and repo SHA match;
- rollback/cleanup expectations are understood;
- no patient-sensitive values will be committed in future execution evidence;
- finance import remains out of scope.

## Future Evidence Requirements

A future execution proof must preserve:

- manifest ID;
- manifest checksum;
- fixture SHA256;
- row count;
- expected total;
- validation/no-write result;
- first guarded apply result;
- second-run idempotency result;
- created, updated, skipped, and refused counts;
- invoice and payment before/after counts;
- target classification;
- repo SHA;
- command shape with secrets redacted;
- timestamp;
- safe non-sensitive actor/operator ID where applicable;
- cleanup or retained-target decision.

## Stop Conditions

Stop before any future execution if:

- approval checklist is incomplete;
- target is not clearly scratch/test;
- target resembles default, live, production, or operational PMS;
- fixture SHA256 mismatch;
- manifest SHA256 mismatch;
- expected-total mismatch;
- eligible-count mismatch;
- repo-SHA mismatch;
- `--confirm SCRATCH_OPENING_BALANCE_APPLY` is missing for apply;
- `--actor-id` is missing for apply;
- unexpected write path appears;
- sensitive output would be logged or committed;
- idempotency proof fails;
- rollback or cleanup is ambiguous;
- invoice/payment/staging intent appears;
- any finance import request appears.

## Separation Of States

Completed synthetic scratch proof:

- PR #615 proved the guarded CLI write path and idempotency with generated
  non-R4 rows and local SQLite scratch/test data only.

Approved-bounded-fixture decision:

- PR #617 selected Option B, approved bounded fixture, as the next package type.

Approved bounded fixture package:

- this package records the fixture, checklist, and approval record;
- it is approved for future scratch/test-only package use;
- it does not execute anything or authorise execution by itself.

Future preserved-evidence scratch execution:

- remains a separate explicitly authorised slice;
- must be scratch/test-only;
- must run validation/no-write before apply;
- must prove idempotency;
- must preserve redacted evidence only.

Live finance import:

- remains unauthorised;
- remains out of scope;
- remains blocked by accounting sign acceptance, cutover timestamp policy,
  owner approval, double-counting controls, and full scratch rehearsal.

## Next Slice

Only after explicit instruction: run the future scratch/test-only execution
slice using the readiness report, with validation/no-write first. Do not run
guarded scratch apply unless that future slice separately authorises execution
and all target, hash, total, count, repo-SHA, rollback/cleanup, and redaction
checks pass.
