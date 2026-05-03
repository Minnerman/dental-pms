# R4 Finance Source Discovery

Status date: 2026-05-03

Baseline: `master@d59e83b4c940cae6692919848fdb83e420127be5`

Safety: R4 SQL Server remains strictly read-only / SELECT-only. This report is
source discovery only. It does not authorise finance import, PMS DB writes, R4
writes, invoice creation, payment creation, balance mutation, or live cutover.

## Scope

Local docs and code confirmed that treatment transactions are already imported
from `dbo.Transactions` into read-only R4 staging, but they did not identify the
R4 finance/payment/balance source of truth. Because the source names were not
clear from repo evidence, this discovery used SELECT-only metadata and aggregate
queries against R4 with `R4_SQLSERVER_READONLY=true`.

Query types used:

- `INFORMATION_SCHEMA.TABLES` name search for finance, ledger, balance,
  invoice, receipt, cash, account, credit, refund, deposit, debt, allocation,
  charge, adjustment, write-off, NHS, insurance, private, and Denplan terms.
- `INFORMATION_SCHEMA.COLUMNS` inspection for the likely finance candidate
  tables/views.
- Aggregate-only `COUNT`, `MIN`, `MAX`, `SUM`, and grouped distribution queries
  over likely candidates. No broad row samples or patient-level finance records
  were extracted into the repo.

## SELECT-Only Inventory Evidence

PR #587 added the repeatable backend SELECT-only finance inventory command and
captured the first live inventory transcript.

Evidence path:
`/home/amir/dental-pms-finance-inventory-proof/.run/finance_inventory_20260503_201724/`

Key artefact: `finance_inventory.json`

Safety result:

- `select_only=true`
- R4 access was SELECT-only.
- No R4 writes occurred.
- No PMS DB writes occurred.
- No finance import, finance staging models, invoices, payments, balances, or
  finance records were created or changed.

Key inventory figures:

- `dbo.PatientStats`: `row_count=17012`, `nonzero_balance_count=1018`,
  `total_balance=-131342.13`, `TreatmentBalance=-139692.13`,
  `SundriesBalance=8350.00`, `NHSBalance=2724.60`,
  `PrivateBalance=-142416.73`, `DPBBalance=0.00`, aged debt 30-60 `379.84`,
  60-90 `579.00`, 90+ `9370.98`, null/blank patient codes `0`.
- `dbo.vwPayments`: `row_count=44906`, date range
  `2005-08-09T08:18:27` to `2026-05-01T10:59:49`,
  `total_amount=-4421051.59`, payments `38269`, refunds `110`,
  credits `6513`, cancellations `1032`, null/blank patient codes `0`.
- `dbo.Adjustments`: `row_count=47731`, date range
  `2005-08-05T14:32:31.063000` to `2026-05-01T10:59:49`,
  `total_amount=-4975508.73`, `CancellationOf=460`, null/blank patient
  codes `0`.
- `dbo.Transactions`: `row_count=516218`, date range
  `1929-02-03T00:00:00` to `2026-05-02T08:08:44`,
  `PatientCost=4844211.68`, `DPBCost=77933.64`, `PaymentAdjustmentID=0`,
  `TPNumber=62604`, `TPItem=62604`, null/blank patient codes `0`.
- `dbo.PaymentAllocations` and `dbo.vwAllocatedPayments`: each
  `row_count=3130`, `total_cost=11714.03`, refunds `795`, advanced
  payments `2335`, linked payments `3130`, charge refs `0`, null/blank
  patient codes `0`.
- Lookup tables: `PaymentTypes=18`, `OtherPaymentTypes=1`,
  `PaymentCardTypes=32`, `AdjustmentTypes=6`.
- Scheme/classification: `vwDenplan=4182`, `DenplanPatients=3`,
  `NHSPatientDetails=16468`.

Inventory risks carried forward:

- sign conventions
- cancellation/reversal handling
- allocation semantics
- no explicit invoice/statement source
- NHS/private/Denplan classification policy
- refund mismatch between `vwPayments` and `PaymentAllocations`
- opening balance reconciliation

## Existing PMS Finance Surface

The current PMS has first-party finance capability:

