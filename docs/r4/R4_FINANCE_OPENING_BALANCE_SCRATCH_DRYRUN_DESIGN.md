# R4 Finance Opening-Balance Scratch Dry-Run Design

Status date: 2026-05-05

Baseline: `master@b42f1e7ba8ecd893d299dc9fa1b05af1246f9455`

Safety: R4 SQL Server remains strictly read-only / SELECT-only. This document is
docs/design evidence only. It does not authorise finance import, finance staging
models, PMS DB writes, R4 writes, invoice creation, payment creation, balance
mutation, ledger creation, or live cutover.

## Inputs

This design uses:

- `docs/r4/R4_FINANCE_OPENING_BALANCE_SNAPSHOT_DESIGN.md`
- `docs/r4/R4_FINANCE_SIGN_CANCELLATION_ALLOCATION_POLICY.md`
- `docs/r4/R4_FINANCE_SOURCE_DISCOVERY.md`
- `docs/r4/R4_FINANCE_REFUND_ALLOCATION_CHARGE_REF_DECISION.md`
- `docs/r4/R4_FINANCE_INVOICE_CHARGE_REF_SOURCE_DECISION.md`
- `backend/app/services/r4_import/opening_balance_snapshot_plan.py`
- `backend/tests/r4_import/test_opening_balance_snapshot_plan.py`
- `backend/app/scripts/r4_opening_balance_reconciliation.py`
- `backend/app/services/r4_import/opening_balance_reconciliation.py`
- `/home/amir/dental-pms-opening-balance-live-proof/.run/opening_balance_reconciliation_20260504_083558/opening_balance_reconciliation.json`
- PMS patient, invoice, payment, and ledger models for design context only.

No live R4 query was needed for this design. No R4 access, PMS DB access, or
finance record write occurred in this slice.

## Current Evidence

The live opening-balance proof shows:

- `dbo.PatientStats` rows: `17012`
- non-zero balance rows: `1018`
- zero/no-action rows: `15994`
- total `Balance`: `-131342.13`
- `TreatmentBalance`: `-139692.13`
- `SundriesBalance`: `8350.00`
- `NHSBalance`: `2724.60`
- `PrivateBalance`: `-142416.73`
- `DPBBalance`: `0.00`
- `Balance = TreatmentBalance + SundriesBalance`: passed with `0`
  mismatches
- `TreatmentBalance = NHSBalance + PrivateBalance + DPBBalance`: passed with
  `0` mismatches
- aged debt total: `10329.82`
- rows with aged debt: `126`
- balance without aged debt: `892`
- aged debt with zero balance: `0`
- `PatientCode` present: `17012`
- blank/null `PatientCode`: `0`
- raw positive balances: `291`
- raw negative balances: `727`
- proof-only PMS directions: increase debt `291`, decrease debt or credit
  `727`, no action `15994`

PR #604 added the pure planning helper that accepts row-like `PatientStats`
data and supplied patient mapping evidence, preserves raw signs and values,
requires exact pence conversion, checks component consistency, and emits
fail-closed row decisions without DB access or importer wiring.

## Dry-Run Purpose

The scratch-only dry-run/report should prove that the merged
`opening_balance_snapshot_plan` helper can classify the live `PatientStats`
opening-balance population against scratch patient mappings without creating
finance records.

It comes before any write/apply path because the project still needs executable
evidence for:

- patient mapping closure for non-zero balance candidates;
- exact pence conversion at full population scale;
- component consistency at the same source timestamp used for the report;
- sign distribution and proof-only PMS direction summaries;
- refusal/manual-review reporting;
- a manifest that can later support idempotency, audit, and rollback design.

The dry-run is distinct from live/default finance migration. It must not create
or mutate PMS invoices, payments, balances, ledger rows, or patient finance
records. It should be treated as a report-only rehearsal for a later, separately
approved scratch apply design.

## Data Inputs

Required inputs:

- R4 `PatientStats` opening-balance source data, either from a preserved
  SELECT-only artefact or a future SELECT-only R4 query guarded by
  `R4_SQLSERVER_READONLY=true`.
- Patient mapping evidence from an isolated scratch/test context, or an
  explicit mapping artefact created from that context.
- The repo SHA and run parameters for the manifest.

Mapping requirement:

- all `1018` non-zero balance `PatientCode` values must map before the dry-run
  can be considered successful;
