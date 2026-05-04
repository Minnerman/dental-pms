# R4 Finance Sign, Cancellation, and Allocation Policy

Status date: 2026-05-04

Baseline: `master@dd28ea7c91aec28c33a321b6ebbc95e6c6d665af`

Safety: R4 SQL Server remains strictly read-only / SELECT-only. This policy is
design evidence only. It does not authorise finance import, finance staging
models, PMS DB writes, R4 writes, invoice creation, payment creation, balance
mutation, or live cutover.

## Inputs

This policy uses:

- `docs/r4/R4_FINANCE_SOURCE_DISCOVERY.md`
- `/home/amir/dental-pms-finance-inventory-proof/.run/finance_inventory_20260503_201724/finance_inventory.json`
- `/home/amir/dental-pms-opening-balance-live-proof/.run/opening_balance_reconciliation_20260504_083558/opening_balance_reconciliation.json`
- `/home/amir/dental-pms-finance-cancellation-allocation-proof/.run/finance_cancellation_allocation_reconciliation_20260504_140810/finance_cancellation_allocation_reconciliation.json`
- `/home/amir/dental-pms-finance-cash-event-live-proof/.run/finance_cash_event_staging_20260504_191704/finance_cash_event_staging.json`
- `docs/r4/R4_FINANCE_REFUND_ALLOCATION_CHARGE_REF_DECISION.md`
- `docs/r4/R4_FINANCE_INVOICE_CHARGE_REF_SOURCE_DECISION.md`
- PR #599 cash-event staging proof tooling.
- Current PMS finance code for invoices, payments, patient ledger, patient
  balances, cash-up, outstanding, trends, and month-pack reporting.

Inventory evidence:

- `dbo.PatientStats`: `17012` rows, `1018` non-zero balances,
  `total_balance=-131342.13`, `727` credit rows totalling `-163760.79`,
  `291` debt rows totalling `32418.66`, aged debt 30-60 `379.84`,
  60-90 `579.00`, 90+ `9370.98`, null/blank patient codes `0`.
- `dbo.vwPayments`: `44906` rows, `total_amount=-4421051.59`, payments
  `38269`, refunds `110`, credits `6513`, cancellations `1032`, null/blank
  patient codes `0`.
- `dbo.Adjustments`: `47731` rows, `total_amount=-4975508.73`,
  `CancellationOf=460`, null/blank patient codes `0`.
- `dbo.Transactions`: `516218` rows, `PatientCost=4844211.68`,
  `DPBCost=77933.64`, `PaymentAdjustmentID=0`, `TPNumber=62604`,
  `TPItem=62604`, null/blank patient codes `0`.
- `dbo.PaymentAllocations` and `dbo.vwAllocatedPayments`: each `3130` rows,
  `total_cost=11714.03`, refunds `795`, advanced payments `2335`, linked
  payments `3130`, charge refs `0`, null/blank patient codes `0`.
- Lookup/classification counts: `PaymentTypes=18`, `OtherPaymentTypes=1`,
  `PaymentCardTypes=32`, `AdjustmentTypes=6`, `vwDenplan=4182`,
  `DenplanPatients=3`, `NHSPatientDetails=16468`.
- Opening balance proof: `PatientStats` component checks passed with `0`
  mismatches, TreatmentBalance split checks passed with `0` mismatches, aged
  debt total `10329.82`, and `892` non-zero balance rows had no aged debt.
- Cancellation/refund/allocation proof: `Adjustments CancellationOf=460`,
  originals found `460`, originals missing `0`, patient mismatches `0`, paired
  net amount `0.00`; `vwPayments` refunds `110`, `PaymentAllocations` refunds
  `795`, matching allocation refunds `62`, allocation refunds without
  `vwPayments` refund `733`, `vwPayments` refunds without allocation `48`,
  advanced payment allocations `2335`, `vwPayments` credits `6513`, linked
  allocations `3130`, charge refs `0`, and missing charge refs `3130`.
- Cash-event staging proof: `vwPayments` rows `44906`, `Adjustments` rows
  `47732`, eligible cash-event candidates `42914`, manual-review rows
  `47794`, excluded rows `0`, cancellation/reversal rows `1930`, payment
  candidates `36859`, refund candidates `104`, credit candidates `5951`,
  missing patient/date/amount/zero amount counts `0`, and
  `finance_import_ready=false`.
- Cash-event method/sign proof: proof-only method families were cash `25678`,
  cheque `10928`, card `6946`, credit/overpayment `1344`, and other/unknown
  `10`; classification rows were candidate `42914` and manual-review `49724`,
  with raw signs negative `88880` and positive `3758`.

Current PMS finance convention:

- Patient balance is the sum of `PatientLedgerEntry.amount_pence`.
- Positive ledger amounts increase debt.
- Payments are stored as negative ledger entries.
- Charges and positive adjustments are stored as positive ledger entries.
- Cash-up reports use absolute values for payment ledger entries.
- Outstanding reports treat summed positive balance as debt.

## Source Priority

| Finance area | Primary R4 source | Policy |
| --- | --- | --- |
| Current balances and aged debt | `dbo.PatientStats` | High-confidence snapshot source for opening balance and aged-debt reconciliation. It is not a row-level invoice/payment import source. |
| Payments, refunds, credits, cancellations | `dbo.vwPayments`, cross-checked to `dbo.Adjustments` | `vwPayments` is the first classification source because it exposes payment/refund/credit/cancellation flags. `Adjustments` is the base table and must be used to prove stable keys, status, and cancellation pairing. |
| Treatment charges | `dbo.Transactions` | Clinical/treatment cost evidence and reconciliation input only. It is not finance ledger truth by itself and must not be used to reconstruct invoices without separate proof. |
| Allocations | `dbo.PaymentAllocations`, `dbo.vwAllocatedPayments` | Reconciliation source for allocated/advanced/refund rows. Not a direct import source until charge/payment linkage semantics are proven. |
| Lookup/method mapping | `PaymentTypes`, `OtherPaymentTypes`, `PaymentCardTypes`, `AdjustmentTypes` | Reference data for a later classification helper and method mapping. |
| NHS/private/Denplan classification | `vwDenplan`, `NHSPatientDetails`, `DenplanPatients` | Classification/reference sources only. They do not define ledger truth. |

## Sign Convention Policy

### PatientStats

`PatientStats.Balance` is treated as an R4 balance snapshot where positive
values are probable patient debt and negative values are probable patient
credit. This matches the current inventory buckets: debt rows are positive and
credit rows are negative.

Before any PMS ledger write:

- prove the sign against patient-level statement examples or another independent
  R4 balance view;
- preserve the raw R4 amount and the interpreted PMS amount in any report;
- map positive opening debt to a positive PMS ledger adjustment only after
  reconciliation passes;
- map negative opening credit to a negative PMS ledger adjustment only after
  reconciliation passes.

### vwPayments and Adjustments

R4 payment-like rows must be treated as R4-native signed values, not blindly
inverted.

Current inventory suggests:

- active payment rows in `vwPayments` are mostly negative;
- active credit rows are mostly negative;
- active refund rows are positive;
- cancelled rows can have either sign and must be treated separately.

Policy:

- classify the row first using flags, type/status fields, and lookup values;
- preserve raw sign and amount;
- only convert to PMS ledger sign after the classifier has a known type and the
  row is not cancelled/reversed/ambiguous;
- fail closed for any unknown combination of `Type`, `Status`, `IsPayment`,
  `IsRefund`, `IsCredit`, `IsCancelled`, `PaymentTypeDescription`,
  `AdjustmentTypeDescription`, or `CancellationOf`.

### Transactions

`Transactions.PatientCost` and `Transactions.DPBCost` are treatment/cost
evidence. Their positive totals do not prove an invoice or ledger sign. They
must remain reconciliation-only until invoice/charge policy is proven.

### PaymentAllocations and vwAllocatedPayments

Allocation `Cost` values are allocation/refund/advanced-payment evidence. Their
sign cannot be imported until the linked payment and charge/refund semantics are
proven. Preserve raw amount and classify only.

## Cancellation and Reversal Policy

Cancellation/reversal fields are first-class safety gates:

- `vwPayments.IsCancelled`
- `vwPayments.CancellationOf`
- `Adjustments.CancellationOf`
- `Adjustments.Status`
- cancellation or reversal descriptions/types from lookup tables
- allocation refund/cancellation/advanced-payment flags

Policy:

- cancelled rows must not create PMS payment, refund, credit, invoice, or
  opening-balance ledger entries;
- rows that cancel another row must not be automatically netted;
- original/cancellation pairs must be linked and reconciled in a report before
  either side can be considered for import;
- non-current or unknown `Adjustments.Status` values are manual-review until
  mapped;
- deleted/voided rows, if found in later finance sources, are excluded from
  import until a specific pairing rule exists;
- cancellation totals must be reported separately from active payment, refund,
  credit, and adjustment totals.

