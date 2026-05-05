# R4 Finance Opening-Balance Snapshot Design

Status date: 2026-05-05

Baseline: `master@f9920265c197bbc009d00038e32b10fc8994c216`

Safety: R4 SQL Server remains strictly read-only / SELECT-only. This document is
design evidence only. It does not authorise finance import, finance staging
models, PMS DB writes, R4 writes, invoice creation, payment creation, balance
mutation, ledger creation, or live cutover.

## Inputs

This design uses:

- `docs/STATUS.md`
- `docs/R4_MIGRATION_READINESS.md`
- `docs/r4/R4_FINANCE_SOURCE_DISCOVERY.md`
- `docs/r4/R4_FINANCE_SIGN_CANCELLATION_ALLOCATION_POLICY.md`
- `docs/r4/R4_FINANCE_REFUND_ALLOCATION_CHARGE_REF_DECISION.md`
- `docs/r4/R4_FINANCE_INVOICE_CHARGE_REF_SOURCE_DECISION.md`
- `/home/amir/dental-pms-opening-balance-live-proof/.run/opening_balance_reconciliation_20260504_083558/opening_balance_reconciliation.json`
- `/home/amir/dental-pms-finance-inventory-proof/.run/finance_inventory_20260503_201724/finance_inventory.json`
- `/home/amir/dental-pms-finance-cancellation-allocation-proof/.run/finance_cancellation_allocation_reconciliation_20260504_140810/finance_cancellation_allocation_reconciliation.json`
- `/home/amir/dental-pms-finance-cash-event-live-proof/.run/finance_cash_event_staging_20260504_191704/finance_cash_event_staging.json`
- Current PMS invoice, payment, patient ledger, and finance-report models for
  design context.

No live R4 query was run for this design. No PMS DB query or write was run.

## Evidence Summary

The live opening-balance proof reported:

- `PatientStats` rows: `17012`
- non-zero balance rows: `1018`
- zero/no-action rows: `15994`
- total `Balance`: `-131342.13`
- `TreatmentBalance`: `-139692.13`
- `SundriesBalance`: `8350.00`
- `NHSBalance`: `2724.60`
- `PrivateBalance`: `-142416.73`
- `DPBBalance`: `0.00`
- `Balance = TreatmentBalance + SundriesBalance`: passed with `0` mismatches
- `TreatmentBalance = NHSBalance + PrivateBalance + DPBBalance`: passed with
  `0` mismatches
- aged-debt total: `10329.82`
- rows with aged debt: `126`
- rows with balance but no aged debt: `892`
- rows with aged debt but zero balance: `0`
- `PatientCode` present: `17012`
- blank/null `PatientCode`: `0`
- distinct `PatientCode`: `17012`
- raw positive balance rows: `291`
- raw negative balance rows: `727`
- proof-only PMS directions: increase debt `291`, decrease debt `727`, no
  change `15994`

The later invoice/charge-ref source decision found no explicit patient
invoice/statement source and no usable allocation charge refs. Historical
invoice import and invoice payment application remain blocked.

## PMS Finance Context

Current PMS finance state is ledger-derived:

- `PatientLedgerEntry` supports `charge`, `payment`, and `adjustment` entries.
- Patient balances and outstanding reports sum `PatientLedgerEntry.amount_pence`.
- Payments are represented as negative ledger entries in current route/backfill
  behaviour.
- PMS `Payment` rows require an invoice.
- PMS invoice payment application requires a reliable invoice relationship.

Therefore, an opening-balance snapshot must not use `Payment` rows, invoice
payments, or reconstructed invoice lines. If a later scratch proof is
authorised to write anything, the narrowest compatible shape is one
manifest-scoped patient ledger `adjustment` row per eligible non-zero mapped
patient, with no `related_invoice_id`.

This is a future-proof recommendation only. This slice does not implement it.

## Plan Helper Continuity

PR #604 completed the first recommended proof phase as backend-only,
pure-helper/test-only work:

- added `backend/app/services/r4_import/opening_balance_snapshot_plan.py`;
- added `backend/tests/r4_import/test_opening_balance_snapshot_plan.py`;
- kept importer behaviour unchanged;
- added no finance import or finance staging models;
- created or changed no invoices, payments, balances, ledger rows, or finance
  records;
- performed no PMS DB writes;
- performed no R4 access or writes.

The helper accepts row-like `PatientStats` data and supplied patient mapping,
then emits deterministic plan decisions without DB access. It preserves raw
R4 signs and values, converts exact pence amounts only, requires patient mapping
for non-zero balances, keeps zero balances as no-op rows, checks component
consistency, and fails closed for missing PatientCode, missing mapping,
component mismatch, invalid/non-pence amounts, explicit sign conflict, and
unsupported sources.

## Source Decision

`dbo.PatientStats` is the candidate opening-balance snapshot source because it
is the only currently proven source with:

