# R4 Finance Opening-Balance Synthetic Scratch Proof

Status date: 2026-05-07

Baseline: `origin/master@32f0bf4b61192b29974fe10cbf6d48ad96e1d03a`

Safety: this is a bounded synthetic scratch proof for the guarded
opening-balance apply CLI. It uses generated non-R4 data, a local SQLite
scratch/test database under pytest `tmp_path`, and synthetic patient/account
codes only. It does not use a real R4 artefact, real patient data, a real PMS
database, actual PMS Postgres, live/default PMS data, finance import, finance
staging models, invoices, or payments.

## Proof Harness

The proof is implemented in:

- `backend/tests/r4_import/test_opening_balance_guarded_scratch_apply_synthetic_proof.py`

The harness builds a synthetic opening-balance dry-run report at test runtime
with two eligible rows:

- `TEST-R4OB-001`: `12.34`
- `TEST-R4OB-002`: `-5.00`

Synthetic proof summary:

- manifest id: `ob-synthetic-20260507-000001`
- synthetic eligible row count: `2`
- expected total: `7.34`
- target type: local SQLite scratch/test under pytest `tmp_path`
- validation/no-write mode: writes only the validation JSON under `tmp_path`
  and does not create the SQLite database file
- first guarded apply: `created=2`, `updated=0`, `skipped=0`, `refused=0`
- second guarded apply: `created=0`, `updated=0`, `skipped=2`, `refused=0`
- finance table check: `patient_ledger_entries=2`, `invoices=0`,
  `payments=0`
- refusal checks: default/non-scratch target refused; report SHA256, expected
  total, and eligible-count mismatches refused

All proof artefacts are generated under pytest `tmp_path`. No committed fixture
contains patient or R4 data.

## Limits

This proof demonstrates only the CLI's guarded scratch write path and
idempotency against a deliberately bounded synthetic fixture. It does not prove
the full `1018`-row preserved opening-balance evidence, does not authorise any
live/default PMS write, and does not make finance import ready.

`finance_import_ready` remains `false`. Finance import remains out of scope.

## Next Slice

After PR #615, the next safe finance slice is the docs-only preserved-evidence
scratch execution plan in
`docs/r4/R4_FINANCE_OPENING_BALANCE_PRESERVED_EVIDENCE_SCRATCH_EXECUTION_PLAN.md`.
Any scratch apply execution against preserved evidence still requires explicit
instruction, a complete eligible-row artefact or deliberately bounded fixture,
and isolated scratch/test data only.
