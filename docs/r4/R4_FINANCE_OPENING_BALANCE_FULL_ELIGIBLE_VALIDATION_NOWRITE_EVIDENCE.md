# R4 Finance Opening-Balance Full Eligible-Row Validation/No-Write Evidence

Status date: 2026-05-09

Baseline: `origin/master@f299243dbe0d54e759a1831f9caa2e562b48d182`

This evidence records the standing-authorised non-live scratch/test-only
validation/no-write slice for the approved full eligible-row opening-balance
package. It does not authorise or perform guarded apply/write.

Owner sign-off for this validation/no-write evidence is recorded separately at:
`docs/r4/R4_FINANCE_OPENING_BALANCE_FULL_ELIGIBLE_VALIDATION_NOWRITE_SIGNOFF.md`.
That sign-off is limited to validation/no-write evidence review and does not
authorise live/default PMS DB writes, actual PMS Postgres writes, production
execution, live finance import, invoice/payment/staging import, or committing
raw artefact or patient-level contents.

This slice did not access R4, did not connect to a PMS database, did not create
a SQLite scratch/test database file, did not write rows, did not pass `--apply`,
did not pass `--confirm`, did not create or change finance records, and did not
start finance import.

`finance_import_ready=false`. Migration/import is not complete. Production
readiness is not established. Guarded apply/write remains future and separately
gated.

## Package Identity

| Field | Value |
| --- | --- |
| Request ID | `r4ob-full-eligible-request-20260509-000001` |
| Manifest ID | `r4ob-full-eligible-20260509-000001` |
| Source artefact SHA256 | `357400cf5c1a53a8b34b6b0d7589b57b76754603946282d794b1881f71f75755` |
| Manifest checksum | `3b902805b138700441ba99b15eb2dadef34829fa3d3544383c0e387142f5a51b` |
| Package summary SHA256 | `25c15e9ebcd018c108dfca758ce04d6463f0520af0c918c4ee97f7cfc8aeb872` |
| Eligible row count | `1018` |
| Excluded row count | `15999` |
| Expected total | `-131187.13` |
| Expected total pence | `-13118713` |
| Repo SHA | `f299243dbe0d54e759a1831f9caa2e562b48d182` |

Package evidence and owner sign-off are recorded in:

- `docs/r4/R4_FINANCE_OPENING_BALANCE_FULL_ELIGIBLE_ARTEFACT_PACKAGE_EVIDENCE.md`
- `docs/r4/R4_FINANCE_OPENING_BALANCE_FULL_ELIGIBLE_ARTEFACT_PACKAGE_EVIDENCE_SIGNOFF.md`

The source artefact, manifest, and package summary remain outside the repo in
owner-local access-controlled storage. The exact storage path is not committed.

## Validation Inputs

The non-repo package files were accessed only for identity and aggregate
validation:

- source artefact hash matched the signed-off SHA256;
- manifest JSON parsed and matched the signed-off checksum;
- package summary JSON parsed and matched the signed-off SHA256;
- source artefact aggregate validation produced only safe counts and totals.

No raw source rows, patient-level contents, patient names, dates of birth,
addresses, phone numbers, emails, clinical details, exact storage paths,
unredacted DSNs, or secrets are committed.

To keep the guarded CLI output safe for evidence handling, the transient
validation input omitted row samples. The CLI therefore reports
`row_source_complete=false`; this is expected for this redacted no-write slice
and preserves patient-level redaction. Full source identity, row count, total,
sign, direction, and duplicate checks were validated separately by aggregate
check without committing row contents.

## Command Shape

Redacted validation/no-write command shape:

```text
PYTHONPATH=backend <scratch-apply-venv-python> \
  -m app.scripts.r4_opening_balance_guarded_scratch_apply \
  --dry-run-report-json .run/r4_full_eligible_validation_nowrite_20260509_184347/full_eligible_validation_nowrite_input.json \
  --database-url sqlite:////tmp/dental-pms-r4-full-eligible-validation-nowrite-scratch-test-20260509.sqlite \
  --manifest-id r4ob-full-eligible-20260509-000001 \
  --output-json .run/r4_full_eligible_validation_nowrite_20260509_184347/opening_balance_guarded_apply_validate.json \
  --expected-report-sha256 29f42c0c8e8396cea0eba5e5a76fb37dceb2f24b5ce4a8c001e97a52239ed43b \
  --expected-total-balance -131187.13 \
  --expected-eligible-count 1018 \
  --expected-repo-sha f299243dbe0d54e759a1831f9caa2e562b48d182 \
  --sample-limit 1
```

