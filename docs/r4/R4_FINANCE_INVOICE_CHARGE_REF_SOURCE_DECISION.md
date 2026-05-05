# R4 Finance Invoice and Charge-Ref Source Decision

Status date: 2026-05-04

Baseline: `master@dd28ea7c91aec28c33a321b6ebbc95e6c6d665af`

Safety: R4 SQL Server remains strictly read-only / SELECT-only. This decision is
design and source-discovery evidence only. It does not authorise finance import,
finance staging models, PMS DB writes, R4 writes, invoice creation, payment
creation, balance mutation, ledger creation, or live cutover.

## Inputs

This decision uses:

- `docs/STATUS.md`
- `docs/R4_MIGRATION_READINESS.md`
- `docs/r4/R4_FINANCE_SOURCE_DISCOVERY.md`
- `docs/r4/R4_FINANCE_SIGN_CANCELLATION_ALLOCATION_POLICY.md`
- `docs/r4/R4_FINANCE_REFUND_ALLOCATION_CHARGE_REF_DECISION.md`
- `/home/amir/dental-pms-finance-inventory-proof/.run/finance_inventory_20260503_201724/finance_inventory.json`
- `/home/amir/dental-pms-opening-balance-live-proof/.run/opening_balance_reconciliation_20260504_083558/opening_balance_reconciliation.json`
- `/home/amir/dental-pms-finance-cancellation-allocation-proof/.run/finance_cancellation_allocation_reconciliation_20260504_140810/finance_cancellation_allocation_reconciliation.json`
- `/home/amir/dental-pms-finance-cash-event-live-proof/.run/finance_cash_event_staging_20260504_191704/finance_cash_event_staging.json`
- `backend/app/scripts/r4_finance_inventory.py`
- `backend/app/scripts/r4_finance_cancellation_allocation_reconciliation.py`
- `backend/app/scripts/r4_finance_cash_event_staging.py`
- `backend/app/services/r4_import/finance_classification_policy.py`
- Current PMS invoice, payment, and patient ledger models for mapping context.

A live SELECT-only metadata/source-discovery check was run for this decision. It
used only `INFORMATION_SCHEMA` table/column searches plus targeted
`COUNT`/`MIN`/`MAX`/`SUM` aggregate checks against suspected finance sources. It
did not dump broad row sets, connect to the PMS DB, or write to R4.

## Existing Evidence

The existing inventory and proofs already show the following:

- `dbo.PatientStats` is the high-confidence balance and aged-debt snapshot
  source. It is not row-level invoice or payment truth.
- `dbo.vwPayments` and `dbo.Adjustments` are the best payment, refund, credit,
  and cancellation candidate sources.
- `dbo.Transactions` is treatment/clinical charge evidence and reconciliation
  input. It is not invoice truth by itself.
- `dbo.PaymentAllocations` and `dbo.vwAllocatedPayments` are allocation,
  refund, and advanced-payment reconciliation inputs.
- The live allocation proof found linked allocations `3130`, charge refs `0`,
  and missing charge refs `3130`.
- The live cash-event proof found `42914` eligible cash-event candidates and
  `finance_import_ready=false`.
- No proof so far has identified an explicit patient invoice, statement, or
  charge-ref source.

## Candidate Sources