- all `17012` `PatientCode` values should be counted and reported so cutover
  mapping coverage is visible;
- the `15994` zero-balance rows are no-op rows and do not block the dry-run when
  unmapped, but they must remain visible in mapping/no-op summaries;
- if a zero-balance row has aged-debt metadata, the row remains no-op for
  financial effect and the metadata is reported for review.

Financial-effect input:

- only combined `PatientStats.Balance` is eligible for future financial effect;
- `TreatmentBalance`, `SundriesBalance`, `NHSBalance`, `PrivateBalance`, and
  `DPBBalance` are preserved as report and manifest metadata;
- aged debt fields are reconciliation and risk metadata only.

## Safety Gates

The dry-run/report phase must enforce these gates:

- scratch/test DB only if a future CLI reads mappings from a DB;
- default/live DB refusal before session creation if `DATABASE_URL` points at a
  normal live/default target;
- explicit dry-run mode;
- no finance writes;
- no ledger rows;
- no balance mutation;
- no invoice or payment creation;
- no apply command in this phase;
- source artefact path or SELECT-only source timestamp required;
- run manifest required;
- R4 read-only guard if R4 is queried;
- report refusal if any code path attempts to create, update, delete, or commit
  finance records.

If the first implementation reads mapping evidence from a file instead of a DB,
the DB guard should still be reported as not used, and the report must still
state that no PMS DB connection was opened.

## Dry-Run Algorithm

The dry-run/report should:

1. Load `PatientStats` rows from a preserved artefact or a SELECT-only R4
   source.
2. Load patient mapping evidence from scratch DB read-only access or an explicit
   mapping artefact.
3. Normalize row fields without changing raw values in the output.
4. Run every row through `plan_opening_balance_snapshot_row`.
5. Aggregate results with `summarize_opening_balance_snapshot_plan` or an
   equivalent report wrapper.
6. Emit decision totals for:
   - `eligible_opening_balance`
   - `no_op_zero_balance`
   - `missing_patient_mapping`
   - `invalid_patient_code`
   - `component_mismatch`
   - `invalid_amount`
   - `ambiguous_sign`
   - `manual_review`
   - `excluded`
7. Emit sign, pence, component, aged-debt, and patient-mapping summaries.
8. Emit bounded samples for eligible rows, no-op rows, and each refusal reason.
9. Produce no writes.

## Expected Report Sections

The JSON report should use stable top-level sections:

- `generated_at`
- `dry_run=true`
- `select_only=true` if R4 is queried
- `source_summary`
- `patient_mapping_summary`
- `eligibility_summary`
- `sign_summary`
- `component_consistency_summary`
- `aged_debt_summary`
- `refusal_reasons`
- `samples`
- `risks`
- `import_ready=false`
- `manifest`

The stdout summary should be concise and should include the output JSON path,
dry-run status, candidate counts, refusal counts, and `import_ready=false`.

## Success Criteria

The dry-run/report can be considered successful only if:

- the source totals match expected evidence or any drift is explicitly
  explained;
- `1018` non-zero balance candidates are present, unless a newer source run
  records explained drift;
- `15994` zero-balance rows are classified as no-op, unless a newer source run
  records explained drift;
- `Balance = TreatmentBalance + SundriesBalance` passes for all rows;
- `TreatmentBalance = NHSBalance + PrivateBalance + DPBBalance` passes for all
  rows;
- every non-zero balance candidate has a valid `PatientCode`;
- every non-zero balance candidate maps to one scratch patient;
- pence conversion is exact for every candidate;
- no candidate has ambiguous sign;
- report totals preserve raw positive, negative, and zero sign counts;
- the run proves no PMS DB finance writes, no R4 writes, no invoice/payment
  creation, no ledger rows, and no balance mutation.

The dry-run does not make `finance_import_ready=true`. It only proves that the
opening-balance snapshot population can be planned safely for a later scratch
apply decision.

## Failure and Refusal Criteria

The report must fail closed or mark the run unsuccessful for:

- any unmapped non-zero balance candidate;
- missing or blank `PatientCode` on a non-zero balance row;
- component mismatch;
- invalid or non-exact pence conversion;
- ambiguous or conflicting sign;
- unsupported source name;
- unexpected source total drift without an explicit source timestamp and
  explanation;