- `Invoice`, `InvoiceLine`, and `Payment` models.
- `PatientLedgerEntry` with entry types `charge`, `payment`, and `adjustment`.
- Invoice issue/void/line/payment routes.
- Patient ledger, patient balance, finance summary, quick payment, charge, and
  treatment-transaction routes.
- Finance reports for cash-up, outstanding balances, trends, and month pack.

There is no R4 finance importer, no R4 invoice importer, no R4 payment importer,
and no R4 balance reconciliation in the repo at this baseline.

## Candidate Sources

| Source | Type | Purpose | Link/date/amount fields | Evidence | Likely PMS target | Confidence | Risk |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `dbo.PatientStats` | Table | Current patient balance and aged debt snapshot. | `PatientCode`; `Balance`, `TreatmentBalance`, `SundriesBalance`, `NHSBalance`, `PrivateBalance`, `DPBBalance`, `CreditBalance`; `OutstandingSince`, `AgeDebtor*`, `AgeDebtorDate`; last transaction/adjustment refs. | `17012` rows, `17012` distinct patients, `1018` non-zero balances. Balance buckets: `15994` zero, `727` credit totalling `-163760.79`, `291` debt totalling `32418.66`. Aged-debt sums: 30-60 `379.84`, 60-90 `579.00`, 90+ `9370.98`. | Opening balance / aged debt reconciliation source, not invoice/payment line import by itself. | High for current balance snapshot. | High until snapshot timing, sign convention, and reconciliation to transactions/payments are proven. |
| `dbo.vwPayments` | View | Enriched payments, refunds, credits, cancellations, and payment-method classification. | `RefId`, `PatientCode`, `At`, `Amount`, `Status`, `Type`, `IsPayment`, `IsRefund`, `IsCredit`, `IsCancelled`, `PaymentTypeDescription`, `AdjustmentTypeDescription`, `ClinicCode`, `UserCode`, `PaymentAdjustmentID`, `CancellationOf`. | `44906` rows, `9030` distinct patients, date range `2005-08-09T08:18:27` to `2026-05-01T10:59:49`. Flags: payments `38269`, refunds `110`, credits `6513`, cancelled `1032`. Top rows are cash, cheque, debit card, over-payment credits, NHS/private/sundry distinctions. | Payment/refund/credit staging and reconciliation candidate. | High. | High until cancellation/reversal, sign, allocation, and method mapping policy is proven. |
| `dbo.Adjustments` | Table | Base payment/adjustment records behind `vwPayments`. | `RefId`, `AdjustmentType`, `PatientCode`, `UserCode`, `ClinicCode`, `At`, `Amount`, `PaymentType`, `ToUser`, `Description`, `Status`, `PaymentAdjustmentID`, `CancellationOf`, `OtherPaymentTypeID`, `PaymentMgrReceiptID`. | `47731` rows, `9483` distinct patients, date range `2005-08-05T14:32:31.063000` to `2026-05-01T10:59:49`, `3` adjustment types, `16` payment types. | Raw adjustment/payment staging candidate; likely source table for `vwPayments`. | High. | High unless the view/source-table relationship and duplicate/cancelled behaviour are proven. |
| `dbo.Transactions` | Table | Treatment/clinical charge transactions, already used for R4 treatment transaction staging. | `RefId`, `PatientCode`, `Date`, `Status`, `TransCode`, `CodeID`, `TPNumber`, `TPItem`, `UserCode`, `RecordedBy`, `PatientCost`, `DPBCost`, `Deleted`, `PaymentsAllocated`, `PaymentAdjustmentID`, `ClinicCode`. | `516218` rows, `15152` distinct patients, date range `1929-02-03T00:00:00` to `2026-05-02T08:08:44`; `PatientCost` sum `4844211.68`, `DPBCost` sum `77933.64`, `3` deleted rows. | Treatment-charge/clinical transaction staging and possible charge reconciliation input. | High as treatment transaction source. | High as finance truth: costs may not equal invoices/open ledger, and `PaymentsAllocated` was `0` for all rows in aggregate evidence. |
| `dbo.PaymentAllocations` / `dbo.vwAllocatedPayments` | Table/view | Payment, refund, over-payment, and allocation rows. | `PaymentID`, `PatientCode`, `Cost`, `AllocationDate`, `PaymentDate`, `PaymentType`, `PaymentTypeDesc`, `IsRefund`, `IsAdvancedPayment`, `IsAllocationAdjustment`, `IsBalancingEntry`, `ChargeTransactionRefID`, `ChargeAdjustmentRefID`. | `3130` rows, `1726` distinct patients, date range `2005-08-09T10:47:03` to `2017-08-29T15:50:50`; `2335` advanced-payment rows, `795` refund rows, `0` for-treatment rows. | Allocation/credit/refund reconciliation source. | Medium-high. | High because this source is sparse, old-only in current evidence, and all rows are non-treatment allocations. |
| `dbo.PaymentTypes`, `dbo.OtherPaymentTypes`, `dbo.PaymentCardTypes`, `dbo.AdjustmentTypes` | Tables | Lookup tables for payment method/card/adjustment mapping. | Payment type IDs, card type IDs, adjustment type IDs, descriptions/current flags. | Metadata confirms lookup presence. | Finance mapping lookup staging. | High. | Medium: descriptions and current flags must be snapshotted and mapped deliberately. |
| `dbo.PaymentMgrReceipts` | Table | External merchant/card receipt records. | `ID`, `ReceiptDate`, `Amount`, `PatientCode`, `ClinicCode`, `UserCode`, `TransDate`, `TransType`, `TransStatus`, `ChargeType`, card/vendor fields. | Structure exists but current aggregate count is `0`. | Payment audit/reconciliation only if populated in another source. | Low for this data set. | High if later populated because it includes sensitive payment/card metadata. |
| `dbo.CashUp` | Table | Daily cash-up totals by method, clinic, and user. | `Date`, `UserId`, `ClinicId`, `Cash`, `Cheques`, `CreditCards`, `DebitCards`, `CashBanked`, discrepancies. | Structure exists but current aggregate count is `0`. | Cash-up reconciliation, not patient ledger import. | Low for this data set. | Medium if later populated; totals need date/method reconciliation. |
| `dbo.CashCredits` | Table | Cash credit records. | `Date`, `Amount`, `Description`, `Processed`. | Structure exists but current aggregate count is `0`. | Credit/deposit reconciliation if populated. | Low for this data set. | Medium. |
| `dbo.SundryCharges` | Table | Sundry/non-treatment charges. | `SundryCode`, `NumberSold`, `RefId`, `AdjustmentRefId`. | `4` rows, `2` sundry codes, all linked to adjustment refs. | Minor sundry charge staging, likely via adjustments. | Medium. | Low-medium due tiny row count, but semantics still need proof. |
| `dbo.vwTreatmentCashFlow` / `dbo.vwSundryCashFlow` | Views | Aggregate cash-flow reporting by category. | Date, clinic/user, category amount columns. | Both views returned `0` rows in current aggregate evidence. | Reporting reconciliation only, not row import. | Low for this data set. | Medium if later populated; aggregate views are not enough for patient ledger. |
| `dbo.ReAllocatedPayments`, `dbo.SplitAllocatedPayment`, `dbo.AllocationAdjustments` | Tables | Reallocation/split/allocation adjustment support. | Reallocation/split IDs, amount fields, adjustment dates, debit/credit refs, patient code on reallocation. | Current aggregate counts are `0`. | Allocation reconciliation if populated. | Low for this data set. | Medium-high because these are essential if non-zero in another R4 extract. |
| `dbo.PBPaymentWritebacks` | Table | Payment writeback integration table. | `PatientCode`, `AT`, `AdjustmentType`, `Amount`, `PaymentType`, `PaymentMgrReceiptID`, writeback metadata. | Structure exists but current aggregate count is `0`. | Not a first import source unless populated. | Low for this data set. | Medium. |
| `dbo.vwDenplan` | View | Denplan/private plan marker data. | `PatientCode`, `DenplanRef`, `DenplanBand`, `DateSignedToDenplan`, `PatientStatus`, `PaymentStatus`, `FeeCode`, membership fields. | `4182` rows. | Patient scheme/private-plan metadata; possible finance classification support. | Medium-high. | Medium due PHI/member identifiers and unclear relationship to finance ledger. |
| `dbo.DenplanPatients` | Table | Denplan patient/member records. | `ID`, `DenplanRef`, `PatientStatus`, `PaymentStatus`, `FeeCode`, member/contact fields. | `3` rows; no `PatientCode` column in this table. | Likely not the main Denplan patient linkage source; prefer `vwDenplan` for linkage. | Low-medium. | Medium due direct identifiers and small inconsistent row count. |
| `dbo.NHSPatientDetails` | Table | NHS patient marker/details. | `PatientCode`, `EthnicityCatID`. | `16468` rows. | NHS/private classification support, not ledger import. | Medium. | Medium; must be separated from finance ledger and PHI policy. |
| `dbo.NHSCourseDetails`, `dbo.NHSContractCharges`, `dbo.NHSContractAdjustments`, `dbo.vwSettledOrAdjustedClaims` | Tables/views | NHS course, contract, charge, adjustment, and claim support. | Course/patient/contract/charge IDs, `PatientPaid`, `AdjustmentAmount`, claim charge fields where present. | Current aggregate counts were `0` for the inspected contract/course/claim sources. | NHS claim/charge reconciliation if populated in another extract. | Low for this data set. | Medium-high if later populated; claim/payment semantics differ from private ledger. |

