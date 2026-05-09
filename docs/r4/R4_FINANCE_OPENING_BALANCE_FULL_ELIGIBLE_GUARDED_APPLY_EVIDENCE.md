# R4 Finance Opening-Balance Full Eligible-Row Guarded Apply Evidence

Status date: 2026-05-09

Baseline: `origin/master@0436a4ed39211e5ad63b8c77c876dfa41097fab1`

This evidence records the standing-authorised non-live scratch/test-only
guarded apply/write proof for the approved full eligible-row opening-balance
package. It proves guarded scratch/test ledger adjustment creation and
idempotency only.

This proof did not access R4, did not connect to a live/default PMS database,
did not use actual PMS Postgres, did not create invoices or payments, did not
run finance import, and did not perform invoice/payment/staging import.

The proof accessed the already-created non-repo full eligible-row artefact only
as needed to verify identity and construct the transient complete-row scratch
apply input. No raw artefact contents, patient-level row contents, patient
codes, row-level ledger references, exact non-repo storage paths, unredacted
DSNs, or secrets are committed.

`finance_import_ready=false`. Migration/import is not complete. Production
readiness is not established. Live finance import remains out of scope.

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
| Repo SHA | `0436a4ed39211e5ad63b8c77c876dfa41097fab1` |

The validation/no-write evidence and owner sign-off are recorded in:

- `docs/r4/R4_FINANCE_OPENING_BALANCE_FULL_ELIGIBLE_VALIDATION_NOWRITE_EVIDENCE.md`
- `docs/r4/R4_FINANCE_OPENING_BALANCE_FULL_ELIGIBLE_VALIDATION_NOWRITE_SIGNOFF.md`

The validation/no-write sign-off cleared this proof as the next non-live gate.
This evidence does not authorise live/default PMS DB writes, actual PMS
Postgres writes, production execution, live finance import, or
invoice/payment/staging import.

## Target And Command Guards

Target classification:

- local isolated SQLite scratch/test only;
- target name included explicit `scratch` and `test` markers;
- not live/default/production-looking;
- not actual PMS Postgres;
- scratch/test DB committed: no.

Scratch setup used one synthetic scratch operator and synthetic scratch patient
rows required only for local foreign-key consistency. No real patient names,
DOBs, addresses, phone numbers, emails, clinical details, or patient-level
contents were committed.

Redacted guarded apply command shape for both runs:

```text
PYTHONPATH=backend <scratch-apply-venv-python> \
  -m app.scripts.r4_opening_balance_guarded_scratch_apply \
  --dry-run-report-json <local-transient-full-eligible-apply-input-json> \
  --database-url '<local-isolated-sqlite-scratch-test-dsn-redacted>' \
  --manifest-id r4ob-full-eligible-20260509-000001 \
  --output-json <local-safe-guarded-apply-output-json> \
  --expected-report-sha256 91bc8542c0a18aed36e71854d6e69e6a0730af930942d0562b4a4cf64089e8ac \
  --expected-total-balance -131187.13 \
  --expected-eligible-count 1018 \
  --expected-repo-sha 0436a4ed39211e5ad63b8c77c876dfa41097fab1 \
  --apply \
  --confirm SCRATCH_OPENING_BALANCE_APPLY \
  --actor-id <scratch-proof-actor-id>
```

The proof used:

- `--apply`: yes;
- exact `--confirm SCRATCH_OPENING_BALANCE_APPLY`: yes;
- `--actor-id`: yes.

## Evidence Files

The following evidence files are local ignored `.run` artefacts and are not
committed. They are listed only as redacted relative evidence handles.

| Evidence | SHA256 |
| --- | --- |
| transient full eligible guarded apply input JSON | `91bc8542c0a18aed36e71854d6e69e6a0730af930942d0562b4a4cf64089e8ac` |
| first guarded apply output JSON | `faa1e43d6c960bf0a9a54ae3abacbbfa469eecf658ff3e2a741c5e8d19a03b42` |
| first guarded apply stdout JSON | `0a75cf1c7bd5430c1116ac4e5ff7fb8c4b5e4413c4fa35401b85e72f461a98dd` |
| second-run idempotency output JSON | `f6aa65f54e85357c2e4d9766299079831930d6ff1ec231c133a4a12c6ee12316` |
| second-run idempotency stdout JSON | `fbd9f2fe23e1528096844298726bbf5b1d60f4eaf5b8c3de1516aa4ac027596c` |
| local query verification JSON | `40dff20545a2ca8ac990ef077423114b95a80d441858aeb6c6910d6bcf59593c` |

