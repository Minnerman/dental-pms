# R4 Finance Refund, Allocation, and Charge-Ref Decision

Status date: 2026-05-04

Baseline: `master@dd28ea7c91aec28c33a321b6ebbc95e6c6d665af`

Safety: R4 SQL Server remains strictly read-only / SELECT-only. This decision is
design evidence only. It does not authorise finance import, finance staging
models, PMS DB writes, R4 writes, invoice creation, payment creation, balance
mutation, ledger creation, or live cutover.

## Inputs

This decision uses:

- `docs/R4_MIGRATION_READINESS.md`
- `docs/r4/R4_FINANCE_SOURCE_DISCOVERY.md`
- `docs/r4/R4_FINANCE_SIGN_CANCELLATION_ALLOCATION_POLICY.md`
- `/home/amir/dental-pms-finance-inventory-proof/.run/finance_inventory_20260503_201724/finance_inventory.json`
- `/home/amir/dental-pms-opening-balance-live-proof/.run/opening_balance_reconciliation_20260504_083558/opening_balance_reconciliation.json`
- `/home/amir/dental-pms-finance-cancellation-allocation-proof/.run/finance_cancellation_allocation_reconciliation_20260504_140810/finance_cancellation_allocation_reconciliation.json`
- `/home/amir/dental-pms-finance-cash-event-live-proof/.run/finance_cash_event_staging_20260504_191704/finance_cash_event_staging.json`
- `backend/app/services/r4_import/finance_classification_policy.py`
- `backend/app/scripts/r4_finance_inventory.py`
- `backend/app/scripts/r4_finance_cancellation_allocation_reconciliation.py`
- Current PMS finance code for invoices, payments, patient ledger entries, and
  payment receipts.

No live R4 query was needed for this decision. No R4 access, PMS DB access, or
finance record write occurred in this slice.

## Evidence Summary

Cancellation evidence:

- `vwPayments` cancelled rows: `1032`
- `vwPayments` cancelled total: `-90633.58`
- `Adjustments.CancellationOf` rows: `460`
- original `Adjustments` rows found: `460`
- original `Adjustments` rows missing: `0`
- patient mismatches: `0`
- paired net amount: `0.00`

Refund/allocation evidence:

- `vwPayments` refunds: `110`
- `vwPayments` refund total: `18563.48`
- `PaymentAllocations` refunds: `795`
- `PaymentAllocations` refund total: `-53401.40`
- matching allocation refunds by `PaymentID` / `RefId`: `62`
- allocation refunds without `vwPayments` refund: `733`
- `vwPayments` refunds without allocation refund: `48`

Advanced payment, credit, and allocation evidence:

- advanced payment allocations: `2335`
- `vwPayments` credits: `6513`
- linked allocations: `3130`
- charge refs: `0`
- missing charge refs: `3130`

Live cash-event staging proof evidence:

- `vwPayments` rows considered: `44906`
- `Adjustments` rows considered: `47732`
- eligible cash-event candidates: `42914`
- manual-review rows: `47794`
- excluded rows: `0`
- cancellation/reversal rows: `1930`
- payment candidates: `36859`
- refund candidates: `104`
- credit candidates: `5951`
- missing patient/date/amount/zero amount counts: `0`
- method-family counts: cash `25678`, cheque `10928`, card `6946`,
  credit/overpayment `1344`, other/unknown `10`
- classification rows: candidate `42914`, manual-review `49724`
- import-readiness gate: `finance_import_ready=false`

Opening balance evidence remains relevant but separate:

- `PatientStats` component checks passed with `0` mismatches.
- `PatientStats` is a balance and aged-debt snapshot source, not row-level
  invoice/payment truth.

Current PMS finance constraints:

- `Payment` rows require an `Invoice`.
- `PatientLedgerEntry` supports `charge`, `payment`, and `adjustment`.
- Positive ledger amounts increase debt; payments are negative ledger entries.
- Invoice payment application requires a reliable PMS invoice or related invoice
  reference.

