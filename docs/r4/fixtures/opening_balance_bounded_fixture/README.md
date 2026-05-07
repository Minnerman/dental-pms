# Opening-Balance Candidate Bounded Fixture Package

Status date: 2026-05-07

Package status: candidate bounded fixture package pending approval.

This package is documentation/fixture preparation only. It does not authorise
guarded scratch apply execution, R4 access, real R4 artefact access, real
patient data handling, PMS database connections, PMS Postgres writes, finance
record creation, or finance import.

`finance_import_ready=false`.

## Package Purpose

This package prepares the Option B bounded fixture selected in
`docs/r4/R4_FINANCE_OPENING_BALANCE_EXECUTION_PACKAGE_DECISION.md`.

It is deliberately small, synthetic, inspectable, and hashable. A future
explicitly authorised slice may use this package for scratch/test-only
preserved-evidence execution proof only after the approval checklist is
completed.

## Contents

- `fixture.json`: synthetic opening-balance dry-run report-shaped fixture.
- `manifest.json`: package manifest, safety metadata, expected totals, hashes,
  redacted command shapes, and future evidence requirements.
- `APPROVAL_CHECKLIST.md`: owner approval checklist required before any future
  execution.

## Fixture Summary

- manifest ID: `ob-bounded-fixture-20260507-000001`
- package status: candidate pending owner approval
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

The fixture uses only these synthetic source identifiers:

- `TEST-R4OB-BF-001`
- `TEST-R4OB-BF-002`
- `TEST-R4OB-BF-003`

No real R4 patient codes, patient names, DOBs, addresses, phone numbers, emails,
clinical details, real account numbers, unredacted DSNs, or secrets are included.

## Inclusion Rules

Included rows:

- exactly three synthetic non-zero opening-balance rows;
- all rows have synthetic patient codes and synthetic mapped patient IDs;
- all rows are mapped and eligible for the selected bounded set;
- all rows have exact pence amounts;
- all rows have matching component totals;
- two rows exercise `increase_debt`;
- one row exercises `decrease_debt_or_credit`.

Excluded rows:

- zero-balance no-op rows;
- unmapped non-zero rows;
- component-mismatch rows;
- ambiguous-sign rows;
- invalid amount rows;
- real R4 rows;
- real patient, account, demographic, or clinical values.

Zero/no-op rows are intentionally excluded from this candidate package because
the guarded apply CLI consumes complete eligible rows for the selected execution
set. The zero/no-op path is already represented in dry-run planning evidence and
does not create ledger rows.

## Hash Commands

Run from the repository root:

```bash
sha256sum docs/r4/fixtures/opening_balance_bounded_fixture/fixture.json
sha256sum docs/r4/fixtures/opening_balance_bounded_fixture/manifest.json
python -m json.tool docs/r4/fixtures/opening_balance_bounded_fixture/fixture.json >/tmp/opening_balance_bounded_fixture.json.pretty
python -m json.tool docs/r4/fixtures/opening_balance_bounded_fixture/manifest.json >/tmp/opening_balance_bounded_manifest.json.pretty
```

Expected hashes for this candidate package:

```text
2afabfcb903b0f4e5a94702ae93b7752e9309e30116a4d01e1f55ec84465b53d  docs/r4/fixtures/opening_balance_bounded_fixture/fixture.json
66cc1c7ac16a4e677dfea6994cef86a5b7c496a00fbfec10336fa7641d98bb67  docs/r4/fixtures/opening_balance_bounded_fixture/manifest.json
```

## Future Command Shapes

The future execution slice must run validation/no-write first. The package does
not authorise either command.

Validation/no-write shape:

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

Future guarded scratch apply shape, only after approval and validation review:

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

The future target must be scratch/test only. Do not include unredacted DSNs or
secrets in committed evidence.

## Required Future Evidence

The future execution proof must preserve:

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
- redacted command shape;
- timestamp;
- safe non-sensitive actor/operator ID where applicable;
- cleanup or retained-target decision.

## Stop Conditions

Stop before execution if any of these occur:

- the approval checklist is incomplete;
- target is not clearly scratch/test;
- target resembles default, live, production, or operational PMS;
- checksum mismatch;
- expected-total mismatch;
- eligible-count mismatch;
- repo-SHA mismatch;
- missing `--confirm SCRATCH_OPENING_BALANCE_APPLY`;
- missing `--actor-id` for apply;
- unexpected write path;
- sensitive output;
- idempotency failure;
- rollback or cleanup ambiguity;
- invoice/payment/staging intent;
- any finance import request.

## Scope Boundary

This package is separate from:

- PR #615's completed synthetic scratch proof;
- PR #617's execution package decision;
- any future preserved-evidence scratch execution;
- live finance import, which remains unauthorised and out of scope.