## First Guarded Apply Result

Result: passed.

- exit code: `0`;
- `apply_requested=true`;
- `row_source_complete=true`;
- `finance_import_ready=false`;
- before counts:
  - `patient_ledger_entries=0`;
  - `invoices=0`;
  - `payments=0`;
- after counts:
  - `patient_ledger_entries=1018`;
  - `invoices=0`;
  - `payments=0`;
- result counts:
  - `created=1018`;
  - `updated=0`;
  - `skipped=0`;
  - `refused=15999`.

The `refused=15999` value is the guarded plan refusal count for excluded/no-op
source rows. It did not create refusal rows.

The first run created only local isolated scratch/test `PatientLedgerEntry`
adjustment rows for eligible opening-balance rows. It created no invoices,
payments, staging/import records, live finance records, or production records.

## Second-Run Idempotency Result

Result: passed.

- exit code: `0`;
- `apply_requested=true`;
- `row_source_complete=true`;
- `finance_import_ready=false`;
- before counts:
  - `patient_ledger_entries=1018`;
  - `invoices=0`;
  - `payments=0`;
- after counts:
  - `patient_ledger_entries=1018`;
  - `invoices=0`;
  - `payments=0`;
- result counts:
  - `created=0`;
  - `updated=0`;
  - `skipped=1018`;
  - `refused=15999`;
- duplicate protection: passed.

The second run recognised the existing manifest-scoped scratch/test rows and
created no duplicates.

## Local Query Verification

The local scratch/test query verification recorded only aggregate values:

- manifest-scoped ledger row count: `1018`;
- ledger total pence: `-13118713`;
- ledger total decimal: `-131187.13`;
- unique manifest-scoped reference count: `1018`;
- duplicate reference count: `0`;
- non-adjustment manifest rows: `0`;
- manifest rows linked to invoices: `0`;
- invoice count: `0`;
- payment count: `0`;
- staging/import table count: `0`;
- staging/import row count: `0`;
- patient-level contents in query output: no;
- raw rows in query output: no;
- row-level references in query output: no.

## Safety Outcomes

| Guard | Result |
| --- | --- |
| R4 access during this slice | No |
| Real artefact access during this slice | Yes, limited to authorised non-repo identity checks and transient apply input construction. |
| Real patient data used during this slice | Yes, limited to authorised non-repo scratch/test proof input handling. |
| Patient-level contents committed | No |
| Raw artefact contents committed | No |
| PMS DB connection | Yes, local isolated SQLite scratch/test only. |
| Local scratch SQLite DB opened or queried | Yes, local isolated scratch/test only. |
| DB writes | Yes, local isolated scratch/test only. |
| Live/default PMS DB writes | No |
| Actual PMS Postgres writes | No |
| Guarded scratch apply run/rerun | Yes, first guarded apply and second-run idempotency proof. |
| CLI validation/no-write run | No |
| `--apply` used | Yes |
| `--confirm` used | Yes, exact `SCRATCH_OPENING_BALANCE_APPLY`. |
| `--actor-id` used | Yes |
| Scratch-test finance records created/changed | Yes, exactly `1018` local isolated scratch/test `PatientLedgerEntry` adjustment rows in the first run; the second run created none. |
| Live finance records created/changed | No |
| Finance import started | No |
| Invoice/payment/staging import | No |

## Cleanup And Rollback Boundary

The scratch/test target is disposable local evidence. Cleanup is limited to
deleting the ignored local `.run` scratch/test artefacts, or deleting only the
manifest-scoped scratch/test rows from that isolated target if local row-level
rollback is needed for additional local proof work.

No live/default PMS rollback is applicable because no live/default PMS DB,
actual PMS Postgres, production execution, or live finance import was used.

## Non-Authorisation

This guarded apply/write evidence does not authorise:

- live/default PMS DB writes;
- actual PMS Postgres writes;
- production execution;
- live finance import;
- invoice/payment/staging import;
- committing raw R4 artefact contents;
- committing patient names, dates of birth, addresses, phone numbers, emails,
  clinical details, patient codes, row-level ledger references, exact non-repo
  storage paths, or unredacted DSNs/secrets.

This proof is not production readiness. It does not mark migration/import
complete. Any live finance import decision remains separate and unauthorised.

## Next Gate

The next gate is owner review/sign-off of this guarded apply/write proof
evidence. Live/default PMS DB writes, actual PMS Postgres writes, production
execution, live finance import, invoice/payment/staging import, and committing
raw artefact or patient-level contents remain unauthorised.