## Cancellation Semantics Decision

`Adjustments.CancellationOf` rows can be paired reliably for the current live R4
data set. The proof found all `460` originals, no patient mismatches, no missing
originals, cancellation dates after or equal to the original rows, and paired net
amount `0.00`.

Decision:

- Paired `Adjustments.CancellationOf` rows are not future import candidates by
  themselves.
- A future cash-event proof may use paired cancellation rows as reversal
  metadata and exclusion evidence.
- A future import must not create independent PMS finance records for both sides
  of a paired cancellation.
- Until a later import-readiness proof chooses a representation, paired
  cancellation rows remain excluded from candidate cash events or manual-review
  reconciliation rows.

This does not cover every cancelled row exposed by `vwPayments`. `vwPayments`
reports `1032` cancelled rows while `Adjustments.CancellationOf` reports `460`
paired cancellation rows. The remaining `vwPayments.IsCancelled` rows are not
proven safe for import. They remain manual-review or excluded until a later
proof maps the view flags to base adjustment status and cancellation pairs.

## Refund Source Semantics Decision

`vwPayments` is the safer first source for future refund cash-event proof because
it exposes `RefId`, patient, date, amount, type, refund/payment/credit flags,
cancellation flag, payment type descriptions, and adjustment descriptions.
`Adjustments` must remain the base-table cross-check for stable keys, status,
and cancellation pairing.

`PaymentAllocations` and `vwAllocatedPayments` refund rows are not treated as
actual refund transaction truth. They are allocation and reconciliation rows.
The evidence shows a different grain:

- allocation refunds `795` versus `vwPayments` refunds `110`;
- only `62` allocation refunds match `vwPayments` refunds;
- `733` allocation refunds have no matching `vwPayments` refund;
- `48` `vwPayments` refunds have no allocation refund;
- all allocation refund rows lack charge refs.

Decision:

- The `62` matched allocation refunds are reconciliation evidence for the
  corresponding `vwPayments` refund rows, not duplicate import rows.
- The `733` allocation refunds without a `vwPayments` refund remain
  reconciliation-only/manual-review. They must not create PMS refunds.
- The `48` `vwPayments` refunds without allocation rows can be considered
  candidate refund cash events in a later SELECT-only cash-event staging proof,
  but they are not import-ready.
- Future refund import proof should start from `vwPayments` plus `Adjustments`,
  not `PaymentAllocations`.

## Allocation Semantics Decision

`PaymentAllocations` and `vwAllocatedPayments` remain reconciliation-only.

The allocation evidence is not sufficient for PMS invoice application:

- all `3130` allocation rows have linked payment IDs;
- charge refs are `0`;
- missing charge refs are `3130`;
- allocation rows are old-only in current inventory, ending in 2017;
- refund and advanced-payment allocation counts do not align with `vwPayments`
  refund and credit counts.

Decision:

- Allocation rows cannot be used to apply payments to PMS invoices.
- Allocation rows cannot create PMS invoices, invoice payments, refunds, or
  ledger entries.
- Allocation import is deferred until an explicit charge/invoice reference
  source is discovered and proven, or until the project deliberately chooses an
  opening-balance-only / cash-event-only migration that does not reconstruct
  historic invoice application.
- Charge-ref discovery remains a blocker for any historical invoice application
  path.

## Credit and Advanced Payment Semantics Decision

`vwPayments` credits and allocation advanced-payment rows are not the same
population:

- `vwPayments` credits: `6513`
- advanced payment allocations: `2335`

Decision:

- `vwPayments` credits are candidate account-credit or over-payment cash-event
  rows for a later SELECT-only cash-event staging proof.
- `PaymentAllocations.IsAdvancedPayment` rows remain reconciliation-only until
  their relationship to `vwPayments` credits, PatientStats credit balances, and
  any explicit invoice/charge references is proven.