## Finance Area Assessment

### Patient Balances

`dbo.PatientStats` is the strongest balance source. It directly carries
patient linkage, current balance fields, treatment/sundry/NHS/private/DPB
balance splits, aged-debt fields, outstanding dates, and refs to last
transaction/adjustment. Positive `Balance` rows appear to be debt and negative
rows appear to be credit, based on the discovered bucket totals, but that sign
convention still needs a focused proof against known patient statements.

### Invoices / Charges

No explicit R4 invoice or statement source table was identified in metadata
searches. The only invoice-like name found was `Clinics.SMSInvoiceNumber`, not a
patient invoice table. Charge candidates are `dbo.Transactions` for treatment
costs and `dbo.SundryCharges`/`dbo.Adjustments` for sundry and adjustment-linked
charges. A future importer should not assume PMS invoices can be reconstructed
one-to-one from R4 without a separate statement/invoice policy.

### Payments / Receipts

`dbo.vwPayments` is the strongest first payment source because it includes
classification flags and descriptions over `dbo.Adjustments`. The base
`dbo.Adjustments` table should be preserved or cross-checked for stable keys and
cancellations. `PaymentMgrReceipts` is present but empty in this source, so it is
not a current first import source.

### Refunds

Refund signals appear in `dbo.vwPayments.IsRefund` and
`dbo.PaymentAllocations.IsRefund`. The counts differ (`110` in `vwPayments`,
`795` in allocations), so refund handling requires a dedicated reconciliation
proof before any ledger import.

