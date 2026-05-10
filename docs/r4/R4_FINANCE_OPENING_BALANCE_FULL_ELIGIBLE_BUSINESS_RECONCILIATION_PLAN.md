# R4 Finance Opening-Balance Full Eligible-Row Business Reconciliation Plan

Status date: 2026-05-10

Baseline:
`origin/master@26e2dc14d9af0620388b9b1db9ba25a522fa434e`

This is a docs-only independent human/business reconciliation plan for the
completed R4 opening-balance full eligible-row non-live pathway.

This plan does not perform reconciliation and does not access patient-level
data. It does not access R4, access/hash/inspect any real artefact, use patient
data, connect to any PMS database, open or query scratch SQLite, rerun
validation/no-write, rerun guarded apply/write, create finance records, perform
finance import, perform invoice/payment/staging import, or perform production
cutover work.

The completed non-live evidence should be reviewed by the owner/business before
any production cutover/readiness planning.

R4 remains the live/main PMS. Dental PMS is not authorised as the live/main PMS.
`finance_import_ready=false`. Live finance import, production readiness/cutover,
live/default PMS DB writes, actual PMS Postgres writes, and
invoice/payment/staging import are not authorised.

## Evidence To Review

The owner/business reconciliation review should use the committed evidence
records only:

- final completion summary:
  `docs/r4/R4_FINANCE_OPENING_BALANCE_FULL_ELIGIBLE_COMPLETION_SUMMARY.md`
- package evidence:
  `docs/r4/R4_FINANCE_OPENING_BALANCE_FULL_ELIGIBLE_ARTEFACT_PACKAGE_EVIDENCE.md`
- package evidence sign-off:
  `docs/r4/R4_FINANCE_OPENING_BALANCE_FULL_ELIGIBLE_ARTEFACT_PACKAGE_EVIDENCE_SIGNOFF.md`
- validation/no-write evidence:
  `docs/r4/R4_FINANCE_OPENING_BALANCE_FULL_ELIGIBLE_VALIDATION_NOWRITE_EVIDENCE.md`
- validation/no-write sign-off:
  `docs/r4/R4_FINANCE_OPENING_BALANCE_FULL_ELIGIBLE_VALIDATION_NOWRITE_SIGNOFF.md`
- guarded apply/write proof evidence:
  `docs/r4/R4_FINANCE_OPENING_BALANCE_FULL_ELIGIBLE_GUARDED_APPLY_EVIDENCE.md`
- guarded apply/write proof sign-off:
  `docs/r4/R4_FINANCE_OPENING_BALANCE_FULL_ELIGIBLE_GUARDED_APPLY_SIGNOFF.md`
- standing authorisation:
  `docs/r4/R4_FINANCE_OPENING_BALANCE_FULL_ELIGIBLE_ARTEFACT_STANDING_AUTHORISATION.md`
- bounded-fixture pathway completion summary:
  `docs/r4/R4_FINANCE_OPENING_BALANCE_BOUNDED_FIXTURE_COMPLETION_SUMMARY.md`

No patient-level contents, raw artefact contents, exact storage paths, patient
codes, row-level ledger references, unredacted DSNs, or secrets should be
introduced into committed reconciliation notes.

## Bound Values

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
| Validation/no-write actual counts | `created=0`, `updated=0`, `skipped=0`, `refused=0` |
| Validation/no-write plan counts | `would_create=1018`, `would_refuse=15999` |
| First guarded proof run | `created=1018`, `updated=0`, `skipped=0`, `refused=15999` |
| Second guarded proof run | `created=0`, `updated=0`, `skipped=1018`, `refused=15999` |
| Query verification | count `1018`, total `-131187.13`, duplicate references `0` |
| Invoice/payment/staging-import counts | `0` / `0` / `0` |

## Reconciliation Checklist

The owner/business reviewer should confirm:

- request ID matches `r4ob-full-eligible-request-20260509-000001`;
- manifest ID matches `r4ob-full-eligible-20260509-000001`;
- source artefact SHA256 matches the committed evidence value;
- manifest checksum matches the committed evidence value;
- package summary SHA256 matches the committed evidence value;
- eligible row count is `1018`;
- excluded row count is `15999`;
- expected total is `-131187.13`;
- validation/no-write evidence was reviewed;
- validation/no-write actual counts are `created=0`, `updated=0`,
  `skipped=0`, `refused=0`;
- validation/no-write plan-only counts are `would_create=1018` and
  `would_refuse=15999`;
- guarded apply/write first-run evidence was reviewed;
- guarded apply/write first-run counts are `created=1018`, `updated=0`,
  `skipped=0`, `refused=15999`;
- guarded apply/write idempotency evidence was reviewed;
- guarded apply/write second-run counts are `created=0`, `updated=0`,
  `skipped=1018`, `refused=15999`;
- query verification count is `1018`;
- query verification total is `-131187.13`;
- duplicate references count is `0`;
- invoice/payment/staging-import counts are `0` / `0` / `0`;
- no patient-level contents were committed;
- no raw artefact contents were committed;
- live finance import remains unauthorised.

## Acceptance Criteria

The owner/business reconciliation can be accepted only if:

- all IDs and hashes match the committed evidence;
- eligible and excluded counts are accepted;
- expected total is accepted;
- validation/no-write evidence is accepted;
- guarded apply/write proof evidence is accepted;
- there are no unexpected invoices, payments, staging records, or import
  records;
- R4 remains the live/main PMS until separate cutover approval;
- no live import or production execution is performed without separate explicit
  owner approval.

## Stop Conditions

Stop reconciliation and record the blocker if any of the following occurs:

- any hash, count, total, or ID does not match the committed evidence;
- excluded-row policy is uncertain;
- negative-balance handling is uncertain;
- there is concern that committed evidence hides a business-significant issue;
- the reviewer needs patient-level detail in committed docs;
- live import is requested before production planning;
- Dental PMS live/main PMS status is requested before cutover approval.

## Next Decision Options

After reviewing this plan, the conservative next decisions are:

- pause and keep R4 live;
- complete manual/business reconciliation and record sign-off in a later
  docs-only PR;
- create a production cutover/readiness plan as a separate docs-only planning
  slice;
- defer live finance import until explicit production approval.

Any later reconciliation sign-off still must not by itself authorise live
finance import, live/default PMS DB writes, actual PMS Postgres writes,
production execution, cutover, or Dental PMS live/main PMS status unless that
authorisation is explicit, separate, and owner-approved.