- Do not import advanced allocation rows as patient credits, deposits, payments,
  or ledger rows.
- Credit/deposit semantics require lookup mapping and patient-level
  reconciliation before any import-readiness decision.

## Import-Readiness Implication

No finance import can proceed safely from the current evidence.

The safe conclusions are:

- `PatientStats` can support opening balance snapshot proof, not row-level
  ledger import.
- `vwPayments` plus `Adjustments` are the best future cash-event proof sources
  for payment, refund, and credit candidates.
- `PaymentAllocations` and `vwAllocatedPayments` are reconciliation-only.
- `Transactions` remain treatment/clinical charge evidence, not invoice truth.
- Historical invoice application is blocked by missing charge refs and no
  confirmed invoice/statement source.

The project should not implement finance import, staging models, or PMS finance
write paths until a later proof produces candidate rows, exclusions, and
reconciliation totals without unresolved cancellation/refund/allocation
ambiguity.

## Fail-Closed Rules

These rules supersede any weaker interpretation:

- Unknown cancellation, refund, credit, or allocation semantics go
  manual-review or excluded.
- `vwPayments.IsCancelled` rows are excluded/manual-review unless paired and
  explicitly allowed by a future import-readiness proof.
- `Adjustments.CancellationOf` rows are reversal metadata or excluded
  reconciliation evidence, not independent import rows.
- Unmatched allocation refunds do not create PMS refund records.
- `vwPayments` refunds without allocation rows may be proof candidates only, not
  import-ready rows.
- Allocation rows without charge refs cannot apply payments to invoices.
- Allocation rows do not create invoices, payments, refunds, credits, or ledger
  entries.
- `Transactions` are not invoice truth.
- `PatientStats` is snapshot/reconciliation evidence, not row-level ledger
  truth.
- Scheme/classification rows remain reporting/reference only.
- No default/live PMS finance write path is authorised by this decision.

## Open Questions and Risks

- Whether `vwPayments.IsCancelled` rows outside `Adjustments.CancellationOf`
  have a separate pairing or status mechanism.
- Whether unmatched allocation refund rows are historic allocation artefacts,
  advanced-payment movement, over-payment state, or a different reporting grain.
- Whether the `48` `vwPayments` refunds without allocation rows are complete
  cash-refund events or require another reference source.
- Whether an explicit R4 invoice, statement, or charge-ref source exists outside
  the currently proven sources.
- The invoice/charge-ref source decision in
  `docs/r4/R4_FINANCE_INVOICE_CHARGE_REF_SOURCE_DECISION.md` confirms no
  explicit patient invoice/statement source or usable allocation charge refs are
  proven in the current evidence.
- Whether cash-event staging plus opening balance snapshot would double count
  without a cutover date and balance reconciliation rule.
- Whether payment method and credit type lookups can be collapsed into current
  PMS payment method categories without losing cash-up reporting fidelity.

## Recommended Next Slice

Selected target: opening-balance snapshot import design/proof before any finance
import.

Why this is the smallest justified next step:

- The live cash-event proof has completed and reports
  `finance_import_ready=false`.
- The invoice/charge-ref source decision confirms no explicit patient
  invoice/statement source and no usable allocation charge refs.
- `vwPayments` is the clearest payment/refund/credit candidate source.
- `PaymentAllocations` cannot apply payments to invoices because charge refs are
  absent.
- Opening-balance snapshot design is the smallest path that does not require
  historical invoice reconstruction, but it must still prove double-counting and
  cutover policy before import.

Likely files:

- docs/design-only decision first;
- no implementation files unless inspection proves a narrow proof helper is
  required;
- if a proof is later needed, keep it backend-only, SELECT-only, and
  proof-report-only.

Likely validation:

- `git diff --check`
- no R4 writes, no PMS DB writes, no finance records created or changed

Docs/design-only is expected. The next slice must not create finance staging
models or import finance records.
