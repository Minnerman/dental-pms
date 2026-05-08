# R4 Finance Opening-Balance Bounded Fixture Guarded Apply Readiness

Status date: 2026-05-08

Base reviewed: `origin/master@c42bc48522842711a90fa6239ca0dcd88315625f`

This is a readiness-check document only. It does not execute guarded scratch apply, does not run CLI validation/no-write again, does not connect to any PMS database, does not create ledger rows, and does not authorise guarded apply/write.

`finance_import_ready=false`. Finance import, invoice import, payment import, staging import, R4 access, real R4 artefact access, live/default PMS database writes, actual PMS Postgres writes, and production execution remain out of scope.

## Readiness Status

The documented prerequisites are present for considering a future separately authorised scratch/test-only guarded apply/write slice against the approved bounded fixture package.

Guarded apply/write remains a later separately authorised slice. This report is not that authorisation and does not mark apply/write complete.

## Bound Assessment

This readiness assessment is bound to the following exact fixture, manifest, and signed-off validation/no-write evidence:

- Manifest ID: `ob-bounded-fixture-20260507-000001`
- Fixture/source hash: `2afabfcb903b0f4e5a94702ae93b7752e9309e30116a4d01e1f55ec84465b53d`
- Manifest checksum: `66cc1c7ac16a4e677dfea6994cef86a5b7c496a00fbfec10336fa7641d98bb67`
- Row count: `3`
- Eligible count: `3`
- Expected total: `7.35`
- Validation/no-write evidence SHA256: `c053f6514b6a9109c60561be5ae7485d81399d43cfc58bcbe58f915b5c880840`
- Validation/no-write evidence report: `docs/r4/R4_FINANCE_OPENING_BALANCE_BOUNDED_FIXTURE_VALIDATION_NOWRITE_EVIDENCE.md`
- Evidence output path: `.run/opening_balance_bounded_fixture_validation_nowrite_20260508_015124/opening_balance_guarded_apply_validate.json`
- Fixture approval record: `docs/r4/fixtures/opening_balance_bounded_fixture/APPROVAL_RECORD_20260507.md`
- Validation/no-write sign-off record: `docs/r4/fixtures/opening_balance_bounded_fixture/VALIDATION_NOWRITE_SIGNOFF_20260508.md`

The fixture data is synthetic only and uses the bounded identifiers `TEST-R4OB-BF-001`, `TEST-R4OB-BF-002`, and `TEST-R4OB-BF-003`. The committed fixture and manifest contain no real patient data, no real R4 data, no real R4 artefact contents, and no secrets.

## Prerequisites Confirmed

- Bounded fixture approval exists and is limited to the exact manifest ID, fixture/source hash, manifest checksum, row count, eligible count, and expected total listed above.
- Validation/no-write evidence exists and has owner sign-off for validation/no-write evidence only.
- The signed-off evidence records no `--apply`, no `--confirm`, no `--actor-id`, no PMS DB connection, no SQLite scratch/test DB file creation, `exit 0`, `apply_requested=false`, `created=0`, `updated=0`, `skipped=0`, `refused=0`, and finance counts `before=null` and `after=null`.
- The future apply/write path remains separated from the completed synthetic proof, the bounded fixture approval, the validation/no-write evidence, and the validation/no-write sign-off.

## Guard Support By Inspection Only

The guarded apply source and tests support the future apply/write guards by inspection only. The CLI was not executed for this readiness check.

- No-write is the default path when `--apply` is absent.
- The write path requires explicit `--apply`.
- The write path requires exact `--confirm SCRATCH_OPENING_BALANCE_APPLY`.
- The write path requires `--actor-id`.
- Non-scratch and live-looking targets are rejected.
- Hash, expected-total, eligible-count, and repo-SHA guard inputs are supported by the documented command shape and apply plan.
- Idempotency is manifest-scoped through deterministic opening-balance references.
- The apply path is scoped to opening-balance ledger adjustments and keeps finance import, invoice import, payment import, and staging import out of scope.

## Required Future Apply/Write Guards

A later separately authorised guarded apply/write slice must require all of the following:

- Scratch/test target only.
- `--apply`.
- Exact `--confirm SCRATCH_OPENING_BALANCE_APPLY`.
- `--actor-id` using a safe non-sensitive operator identifier.
- Fixture/source hash guard.
- Manifest checksum guard.
- Expected total guard.
- Eligible count guard.
- Repo SHA guard as documented for the execution package.
- Redacted DSN or target in any committed evidence.

The future command shape must remain redacted in committed documentation:

```bash
python -m backend.app.scripts.r4_opening_balance_guarded_scratch_apply \
  --report docs/r4/fixtures/opening_balance_bounded_fixture/fixture.json \
  --manifest docs/r4/fixtures/opening_balance_bounded_fixture/manifest.json \
  --database-url '<scratch-or-test-dsn-redacted>' \
  --expected-report-sha256 2afabfcb903b0f4e5a94702ae93b7752e9309e30116a4d01e1f55ec84465b53d \
  --expected-total-balance 7.35 \
  --expected-eligible-count 3 \
  --expected-repo-sha '<authorised-package-or-execution-sha>' \
  --actor-id '<safe-non-sensitive-operator-id>' \
  --apply \
  --confirm SCRATCH_OPENING_BALANCE_APPLY \
  --output '<preserved-evidence-path-redacted>'
```

## Required Future Evidence

A later separately authorised apply/write proof must preserve safe evidence for:

- Manifest ID.
- Manifest checksum.
- Fixture/source hash.
- Row count.
- Expected total.
- Target classification.
- Repo SHA.
- Redacted command shape.
- Timestamp.
- Safe non-sensitive actor/operator identifier where applicable.
- First-run created, updated, skipped, and refused counts.
- Second-run idempotency created, updated, skipped, and refused counts.
- Confirmation that no live/default PMS DB or actual PMS Postgres was used.
- Confirmation that no R4 or real R4 artefact was accessed.
- Confirmation that finance import, invoice import, payment import, and staging import did not run.

## Stop Conditions

The future apply/write slice must stop before execution if any of the following occur:

- Approval or sign-off is missing or mismatched.
- Target is not clearly scratch/test.
- Target resembles live/default/production.
- Fixture/source hash mismatch.
- Manifest checksum mismatch.
- Expected-total mismatch.
- Eligible-count mismatch.
- Repo-SHA mismatch.
- Missing `--apply`.
- Missing or wrong `--confirm` value.
- Missing `--actor-id`.
- Unexpected write path.
- Sensitive output.
- Idempotency failure.
- Rollback or cleanup ambiguity.
- Invoice, payment, or staging intent.
- Any finance import request.

## Non-Authorisations

This readiness report does not authorise:

- Guarded apply/write now.
- Live/default PMS database writes.
- Actual PMS Postgres writes.
- R4 access.
- Real R4 artefact access.
- Real patient data use.
- Finance import.
- Invoice/payment/staging import.
- Production execution.

## Next Gate

The next slice, if explicitly authorised later, should be a scratch/test-only guarded apply/write proof against this exact approved bounded fixture package. It must re-check the fixture and manifest hashes, validation/no-write sign-off, target classification, command guards, and preserved main worktree status before any execution.