PR #596 narrows this risk: all `460` `Adjustments.CancellationOf` rows resolved
to original `Adjustments` rows, with `0` missing originals, `0` patient
mismatches, and paired net amount `0.00`. This supports a future
exclude/net/manual-review decision for paired `Adjustments` cancellations, but
it does not authorise import. The live cash-event proof classified
cancellation/reversal rows separately and kept `vwPayments` cancellation rows
outside proven `Adjustments.CancellationOf` pairs excluded/manual-review, so
cancellation handling remains fail-closed until a later import-readiness policy
authorises a representation.

## Payment, Refund, Credit, and Adjustment Policy

Candidate classes for a later pure helper:

| Candidate class | Required R4 evidence | PMS treatment before import |
| --- | --- | --- |
| Payment | Known payment flag/type, not cancelled, not reversed, valid patient code, known method mapping, sign policy proven. | Candidate negative PMS payment ledger entry, but report-only until reconciliation passes. |
| Refund | Known refund flag/type, not cancelled, not reversed, valid patient code, sign policy proven. | Candidate positive PMS adjustment/refund representation, but no import until refund mismatch is reconciled. |
| Credit | Known credit flag/type, not cancelled, not reversed, valid patient code, sign policy proven. | Candidate negative PMS adjustment/opening-credit representation, but no import until credit/deposit policy is proven. |
| Write-off / bad debtor | Known adjustment/write-off type from lookup, not cancelled, not reversed, valid patient code. | Manual-review by default until practice accounting semantics are confirmed. |
| Deposit / advanced payment | Allocation or payment type evidence showing advanced payment/over-payment. | Reconciliation-only until allocation policy is proven. |

The `vwPayments` refund count (`110`) and `PaymentAllocations` refund count
(`795`) conflict at inventory level. Refund import must stay blocked until a
SELECT-only reconciliation explains whether allocation refunds are linked to
credit/deposit movements, payment reversals, or a different reporting grain.

PR #596 confirmed the mismatch remains material: only `62` allocation refund
rows matched `vwPayments` refund rows by `PaymentID`/`RefId`, `733` allocation
refunds had no matching `vwPayments` refund, and `48` `vwPayments` refunds had
no allocation refund. These unmatched rows remain unresolved blockers rather
than import-ready evidence.

The refund-allocation/charge-ref semantics decision is now recorded in
`docs/r4/R4_FINANCE_REFUND_ALLOCATION_CHARGE_REF_DECISION.md`: `vwPayments`
plus `Adjustments` are the cash-event proof sources, matched allocation refunds
are reconciliation evidence only, unmatched allocation refunds are
manual-review/reconciliation-only, and `vwPayments` refunds without allocation
rows may be proof candidates but are not import-ready. The live cash-event
proof confirmed `104` refund candidates and kept allocation refunds
reconciliation-only.

Rows with blank flags or mutually inconsistent payment/refund/credit flags are
manual-review. No classifier may infer payment/refund/credit type from sign
alone.

## Allocation Policy

`PaymentAllocations` and `vwAllocatedPayments` are reconciliation sources, not
first import sources.

Current evidence is high risk:

- both sources have only `3130` rows;
- date range ends in 2017;
- all rows have linked payment refs;
- charge transaction refs are `0`;
- allocation refund count is `795`, which does not match `vwPayments` refunds
  `110`.
- PR #596 found linked allocations `3130`, charge refs `0`, and missing charge
  refs `3130`, confirming invoice application remains blocked by missing
  charge refs.
- The refund-allocation/charge-ref decision keeps `PaymentAllocations` and
  `vwAllocatedPayments` reconciliation-only. Allocation rows cannot create PMS
  invoices, invoice payments, refunds, credits, or ledger entries unless a later
  proof finds reliable charge/invoice refs and an import-readiness decision
  authorises that path.

Policy:

- allocations are required before any attempt to recreate historical invoice
  payment application;
- allocations are not required for a later opening-balance-only snapshot proof;
- linked payments without charge refs cannot be applied to PMS invoices;
- allocation rows with missing charge/payment links are reconciliation-only;
- allocation rows with refund/advanced/balancing flags are manual-review until
  pair semantics are proven;
- imported payment records, if ever built, must preserve enough R4 refs to
  reconcile to allocation rows without relying on PMS-generated invoice IDs.

## Opening Balance Policy

`PatientStats` is the strongest first opening-balance source.

Policy:

- treat `PatientStats` as a current snapshot for balance and aged debt, not a
  source of invoice lines;
- first proof should be SELECT-only reconciliation of `PatientStats.Balance`
  against payment/refund/credit/transaction/allocation evidence;
- aged-debt fields are reconciliation/reporting evidence and must not create
  separate ledger rows by themselves;
- do not import both historic row-level payments/charges and a full opening
  balance unless the reconciliation proves there is no double counting;
- if a future import chooses opening balances, use one explicitly labelled PMS
  opening-balance adjustment per patient, preserving raw R4 balance fields and
  generated evidence artefacts.