### Adjustments / Write-offs

`dbo.Adjustments` and `dbo.vwPayments` expose `AdjustmentType`,
`AdjustmentTypeDescription`, `Status`, `CancellationOf`, and payment type data.
Bad-debtor credits appear in the payment view distribution. Write-off policy
should be driven from these adjustment/payment types, not inferred from
transaction costs alone.

### Credits / Deposits

Credit and deposit-like data appears in `dbo.vwPayments.IsCredit`, over-payment
payment type descriptions, advanced-payment allocation rows, and negative
`PatientStats.Balance` rows. These must be reconciled together before creating
opening credits in PMS.

### Open Balances / Aged Debt

`dbo.PatientStats` has direct aged-debt fields and current outstanding dates.
This is likely the first source for opening balance and debt reconciliation,
with row-level ledger import treated separately.

### Treatment Plan / Appointment Links

`dbo.Transactions` includes `TPNumber`, `TPItem`, `PaymentAdjustmentID`, and
treatment code fields. `dbo.PaymentAllocations` includes
`ChargeTransactionRefID`, `ChargeAdjustmentRefID`, and owner/course fields.
These are the likely links between treatment/charge rows and payment/allocation
rows, but the current allocation evidence is sparse and old-only.

### Clinician / Provider Attribution

`dbo.Transactions` carries `UserCode` and `RecordedBy`. `dbo.Adjustments` and
`dbo.vwPayments` carry `UserCode`, `ToUser`, and `ClinicCode`. R4 user codes
must be preserved and mapped explicitly; PMS users must not be inferred.

