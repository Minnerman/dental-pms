# R4 Finance Opening-Balance Bounded Fixture Validation/No-Write Evidence

Status date: 2026-05-08

Baseline: `origin/master@39e97e0af7baa669b8ce075a7b7194ea7bf4c33c`

Safety: this evidence records validation/no-write only. It did not run guarded
apply, did not pass `--apply`, did not pass `--confirm`, did not connect to a
PMS database, did not create a SQLite scratch/test database file, did not create
ledger rows, did not access R4, did not open a real R4 artefact, did not use
real patient data, and did not start finance import.

`finance_import_ready=false`. Finance import remains out of scope.

## Package Verified

Approved bounded fixture package:

- approval record:
  `docs/r4/fixtures/opening_balance_bounded_fixture/APPROVAL_RECORD_20260507.md`
- fixture:
  `docs/r4/fixtures/opening_balance_bounded_fixture/fixture.json`
- manifest:
  `docs/r4/fixtures/opening_balance_bounded_fixture/manifest.json`
- validation/no-write sign-off:
  `docs/r4/fixtures/opening_balance_bounded_fixture/VALIDATION_NOWRITE_SIGNOFF_20260508.md`
- manifest ID: `ob-bounded-fixture-20260507-000001`
- row count: `3`
- eligible count: `3`
- expected total: `7.35`
- fixture/source hash:
  `2afabfcb903b0f4e5a94702ae93b7752e9309e30116a4d01e1f55ec84465b53d`
- manifest checksum:
  `66cc1c7ac16a4e677dfea6994cef86a5b7c496a00fbfec10336fa7641d98bb67`

The fixture uses only synthetic `TEST-R4OB-BF-*` identifiers. No real patient
names, DOBs, addresses, phone numbers, emails, clinical details, real R4 patient
codes, real account numbers, unredacted DSNs, secrets, or full real artefact
contents were used.

## Validation Commands

JSON and hash validation:

```bash
git diff --check
git diff --cached --check
git diff --check origin/master...HEAD
python -m json.tool docs/r4/fixtures/opening_balance_bounded_fixture/fixture.json >/tmp/opening_balance_bounded_fixture.json.pretty
python -m json.tool docs/r4/fixtures/opening_balance_bounded_fixture/manifest.json >/tmp/opening_balance_bounded_manifest.json.pretty
sha256sum docs/r4/fixtures/opening_balance_bounded_fixture/fixture.json docs/r4/fixtures/opening_balance_bounded_fixture/manifest.json
```

Validation/no-write command shape, with the local scratch/test target and output
path shown because they contain no secrets:

```bash
PYTHONPATH=backend /tmp/dental-pms-scratch-apply-venv/bin/python \
  -m app.scripts.r4_opening_balance_guarded_scratch_apply \
  --dry-run-report-json docs/r4/fixtures/opening_balance_bounded_fixture/fixture.json \
  --database-url sqlite:////tmp/dental-pms-ob-bounded-fixture-validation-nowrite-scratch-test.sqlite \
  --manifest-id ob-bounded-fixture-20260507-000001 \
  --output-json .run/opening_balance_bounded_fixture_validation_nowrite_20260508_015124/opening_balance_guarded_apply_validate.json \
  --expected-report-sha256 2afabfcb903b0f4e5a94702ae93b7752e9309e30116a4d01e1f55ec84465b53d \
  --expected-total-balance 7.35 \
  --expected-eligible-count 3 \
  --expected-repo-sha 5817a99bf14ec389b93fc169a9ddc536b54ba239
```

The command deliberately omitted:

- `--apply`
- `--confirm`
- `--actor-id`

## Validation Result

Result: passed for validation/no-write.

The guarded CLI exited `0` and wrote the validation JSON report only:

- local evidence path:
  `.run/opening_balance_bounded_fixture_validation_nowrite_20260508_015124/opening_balance_guarded_apply_validate.json`
- local evidence SHA256:
  `c053f6514b6a9109c60561be5ae7485d81399d43cfc58bcbe58f915b5c880840`
- local evidence size: `6480` bytes

Summary fields:

- `apply_requested=false`
- `scratch_only=true`
- `row_source_complete=true`
- `finance_import_ready=false`
- representation: `patient_ledger_entry_adjustment`
- result counts: `created=0`, `updated=0`, `skipped=0`, `refused=0`
- finance counts: `before=null`, `after=null`
- write intent: `invoices=0`, `payments=0`, `staging_models=0`,
  `balance_mutation_outside_ledger_adjustment=false`

The preflight plan reported `is_safe_to_apply_in_scratch=false` with
`missing_confirmation_token`. That is expected for this slice because the apply
confirmation was intentionally not supplied. This preserves the apply gate and
does not indicate an apply/write authorisation.

## Owner Sign-Off

Owner sign-off for this validation/no-write evidence is recorded in:

- `docs/r4/fixtures/opening_balance_bounded_fixture/VALIDATION_NOWRITE_SIGNOFF_20260508.md`

The sign-off is limited to this evidence document, the local evidence SHA256,
the approved bounded fixture hash, the manifest checksum, manifest
`ob-bounded-fixture-20260507-000001`, row count `3`, eligible count `3`, and
expected total `7.35`.

The sign-off accepts the validation/no-write evidence for consideration of a
later separately authorised scratch/test-only guarded apply/write slice. It
does not authorise guarded apply/write, PMS writes, R4 access, real artefact
access, real patient data use, finance import, invoice/payment/staging import,
or production execution.

Target classification:

- target string: local SQLite scratch/test URL
- parsed database name:
  `dental-pms-ob-bounded-fixture-validation-nowrite-scratch-test.sqlite`
- scratch/test target decision: allowed by name inspection
- PMS DB connection: no
- SQLite DB file created: no
- ledger rows created: no
- finance records created or changed: no

## Output Safety

The validation output contains only synthetic fixture identifiers and static
guard metadata. It does not contain real patient names, DOBs, addresses, phone
numbers, emails, clinical details, unredacted DSNs, secrets, or real artefact
contents.

The validation output does include the static preflight reason
`missing_confirmation_token`; that was expected because this slice did not
supply any apply confirmation.

## Non-Authorisations

This validation evidence does not authorise:

- guarded apply/write execution;
- passing `--apply`;
- passing `--confirm`;
- PMS database writes;
- actual PMS Postgres writes;
- scratch-test finance record creation;
- live/default/production PMS use;
- R4 access;
- real R4 artefact access;
- real patient data use;
- finance import;
- finance import or staging models;
- invoice, payment, or staging import.

## Next Gate

After owner sign-off, the next gate is a separate explicit decision whether to
authorise a scratch/test-only guarded apply/write slice. Guarded apply/write may
be considered only in that later separately authorised slice, and only after it
re-confirms the target, fixture hash, manifest checksum, expected total,
eligible count, repo SHA, rollback/cleanup plan, and redaction controls still
match the approved package.