| Source | Type | Evidence | Confidence | Risk | Decision |
| --- | --- | --- | --- | --- | --- |
| Explicit invoice / statement tables | Not found | Metadata search found no row-bearing patient invoice or statement source. The only invoice-like field found was `Clinics.SMSInvoiceNumber`. | None for patient invoices. | High: no source for invoice number, issue date, paid status, or line grouping. | Historical invoice import remains blocked. |
| `dbo.Transactions` | Table | Live metadata check found `516275` rows, `15153` distinct patients, date range `1929-02-03` to `2026-05-04`, `PatientCost=4845811.68`, `DPBCost=77933.64`, `TPNumber`/`TPItem` present on `62607` rows, `Deleted=3`, and `PaymentAdjustmentID` non-zero `0`. | High as treatment/charge evidence. | High as invoice truth because it lacks proven invoice grouping and payment linkage. | Reconciliation-only unless a later proof authorises charge-line use. |
| `dbo.PaymentAllocations` / `dbo.vwAllocatedPayments` | Table/view | Each has `3130` rows, `1726` distinct patients, linked `PaymentID=3130`, total `Cost=11714.03`, date range `2005-08-09` to `2017-08-29`, `ChargeTransactionRefID=0`, and `ChargeAdjustmentRefID=0`. | Medium-high as allocation evidence. | High for invoice application because every charge ref is missing. | Reconciliation-only; cannot apply payments to PMS invoices. |
| `dbo.SundryCharges` | Table | `4` rows, all with `AdjustmentRefId`. | Low-medium as a sundry-charge hint. | High because it is tiny and adjustment-linked, not an invoice source. | Needs separate sundry proof if ever used. |
| `dbo.vwPayments` | View | `44906` rows, `9030` distinct patients, amount total `-4421051.59`, `IsCancelled=1032`, and `CancellationOf` present on `438` view rows. | High as cash-event candidate evidence. | High as invoice truth because it has no explicit invoice/charge refs. | Cash-event proof source only. |
| `dbo.Adjustments` | Table | `47732` rows, `9483` distinct patients, amount total `-4977508.73`, and `CancellationOf=460`. | High as base cash-event/cancellation cross-check. | High as invoice truth because it has no proven invoice application semantics. | Cross-check and future cash-event candidate source only. |
| `PaymentMgrReceipts`, `CashUp`, `CashCredits`, `ReAllocatedPayments`, `SplitAllocatedPayment`, `AllocationAdjustments`, `PBPaymentWritebacks`, `RedcardReceipt`, `vwSundryCashFlow`, `vwTreatmentCashFlow` | Tables/views | Present but currently `0` rows in the live metadata check. | Low for this extract. | High if assumed as missing ledger truth. | Not usable as current invoice/statement source. |
| `SChargeMechanismCharges`, `SChargeMechanismChargesItemSnapshot`, `SChargeMechanismChargesTotalSnapshot` | Tables | Present but currently `0` rows. | Low for this extract. | High if inferred as charge truth. | Not usable as current invoice source. |
| `NHSCourseDetails`, `NHSContractCharges`, `NHSContractAdjustments`, `vwSettledOrAdjustedClaims` | Tables/views | Present but currently `0` rows. | Low for this extract. | Medium-high if later populated because NHS claim semantics differ from private ledger. | Not usable as current invoice/statement source. |
| `NHSChargeBands`, `NHSChargeBandValues`, `NHSChargeValueSets` | Tables | Lookup/reference rows only. | Medium as NHS charge lookup evidence. | High if treated as patient ledger source. | Reference only. |

The live metadata check is not a replacement for the prior finance inventory.
It confirms the source-decision shape with fresher R4 data and only
SELECT-only aggregate/metadata queries.

## Payment Allocation Interpretation

`PaymentAllocations` and `vwAllocatedPayments` cannot be used for PMS invoice
application in the current R4 evidence.

Interpretation:

- linked allocations `3130` means allocation rows can point to payment rows;
- charge refs `0` means no allocation row points to a treatment transaction or
  adjustment charge via the discovered charge-ref columns;
- missing charge refs `3130` means every allocation row fails the invoice
  application prerequisite;
- allocation date ranges ending in 2017 show this source is also not a complete
  recent allocation stream.

Decision:

- keep `PaymentAllocations` and `vwAllocatedPayments` reconciliation-only;
- do not use allocation rows to apply payments, refunds, or credits to PMS
  invoices;
- do not create PMS invoices, invoice payments, refunds, credits, ledger rows,
  or balances from allocation rows;
- revisit allocations only if a later source proof discovers reliable charge or
  invoice references.

## Transactions Interpretation

`Transactions` can support treatment/charge reconciliation, but not invoice
truth by itself.

Current evidence:

- it carries patient linkage, dates, clinical/treatment status, `PatientCost`,
  `DPBCost`, treatment plan numbers/items, and R4 transaction refs;
- `PaymentAdjustmentID` remains non-zero on `0` rows in current aggregate
  evidence;
- the allocation sources have `ChargeTransactionRefID=0`, so current payment
  allocation evidence does not link back to transaction charges;
