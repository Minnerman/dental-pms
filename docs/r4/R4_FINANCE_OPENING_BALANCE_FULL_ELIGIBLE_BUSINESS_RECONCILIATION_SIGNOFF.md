# R4 Finance Opening-Balance Full Eligible-Row Business Reconciliation Sign-Off

Status date: 2026-05-10

Baseline:
`origin/master@e80c9dad58c5e8e8d395a05939806cb305e9c7ee`

This is a docs-only record of owner business/accounting reconciliation sign-off
for the completed R4 opening-balance full eligible-row non-live evidence.

This record does not access R4, access/hash/inspect real artefacts, use patient
data, connect to any PMS database, open or query local scratch SQLite, rerun
validation/no-write, rerun guarded apply/write, perform finance import, perform
invoice/payment/staging import, perform live/default PMS DB writes, perform
actual PMS Postgres writes, or perform production cutover.

## Signed-Off Evidence

The owner has reviewed the R4 opening-balance full eligible-row non-live
evidence from a business/accounting perspective and accepts the following
reconciliation facts:

| Field | Accepted Value |
| --- | --- |
| Request ID | `r4ob-full-eligible-request-20260509-000001` |
| Manifest ID | `r4ob-full-eligible-20260509-000001` |
| Eligible rows | `1018` |
| Excluded rows | `15999` |
| Expected total | `-131187.13` |
| Scratch/test proof created rows | `1018` opening-balance ledger rows |
| Second run duplicate rows created | `0` |
| Invoice/payment/staging-import counts | `0` / `0` / `0` |

The owner confirms these figures are acceptable for the non-live
opening-balance migration evidence.

## Scope Boundary

This business reconciliation sign-off is limited to the non-live
opening-balance evidence. It does not authorise:

- live/default PMS DB writes;
- actual PMS Postgres writes;
- production execution;
- live finance import;
- invoice/payment/staging import;
- making Dental PMS the live/main PMS.

R4 remains the live/main PMS until a separate production cutover decision is
made. Dental PMS is not authorised as the live/main PMS by this sign-off.
`finance_import_ready=false`; production readiness is not complete.

No patient-level contents, raw artefact contents, exact artefact paths,
patient codes, row-level ledger references, unredacted DSNs, or secrets are
committed by this sign-off record.