- default/live DB target;
- any attempted finance write path;
- any attempted invoice/payment/ledger/balance mutation;
- any R4 non-SELECT access.

Zero-balance rows remain no-op. They should not create finance records and
should not block the dry-run solely because they lack patient mapping.

## Artefacts

The dry-run/report should preserve:

- JSON report;
- stdout summary;
- stderr log;
- exit code;
- manifest.

The manifest should contain:

- repo SHA;
- source artefact path or R4 query timestamp;
- run timestamp;
- dry-run parameters;
- sample limits;
- mapping source description;
- DB target name or `not_used`;
- R4 read-only flag if R4 is queried;
- report output path;
- implementation version or script module path.

Later apply design can use the manifest shape for idempotency and rollback, but
this dry-run phase must not create rollback rows because it creates no finance
records.

## Future Scratch Proof Shape

The next implementation slice should be a backend-only opening-balance
dry-run/report CLI plus tests with no writes.

Recommended first shape:

- read a `PatientStats` artefact or SELECT-only source through explicit
  dry-run/report parameters;
- read patient mappings from a supplied mapping artefact, or from scratch DB
  read-only access if the implementation can prove default/live DB refusal
  before session creation;
- call the pure planning helper for each row;
- write JSON/stdout/stderr/exit-code artefacts;
- refuse apply/write options because no apply command exists in this phase;
- include tests for report shape, mapping failure, component failure, live DB
  refusal, and no session/write behaviour.

This is smaller and safer than a scratch apply proof because it exercises the
policy core and report contract before designing any finance write path.

## Import-Readiness Implication

`finance_import_ready` remains `false`.

Before any opening-balance write is considered, the project still needs:

1. dry-run/report CLI implementation and tests;
2. live/scratch dry-run evidence;
3. docs/evidence refresh after that run;
4. a later guarded scratch apply design;
5. explicit write model decision for adjustment or opening-balance ledger rows;
6. scratch apply/idempotency/rollback proof;
7. separate approval before any live/default finance migration.

Historical invoice import remains blocked because no explicit patient
invoice/statement/charge-ref source is proven. Invoice payment application
remains blocked because allocation charge refs are absent.

## Recommended Next Slice

Selected target: backend-only opening-balance dry-run/report CLI plus tests, no
writes.

Why this is the smallest justified next step:

- the policy helper is already merged and tested;
- the next risk is report composition, mapping summaries, refusal handling, and
  environment safety gates;
- no finance write model needs to be chosen to produce the report;
- no finance staging model is required;
- the resulting artefacts will support a later docs/evidence refresh and only
  then a guarded scratch apply design.

Likely files:

- `backend/app/services/r4_import/opening_balance_snapshot_dry_run.py`
- `backend/app/scripts/r4_opening_balance_snapshot_dry_run.py`
- `backend/tests/r4_import/test_opening_balance_snapshot_dry_run.py`

Likely validation:

- focused unit tests for the new report wrapper and CLI guards;
- existing opening-balance snapshot plan helper tests;
- existing opening-balance reconciliation tests if the source adapter is reused;
- `git diff --check`;
- no live R4 query unless explicitly running a SELECT-only evidence capture;
- no PMS DB writes;
- no finance records created or changed.

Backend-only/proof-only is likely for the next slice. Finance import, finance
staging models, default/live PMS finance writes, R4 writes, and frontend changes
remain out of scope.

## Open Questions and Risks

- Whether all `1018` non-zero balance candidates map cleanly in the current
  scratch patient mapping set.
- Whether source totals drift if the dry-run queries R4 instead of consuming the
  preserved 2026-05-04 artefact.
- Which cutover timestamp should anchor the future opening-balance snapshot.
- How to prevent double counting if later cash-event staging is also selected.
- Whether aged-debt metadata needs operator-facing reporting before any apply
  decision.
- What exact PMS write representation, if any, should be used in a later
  scratch apply design.

## Fail-Closed Rules

- No opening-balance write without patient mapping.
- No default/live DB write.
- No write without explicit confirmation token in a future apply phase.
- No write if component checks fail.
- No write without exact pence conversion.
- No write without sign clarity.
- No invoice/payment reconstruction from `PatientStats`.
- No invoice application without explicit invoice or charge refs.
- Zero balances remain no-op unless later proof requires metadata-only capture.
- Unknown source, mapping, sign, amount, or component semantics block import.