- one row per discovered patient code in current evidence;
- direct current balance fields;
- treatment, sundry, NHS, private, and DPB component fields;
- aged-debt fields;
- `0` component mismatches in the live proof;
- no blank/null patient codes in the live proof.

`PatientStats` is not row-level invoice/payment truth. It is a current snapshot.
It does not prove invoice numbers, issue dates, paid status, invoice lines,
payment allocation, or historical ledger chronology.

Other finance sources must not be used to reconstruct opening balances directly:

- `Transactions` remains treatment/charge evidence and reconciliation input, not
  invoice truth.
- `vwPayments` and `Adjustments` remain cash-event and cancellation evidence,
  not balance seed rows.
- `PaymentAllocations` and `vwAllocatedPayments` remain reconciliation-only
  because charge refs are absent.
- `PatientStats` plus historical charges/payments could double count unless a
  future cutover design explicitly prevents it.

## Snapshot Semantics

The future opening balance should represent the patient account balance at a
defined cutover snapshot time.

Financial effect:

- use the combined `PatientStats.Balance` only;
- one eligible non-zero patient balance becomes at most one opening-balance
  adjustment in a scratch-only proof;
- zero balances remain no-op rows.

Metadata and reconciliation evidence:

- preserve raw `Balance`, `TreatmentBalance`, `SundriesBalance`, `NHSBalance`,
  `PrivateBalance`, `DPBBalance`, aged-debt fields, raw sign, proof direction,
  and source artefact path in a run manifest;
- do not create separate PMS ledger rows for treatment, sundry, NHS, private,
  DPB, or aged-debt component values;
- use component values to verify and explain the combined balance only;
- keep aged-debt fields reconciliation/reporting-only unless a later design
  creates a dedicated aged-debt reporting model.

Aged debt policy:

- aged debt is not a ledger source;
- aged-debt totals do not need to equal total balance;
- `892` non-zero-balance rows without aged debt remain eligible for snapshot
  proof but must be risk-flagged;
- any future row with aged debt and zero balance must be manual-review until
  explained.

## Sign Policy

Raw R4 signs must be preserved.

Current proof-only interpretation:

- positive `PatientStats.Balance` means probable PMS debt increase;
- negative `PatientStats.Balance` means probable PMS debt decrease or patient
  credit;
- zero balance means no action.

Future pence mapping, if authorised in scratch:

- positive R4 balance maps to positive PMS `amount_pence`;
- negative R4 balance maps to negative PMS `amount_pence`;
- zero R4 balance maps to no row;
- use exact money-to-pence conversion and fail if the value cannot be converted
  exactly to pence.

No blind sign inversion is allowed. If statement examples, independent
reconciliation, or patient-level evidence contradict the current sign
interpretation, the row and proof must fail closed rather than invert signs.

Fail-closed sign cases:

- missing `Balance`;
- non-numeric `Balance`;
- amount not exactly representable in pence;
- conflicting raw sign and proposed PMS direction;
- component mismatch;
- unknown source row.

## Patient Linkage Policy

`PatientCode` is mandatory for any future opening-balance action.

Future proof requirements:

- report mapping for all `17012` `PatientStats` rows;
- require all non-zero-balance candidates to map before any scratch apply;
- treat the `1018` non-zero-balance candidates as the write-blocking mapping
  set;
- report zero-balance unmapped patients separately, but do not write rows for
  them;
- before live/default finance migration, full patient mapping closure remains
  part of broader cutover readiness even if zero-balance rows are no-op.

Missing or unmapped non-zero candidates fail the apply gate. Missing
`PatientCode` rows are excluded/manual-review and must not produce PMS finance
records.

## Eligibility Policy

Eligible for future opening-balance snapshot proof:

- `PatientStats` rows only;
- non-zero `Balance`;
- present `PatientCode`;
- mapped PMS patient in the scratch target;
- passed component checks;
- exactly convertible pence amount;
- raw sign classified without ambiguity.

No-op:

- zero-balance rows with no contradictory aged-debt signal.

Manual-review or fail:

- missing or unmapped non-zero patient code;
- component mismatch;
- aged debt with zero balance;
- non-numeric or non-pence amount;
- unknown sign;
- duplicate `PatientCode`;
- any attempt to combine the snapshot with historic invoice/payment rows without
  a double-counting proof.

Positive and negative balances are both eligible if all gates pass. Positive
rows increase debt; negative rows decrease debt or represent credit.

## Future Scratch Proof Design

The next executable proof must be scratch-only and fail closed.

Required gates:

- scratch/test DB only;
- default/live DB refusal before session/open;
- explicit confirmation token for any scratch apply mode;
- dry-run report before any apply;
- immutable run manifest ID;
- before/after counts for `patient_ledger_entries`, `invoices`, and `payments`;
- guarantee `invoices` and `payments` counts do not change;
- idempotency rerun that creates `0` new rows for the same manifest;
- rollback artefact and manifest-scoped rollback command for scratch only;
- no R4 writes;
- no default/live PMS DB writes.