The command deliberately omitted:

- `--apply`
- `--confirm`
- `--actor-id`

Target classification:

- target string: local SQLite scratch/test URL;
- parsed database name:
  `dental-pms-r4-full-eligible-validation-nowrite-scratch-test-20260509.sqlite`;
- scratch/test target decision: allowed by name inspection;
- PMS DB connection: no;
- SQLite DB file created: no;
- DB writes: no.

## Validation Result

Result: passed for validation/no-write.

The guarded CLI exited `0` and wrote local validation JSON only:

- local CLI evidence path:
  `.run/r4_full_eligible_validation_nowrite_20260509_184347/opening_balance_guarded_apply_validate.json`
- local CLI evidence SHA256:
  `8f5831649d96b19881c330aa0798da40b6fb851bc6acf72ec6e914f70a6a273d`
- local CLI evidence size: `5121` bytes
- transient no-write input SHA256:
  `29f42c0c8e8396cea0eba5e5a76fb37dceb2f24b5ce4a8c001e97a52239ed43b`
- source aggregate check SHA256:
  `31be7121c2c753c665b7a43529a203bed085e5b76309b602198be586d9b0577f`

Summary fields:

- `apply_requested=false`
- `scratch_only=true`
- `finance_import_ready=false`
- representation: `patient_ledger_entry_adjustment`
- result counts: `created=0`, `updated=0`, `skipped=0`, `refused=0`
- finance counts: `before=null`, `after=null`
- write intent: `invoices=0`, `payments=0`, `staging_models=0`,
  `balance_mutation_outside_ledger_adjustment=false`

The preflight plan reported `is_safe_to_apply_in_scratch=false` with
`missing_confirmation_token`. That is expected for this slice because no apply
confirmation was supplied. This preserves the guarded apply/write gate and does
not indicate a validation failure.

The preflight plan also recorded:

- `scratch_or_test_database_allowed`;
- `dry_run_true`;
- `import_ready_false`;
- `finance_import_ready_false`;
- `manifest_no_write_true`;
- `manifest_apply_mode_false`;
- `dry_run_repo_sha_present`;
- `all_nonzero_candidates_mapped`;
- `before_finance_counts_present`;
- `apply_execution=false`;
- `would_create=1018`;
- `would_skip=0`;
- `would_refuse=15999`.

The `would_create` and `would_refuse` values are plan-only counts. No rows were
created, updated, skipped, refused, or written by this validation/no-write run.

## Source Aggregate Check

The source artefact aggregate check read the non-repo source artefact and wrote
only safe summary values:

- row count: `1018`
- amount pence total: `-13118713`
- decimal total: `-131187.13`
- decision counts: `eligible_opening_balance=1018`
- proposed PMS direction counts:
  `decrease_debt_or_credit=727`, `increase_debt=291`
- raw sign counts: `negative=727`, `positive=291`
- distinct source patient code count: `1018`
- duplicate source patient code count: `0`
- zero amount rows: `0`
- invalid amount rows: `0`
- patient-level contents in aggregate output: no
- raw rows in aggregate output: no

## Safety Outcomes

| Guard | Result |
| --- | --- |
| R4 access during this slice | No |
| Real artefact access during this slice | Yes, limited to non-repo identity hashing, manifest/package summary parsing, and aggregate count/total validation. |
| Real patient data committed | No |
| Patient-level contents committed | No |
| Raw artefact contents committed | No |
| PMS DB connection | No |
| Local scratch SQLite DB opened or queried | No |
| DB writes | No |
| Live/default PMS DB writes | No |
| Actual PMS Postgres writes | No |
| Validation/no-write run | Yes |
| Guarded apply/write run | No |
| `--apply` used | No |
| `--confirm` used | No |
| Scratch-test finance records created/changed | No |
| Live finance records created/changed | No |
| Finance import started | No |
| Invoice/payment/staging import | No |

## Non-Authorisation

This validation/no-write evidence does not authorise:

- guarded apply/write;
- passing `--apply`;
- passing `--confirm`;
- PMS DB writes;
- live/default PMS DB writes;
- actual PMS Postgres writes;
- production execution;
- live finance import;
- invoice/payment/staging import;
- committing raw R4 artefact contents;
- committing patient names, dates of birth, addresses, phone numbers, emails,
  clinical details, exact storage paths, or unredacted DSNs/secrets.

## Next Gate

The next gate is owner review/sign-off of this validation/no-write evidence.
Only after that separate sign-off can a later slice consider scratch/test-only
guarded apply/write readiness or authorisation. Guarded apply/write remains
unauthorised now.
