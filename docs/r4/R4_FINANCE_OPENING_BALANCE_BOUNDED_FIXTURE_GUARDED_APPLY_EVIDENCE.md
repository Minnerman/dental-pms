# R4 Finance Opening Balance Bounded Fixture Guarded Apply Evidence

Status date: 2026-05-08

This report records the first owner-authorised guarded apply/write proof for the approved bounded opening-balance fixture. The proof used only a local isolated SQLite scratch/test target and the approved bounded fixture. It does not authorise live/default PMS writes, actual PMS Postgres writes, R4 access, real R4 artefact access, real patient data use, finance import, invoice/payment/staging import, or production execution.

## Scope

- Origin/master SHA verified before execution: `731b28ebbff2d2b8049b5a324c4058367b09b5a0`
- Execution worktree SHA before evidence-doc commit: `731b28ebbff2d2b8049b5a324c4058367b09b5a0`
- Manifest ID: `ob-bounded-fixture-20260507-000001`
- Fixture/source SHA256: `2afabfcb903b0f4e5a94702ae93b7752e9309e30116a4d01e1f55ec84465b53d`
- Manifest SHA256: `66cc1c7ac16a4e677dfea6994cef86a5b7c496a00fbfec10336fa7641d98bb67`
- Row count: `3`
- Eligible count: `3`
- Expected total: `7.35`
- Validation/no-write sign-off: `docs/r4/fixtures/opening_balance_bounded_fixture/VALIDATION_NOWRITE_SIGNOFF_20260508.md`
- Owner authorisation: provided in task input for the first local isolated scratch/test-only guarded apply/write proof only.

## Target

- Target classification: local isolated SQLite scratch/test only.
- Scratch/test DB path: `.run/opening_balance_bounded_fixture_guarded_apply_20260508_174319/dental_pms_opening_balance_bounded_fixture_scratch_test.sqlite`
- Scratch/test DB committed: no.
- Scratch seed scope: one synthetic operator row, `990000`, and synthetic fixture patient IDs `990001`, `990002`, and `990003`.
- PMS DB connection: yes, to the local isolated SQLite scratch/test target only.
- Live/default PMS DB connection: no.
- Actual PMS Postgres connection: no.

## Command Shape

The guarded apply proof used this redacted command shape for both runs:

```text
PYTHONPATH=backend python -m app.scripts.r4_opening_balance_guarded_scratch_apply
  --dry-run-report-json docs/r4/fixtures/opening_balance_bounded_fixture/fixture.json
  --database-url '<local-isolated-sqlite-scratch-test-dsn-redacted>'
  --manifest-id ob-bounded-fixture-20260507-000001
  --output-json '<safe-local-run-output-json>'
  --expected-report-sha256 2afabfcb903b0f4e5a94702ae93b7752e9309e30116a4d01e1f55ec84465b53d
  --expected-total-balance 7.35
  --expected-eligible-count 3
  --expected-repo-sha 5817a99bf14ec389b93fc169a9ddc536b54ba239
  --apply
  --confirm SCRATCH_OPENING_BALANCE_APPLY
  --actor-id 990000
```

The proof used `--apply`, the exact `--confirm SCRATCH_OPENING_BALANCE_APPLY` phrase, and `--actor-id 990000`.

## First Guarded Apply Result

- Output JSON: `.run/opening_balance_bounded_fixture_guarded_apply_20260508_174319/opening_balance_guarded_apply_first.json`
- Output JSON SHA256: `802d4ca94762e060037b97dc68bdd08ad40d17541f04493378f5a0125a567837`
- Captured stdout JSON: `.run/opening_balance_bounded_fixture_guarded_apply_20260508_174319/first_stdout.json`
- Captured stdout SHA256: `90bdee22712271262873f21d54641875bfe853466e181b3113bb5f2f1b0cc1a3`
- Exit code: `0`
- `apply_requested`: `true`
- Before counts: `patient_ledger_entries=0`, `invoices=0`, `payments=0`
- After counts: `patient_ledger_entries=3`, `invoices=0`, `payments=0`
- Result counts: `created=3`, `updated=0`, `skipped=0`, `refused=0`
- Expected total: `7.35`
- `finance_import_ready`: `false`

## Second-Run Idempotency Result

- Output JSON: `.run/opening_balance_bounded_fixture_guarded_apply_20260508_174319/opening_balance_guarded_apply_second_idempotency.json`
- Output JSON SHA256: `e83a3faf7a6b22045d11a98559f342618d81a192841079864d0e2688cdfa5e2b`
- Captured stdout JSON: `.run/opening_balance_bounded_fixture_guarded_apply_20260508_174319/second_stdout.json`
- Captured stdout SHA256: `6e35d8fd49bd978b8cf714c86fbff4373c2e94b7c8e13d717e9834e7007a9662`
- Exit code: `0`
- `apply_requested`: `true`
- Before counts: `patient_ledger_entries=3`, `invoices=0`, `payments=0`
- After counts: `patient_ledger_entries=3`, `invoices=0`, `payments=0`
- Result counts: `created=0`, `updated=0`, `skipped=3`, `refused=0`
- Idempotency conclusion: passed. The second run recognised the existing manifest-scoped rows and created no duplicates.
- `finance_import_ready`: `false`

## Local Query Verification

- Query verification JSON: `.run/opening_balance_bounded_fixture_guarded_apply_20260508_174319/opening_balance_guarded_apply_local_query_verification.json`
- Query verification SHA256: `db8846ca82489a67a0979a5524fbb1e8f0cefe6d36db12630180e13293b762f0`
- Ledger row count: `3`
- Ledger total pence: `735`
- Ledger total decimal: `7.35`
- Unique manifest-scoped reference count: `3`
- Patient IDs: `990001`, `990002`, `990003`
- References:
  - `R4OB:ob-bounded-fixture-20260507-000001:TEST-R4OB-BF-001`
  - `R4OB:ob-bounded-fixture-20260507-000001:TEST-R4OB-BF-002`
  - `R4OB:ob-bounded-fixture-20260507-000001:TEST-R4OB-BF-003`
- Invoice count: `0`
- Payment count: `0`
- Scratch-test finance records created/changed: yes, exactly three local isolated scratch/test `PatientLedgerEntry` adjustment rows in the first run; the second run created none.
- Live finance records created/changed: no.

## Safety

- R4 access: no.
- Real R4 artefact access: no.
- Real patient data used: no.
- Live/default PMS DB writes: no.
- Actual PMS Postgres writes: no.
- Finance import started: no.
- Invoice/payment/staging import started: no.
- Raw DB file committed: no.
- Raw unredacted DSNs/secrets committed: no.
- Sensitive-output review: safe committed evidence contains no patient names, DOBs, addresses, phone numbers, emails, clinical details, unredacted DSNs/secrets, or full real artefact contents.

## Non-Authorisations

This proof is not production readiness. It does not authorise live/default PMS writes, actual PMS Postgres writes, any R4 access, real R4 artefact access, real patient data use, finance import, invoice/payment/staging import, or any broader fixture/package execution.

The next gate is human review of this guarded apply/idempotency evidence before deciding whether any further scratch/test-only finance proof is needed.