Recommended proof phases:

1. Pure planning helper and unit tests. Completed by PR #604. It converts
   row-like `PatientStats` data plus mapping evidence into deterministic plan
   rows and refusal reasons with no DB and no R4 access.
2. Scratch dry-run/report design. Define the report shape, scratch/default DB
   refusal gates, mapping closure evidence, manifest fields, idempotency
   expectations, and rollback evidence before implementing the report.
3. Scratch dry-run/report. Read mapped patients from an isolated scratch DB and
   produce a plan, but write nothing.
4. Scratch apply transcript, only after a separate decision. Create one
   manifest-scoped `PatientLedgerEntry` adjustment per eligible non-zero mapped
   patient, with no invoice/payment rows and no `related_invoice_id`.

No future proof should write default/live PMS data until the scratch transcript,
rollback, idempotency, and operator signoff are complete.

## Audit and Rollback Policy

Any future run manifest must preserve:

- R4 `PatientCode`;
- mapped PMS `patient_id`;
- raw `Balance`;
- raw component fields;
- raw aged-debt fields;
- raw sign;
- proof-only PMS direction;
- planned `amount_pence`;
- source artefact path;
- source snapshot timestamp or run timestamp;
- import/proof run ID;
- operator confirmation token hash or identifier;
- before/after ledger, invoice, payment, and patient counts;
- refusal and manual-review reason codes.

Current `PatientLedgerEntry` has `reference`, `note`, `related_invoice_id`, and
audit timestamps, but no dedicated import-run foreign key. A scratch apply can
use a strict reference prefix plus manifest ID for rollback proof. A live design
should consider stronger manifest linkage before any default/live finance write.

Rollback requirements:

- scratch rollback must delete only rows created by the exact manifest;
- rollback must prove before/after counts and remaining manifest rows `0`;
- rollback must not touch manually entered ledger rows;
- live/default rollback requires a separate operator runbook, backup point, and
  explicit approval before any implementation.

## Import-Readiness Implication

This design does not make finance import ready.

Opening-balance snapshot is safer than historical invoice import because:

- no explicit invoice/statement source is proven;
- allocation charge refs are absent;
- payment application to invoices remains blocked;
- PatientStats component checks are internally consistent.

Still blocked before any live/default finance migration:

- patient mapping proof for non-zero candidates;
- PR #607 dry-run/report tooling execution against real `PatientStats` rows and
  scratch mapping evidence;
- scratch dry-run/report evidence transcript;
- scratch apply/idempotency/rollback transcript, if writes are later selected;
- cutover timestamp and double-counting policy;
- payment/refund/credit handling policy for post-cutover or staged cash events;
- operator approval and backup/rollback plan.

`finance_import_ready` remains `false`.

## Recommended Next Slice

Selected target: scratch-only dry-run execution evidence using the real
`PatientStats` row artefact and scratch mapping evidence, no writes.

Why this is the smallest justified next step:

- PR #604 has completed deterministic row-level eligibility, sign, pence
  conversion, patient mapping, component consistency, and refusal logic;
- `docs/r4/R4_FINANCE_OPENING_BALANCE_SCRATCH_DRYRUN_DESIGN.md` defines how a
  scratch-only dry-run/report consumes that helper without writing finance
  records;
- PR #607 has completed the backend-only report composition, mapping summaries,
  refusal reasons, safety gates, and artefact shape with no R4 source mode, no
  DB write path, and no apply mode;
- the next risk is proving the report against real `PatientStats` rows and
  scratch mapping evidence before any scratch apply design.

Likely files:

- no repo code files for the execution itself;
- a later docs/evidence refresh if the scratch-only run succeeds.

Likely validation:

- command exit status, JSON parse/top-level report shape, and manifest fields;
- `import_ready=false`, manifest `no_write=true`, and `apply_mode=false`;
- `git status --short`;
- no live R4 access unless explicitly capturing a SELECT-only source artefact;
- no R4 writes;
- no PMS DB writes;
- no finance records created or changed.

Backend-only/proof-only is likely for the next slice. It must not add finance
staging models, importer wiring, PMS write paths, R4 writes, or finance records.

## Fail-Closed Rules

- No opening-balance write without mapped patient identity.
- No default/live DB write.
- No write without explicit confirmation token.
- No write if component checks fail.
- No write if pence conversion is ambiguous.
- No blind sign inversion.
- No invoice/payment reconstruction from `PatientStats`.
- No invoice, payment, or allocation application from this snapshot.
- No zero-balance ledger row unless a later proof explicitly requires metadata.
- No combination with historic cash events without a double-counting proof.
- Unknown source, status, amount, sign, or linkage semantics block import.

## Stop Point

This document is a design stop point. It does not implement finance import,
finance staging models, opening-balance writes, invoice creation, payment
creation, balance mutation, ledger creation, R4 writes, or PMS DB writes.