### NHS / Private / Insurance Markers

`dbo.vwPayments.AdjustmentTypeDescription` includes private/NHS/sundry values.
`dbo.PatientStats` includes NHS/private/DPB balance splits.
`dbo.NHSPatientDetails` and `dbo.vwDenplan` provide scheme markers. These are
classification sources, not enough by themselves for ledger import.

### Void / Deleted / Reversed Handling

`dbo.vwPayments.IsCancelled`, `dbo.Adjustments.Status`, `CancellationOf`, and
allocation refund/cancellation descriptions must be treated as first-class
fields. Future finance import must fail closed until cancellation/reversal and
sign conventions are proven.

## Readiness Assessment

Source discovery is sufficient to define the first finance proof slice, but not
sufficient to implement an importer.

Largest gaps before finance import design:

- Determine the finance source of truth: `PatientStats` for balances,
  `vwPayments`/`Adjustments` for payment-like rows, and `Transactions` for
  treatment costs appear necessary but not independently sufficient.
- Prove sign conventions for balances, payments, refunds, credits, cancellations,
  and write-offs.
- Decide whether PMS should import historical invoices, opening balances only,
  or a staged ledger with reconciliation to R4 balances.
- Reconcile `PatientStats.Balance` against transactions, payments, refunds,
  credits, and allocations.
- Preserve R4 payment/card/merchant metadata safely without importing sensitive
  fields into normal PMS payment records unless explicitly required.
- Decide how NHS/private/Denplan/sundry categories map into PMS billing reports.

## Policy Continuity

The finance sign/cancellation/allocation policy is recorded in
`docs/r4/R4_FINANCE_SIGN_CANCELLATION_ALLOCATION_POLICY.md`.

That policy keeps finance fail-closed:

- `PatientStats` is the current balance and aged-debt snapshot source, not a
  row-level invoice/payment source.
- `vwPayments` is the first payment/refund/credit/cancellation classification
  source, with `Adjustments` used as the base-table cross-check.
- `Transactions` remains treatment/clinical charge evidence and reconciliation
  input only, not finance ledger truth by itself.
- `PaymentAllocations` / `vwAllocatedPayments` are allocation/refund/advanced
  payment reconciliation sources, not first import sources.
- Unknown signs, ambiguous flags, cancellations/reversals, missing patient
  codes, refund/allocation mismatches, and invoice-source gaps remain
  manual-review or excluded until a proof settles them.

## Recommended Next Slice

Add a pure finance classification/sign helper before any finance importer,
finance staging model, or PMS finance write path.

Suggested worktree: `/home/amir/dental-pms-finance-classification-proof`

Suggested first inputs:

- This document.
- `docs/r4/R4_FINANCE_SIGN_CANCELLATION_ALLOCATION_POLICY.md`
- The PR #587 inventory artefact.
- `backend/app/scripts/r4_finance_inventory.py`
- Existing PMS finance models/routes:
  - `backend/app/models/invoice.py`
  - `backend/app/models/ledger.py`
  - `backend/app/routers/invoices.py`
  - `backend/app/routers/patients.py`
  - `backend/app/routers/reports.py`

Expected helper proof:

- classify inventory-shaped rows into payment, refund, credit,
  adjustment/write-off, cancellation/reversal, allocation, opening-balance, or
  manual-review categories;
- preserve raw R4 sign and amount;
- produce deterministic reason codes;
- fail closed for unknown flags/statuses/signs, missing patient code, cancelled
  or reversed rows, allocation/refund mismatches, and invoice-source ambiguity;
- avoid DB access, R4 access, finance staging models, and PMS finance writes.

Expected validation:

- Focused unit tests for known/unknown flag combinations, cancellation handling,
  sign preservation, patient-code requirement, and reason codes.
- `git diff --check`.
- No R4 writes, no PMS DB writes, and no finance records created or changed.