## Invoice and Charge Policy

No explicit R4 invoice or statement source is confirmed.

Policy:

- do not create historical PMS invoices from `Transactions` alone;
- do not infer invoice numbers, issue dates, paid status, or line grouping from
  treatment transaction costs;
- use `Transactions` as clinical charge/cost evidence and reconciliation input;
- use `SundryCharges`/adjustment-linked evidence only after a separate sundry
  charge proof;
- invoice import remains blocked until an invoice/statement source is found or
  the project explicitly chooses opening-balance-only finance migration.

## NHS, Private, and Denplan Policy

Scheme and classification sources are useful but not ledger truth.

Policy:

- `PatientStats` balance splits may inform NHS/private/DPB reconciliation, not
  ledger creation by themselves;
- `vwPayments.AdjustmentTypeDescription` can classify payment-like rows but
  does not override cancellation/sign rules;
- `vwDenplan` is the preferred Denplan linkage candidate because it has
  `PatientCode`;
- `DenplanPatients` has only `3` rows in this extract and no `PatientCode`, so
  it is not a primary import source;
- `NHSPatientDetails` supports NHS/private classification only;
- classification must not infer patient ledger signs, invoice grouping, or
  payment application.

## Fail-Closed Rules

Before any finance import or PMS finance write path exists:

- unknown type/status/sign combinations are manual-review;
- missing or blank patient code is excluded;
- cancelled, reversed, voided, deleted, or non-current rows are excluded until
  pair/reversal policy is proven;
- rows with `CancellationOf` are manual-review until linked to the original row;
- payment/refund/credit flags must be known and mutually consistent;
- refund/allocation mismatches are manual-review;
- allocations without charge refs cannot apply to invoices;
- no import may infer payment method from free text when a lookup mapping is
  missing;
- `Transactions` cannot create invoices or ledger entries by itself;
- `PatientStats` opening balances cannot be imported until reconciliation
  evidence proves sign and avoids double counting;
- no finance import may run against default/live PMS DB until a later guarded,
  scratch-first design exists.

## Open Questions and Risks

- Patient-level statement examples are still needed to prove balance signs.
- `vwPayments` versus `Adjustments` duplicate and key relationships still need
  an import-readiness decision even though `Adjustments.CancellationOf` pairing
  is now proven at aggregate level.
- Cancellation and reversal pairing is proven for `Adjustments.CancellationOf`
  rows, but `vwPayments` cancellation flag semantics still need policy mapping;
  the live cash-event proof keeps these rows excluded/manual-review.
- Refund counts differ sharply between `vwPayments` and allocation sources, and
  PR #596 confirmed most allocation refund rows do not match `vwPayments`
  refunds.
- Allocation rows have no charge refs in current inventory and PR #596 evidence.
- No R4 invoice/statement source is confirmed.
- `docs/r4/R4_FINANCE_INVOICE_CHARGE_REF_SOURCE_DECISION.md` confirms no
  explicit patient invoice/statement source or usable allocation charge refs are
  proven.
- `Transactions` costs may not equal accounting ledger truth.
- Opening balance import could double count if combined with historic charges
  and payments.
- Payment/card/merchant metadata may include sensitive fields and needs explicit
  retention policy before staging.
- Opening-balance snapshot design is now the smallest finance path that avoids
  historical invoice reconstruction, but it must still prove double-counting
  and cutover semantics before any import.

## Recommended Next Proof Slices

1. Pure opening-balance snapshot plan helper plus unit tests.
   - Target: convert the docs/design decision in
     `docs/r4/R4_FINANCE_OPENING_BALANCE_SNAPSHOT_DESIGN.md` into a pure
     planning helper that classifies PatientStats rows, preserves raw signs,
     proposes proof-only directions, and emits fail-closed reasons without
     writing finance records.
   - Why next: the opening-balance snapshot design now records that
     `PatientStats` is the only currently strong opening-balance snapshot
     source, while invoice import and payment application remain blocked.
   - Validation: focused unit tests, existing finance classification tests if
     relevant, `git diff --check`, no PMS DB writes, no R4 writes, no finance
     records created or changed.

2. Payment method mapping proof.
   - Target: once cash-event staging has a stable candidate/exclusion shape, map R4
     payment and card lookup values to PMS reporting/payment method categories.
   - Why next later: method mapping affects cash-up/reporting, but it should not
     outrun cancellation/reversal and allocation semantics.
   - Validation: focused unit/report tests, no PMS DB writes.

Do not start finance import, finance staging models, invoice creation, payment
creation, or balance mutation until these proofs pass and are recorded.
