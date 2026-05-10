# R4 Finance Opening-Balance Full Eligible-Row Completion Summary

Status date: 2026-05-10

Baseline:
`origin/master@518344357339a9415b3d77b95d897b86f570dbe3`

This document records the final status and next-decision boundary for the R4
opening-balance full eligible-row non-live pathway after signed-off
scratch/test-only guarded apply/write proof evidence.

The full eligible-row opening-balance non-live pathway is complete through
signed-off guarded apply/write proof. This is non-live proof only.

R4 remains the live/main PMS. Dental PMS is not authorised as the live/main PMS
by this work. `finance_import_ready=false`.

## Evidence Chain

Completed full eligible-row pathway records:

- standing authorisation:
  `docs/r4/R4_FINANCE_OPENING_BALANCE_FULL_ELIGIBLE_ARTEFACT_STANDING_AUTHORISATION.md`
- owner-authorised request record:
  `docs/r4/R4_FINANCE_OPENING_BALANCE_FULL_ELIGIBLE_ARTEFACT_PACKAGE_REQUEST_RECORD_20260509.md`
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

The bounded-fixture pathway was completed earlier in
`docs/r4/R4_FINANCE_OPENING_BALANCE_BOUNDED_FIXTURE_COMPLETION_SUMMARY.md`.
The full eligible-row pathway has now completed the same kind of non-live
evidence track: package evidence, validation/no-write evidence, guarded
apply/write proof evidence, and owner sign-off for each evidence gate.

## Bound Proof Values

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
| First proof run | exit `0`, `created=1018`, `updated=0`, `skipped=0`, `refused=15999` |
| Second proof run | exit `0`, `created=0`, `updated=0`, `skipped=1018`, `refused=15999` |
| Query verification | count `1018`, total `-131187.13`, duplicate references `0` |
| Invoice/payment/staging-import counts | `0` / `0` / `0` |
| Input JSON SHA256 | `91bc8542c0a18aed36e71854d6e69e6a0730af930942d0562b4a4cf64089e8ac` |
| First output JSON SHA256 | `faa1e43d6c960bf0a9a54ae3abacbbfa469eecf658ff3e2a741c5e8d19a03b42` |
| First stdout JSON SHA256 | `0a75cf1c7bd5430c1116ac4e5ff7fb8c4b5e4413c4fa35401b85e72f461a98dd` |
| Second output JSON SHA256 | `f6aa65f54e85357c2e4d9766299079831930d6ff1ec231c133a4a12c6ee12316` |
| Second stdout JSON SHA256 | `fbd9f2fe23e1528096844298726bbf5b1d60f4eaf5b8c3de1516aa4ac027596c` |
| Query verification JSON SHA256 | `40dff20545a2ca8ac990ef077423114b95a80d441858aeb6c6910d6bcf59593c` |

## Safety Boundary

No patient-level contents, raw artefact contents, exact storage paths, patient
codes, row-level ledger references, unredacted DSNs, or secrets are committed
by this completion summary.

This completion summary does not access R4, access or hash the real artefact,
use patient data, connect to any PMS database, open or query scratch SQLite,
rerun validation/no-write, rerun guarded apply/write, create finance records,
or perform finance import.

## Non-Authorisations

This completion summary does not authorise:

- live/default PMS DB writes;
- actual PMS Postgres writes;
- production execution or cutover;
- Dental PMS as live/main PMS;
- live finance import;
- invoice/payment/staging import;
- migration/import completion;
- committing raw R4 artefact contents;
- committing patient names, dates of birth, addresses, phone numbers, emails,
  clinical details, patient codes, row-level ledger references, exact storage
  paths, unredacted DSNs, or secrets.

`finance_import_ready=false`. Live finance import remains unauthorised.
Production readiness is not claimed. Live/default PMS execution is not
authorised.

## Next Decision Options

The conservative next decision options are:

- pause and keep R4 live;
- perform independent human/business reconciliation of the signed-off evidence;
- create a production cutover/readiness plan as a separate docs-only planning
  slice;
- defer live finance import until explicit production approval.

Any live import, live/default PMS DB write, actual PMS Postgres write,
production execution, cutover, or Dental PMS live/main PMS decision must remain
separate and requires new explicit owner approval.