- no invoice number, statement number, invoice issue date, invoice status, or
  invoice-line grouping source has been proven.

Decision:

- use `Transactions` as treatment charge evidence and reconciliation input;
- do not convert `Transactions` blindly into PMS invoices;
- do not infer invoice grouping, invoice numbers, issue dates, paid state, or
  payment application from treatment transaction costs;
- require a separate proof before any transaction-derived charge line can be
  used in finance migration.

## Invoice / Statement Source Decision

No explicit R4 patient invoice or statement source has been found.

The source-discovery result supports these decisions:

- historical PMS invoice import is blocked;
- historical payment application to PMS invoices is blocked;
- allocation rows remain reconciliation-only because charge refs are absent;
- cash-event staging can only be considered without invoice application, and
  only after a later import-readiness decision;
- opening-balance snapshot strategy remains the only currently strong finance
  path that does not require reconstructing historic R4 invoices.

## Import-Readiness Implication

No finance import can proceed safely now.

The current evidence supports proof and design work only:

- `PatientStats` may support an opening-balance snapshot design/proof;
- `vwPayments` plus `Adjustments` may support cash-event staging design/proof
  without invoice application;
- allocations remain reconciliation-only;
- `Transactions` remain reconciliation-only for finance until later charge-line
  proof;
- explicit invoice/statement/charge-ref discovery remains negative for the
  current extract.

Finance import-readiness remains false until the project chooses a bounded
migration strategy and proves double-counting, cutover-date, refund/allocation,
payment-method, and patient-ledger semantics.

## Fail-Closed Rules

These rules supersede weaker interpretations:

- no invoice application without explicit invoice or charge refs;
- no allocation row may create or apply a PMS invoice payment without charge
  refs;
- `Transactions` remain reconciliation-only unless later proof authorises
  charge-line use;
- unlinked payments, refunds, and credits remain staging/reconciliation
  candidates only;
- `PatientStats` remains snapshot evidence, not row-level ledger truth;
- lookup/reference charge tables remain reporting/reference only;
- unknown invoice, statement, charge, allocation, or refund semantics block
  import;
- no default/live PMS finance write path is authorised by this decision.

## Open Questions and Risks

- Whether R4 stores patient statement/invoice history outside the inspected SQL
  finance sources.
- Whether clinic workflows used statements or invoices outside SQL data.
- Whether a future opening-balance snapshot plus selected cash-event staging can
  avoid double counting.
- Whether payment method mapping can be made import-ready without losing
  cash-up fidelity.
- Whether transaction-derived treatment costs can ever be safely grouped into
  invoice-like charge lines.
- Whether NHS/private/sundry charge semantics need separate treatment before
  any finance migration strategy.

## Recommended Next Slice

Selected target: scratch-only opening-balance dry-run execution evidence.

Why this is the smallest justified next step:

- the opening-balance snapshot import design is recorded in
  `docs/r4/R4_FINANCE_OPENING_BALANCE_SNAPSHOT_DESIGN.md`;
- PR #604 completed the backend-only pure opening-balance snapshot plan helper
  proof and unit tests without importer wiring, R4 access, PMS DB writes, or
  finance record changes;
- PR #607 completed backend-only dry-run/report tooling with JSON inputs, no R4
  source mode, no DB write path, and no apply mode;
- the live opening balance proof found internally consistent `PatientStats`
  balances with `0` component mismatches;
- invoice/statement source discovery remains negative;
- allocation charge refs remain absent;
- cash-event proof found a candidate population, but `finance_import_ready=false`
  and payment/application semantics remain blocked;
- scratch-only opening-balance dry-run execution evidence is the smallest next
  proof step because the planning helper and report tooling are now merged, but
  no scratch mapping report evidence exists yet.

Likely files:

- no repo code files for the execution itself;
- later docs/evidence refresh if the scratch-only run succeeds;
- no finance staging models, import wiring, PMS DB writes, or R4 writes.

Likely validation:

- `git diff --check`
- docs-only validation if present
- no R4 writes
- no PMS DB writes
- no finance records created or changed

Do not start finance import, finance staging models, invoice creation, payment
creation, balance mutation, ledger creation, R4 writes, or PMS DB writes from
this decision.
