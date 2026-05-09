# R4 Finance Opening-Balance Full Eligible-Row Artefact Package Evidence

Status date: 2026-05-09

Evidence timestamp: `2026-05-09T16:52:25+00:00`

Request ID: `r4ob-full-eligible-request-20260509-000001`

Origin master at package creation/access time:
`4d7cfd920dc8b6a9e7b1af1422fef8d0fb2c22af`

This is the first standing-authorised non-live full eligible-row artefact
package creation/access evidence slice for the approved request ID above. It
records safe package hashes, counts, totals, storage classification, and guard
outcomes only.

This evidence summary does not commit raw artefact contents, patient-level row
contents, patient names, dates of birth, addresses, phone numbers, emails,
clinical details, unredacted DSNs, secrets, or production/live-looking target
details.

Owner sign-off for this package evidence is recorded separately at:
`docs/r4/R4_FINANCE_OPENING_BALANCE_FULL_ELIGIBLE_ARTEFACT_PACKAGE_EVIDENCE_SIGNOFF.md`.
That sign-off is limited to package-evidence review and does not authorise
guarded apply/write, live/default PMS DB writes, actual PMS Postgres writes,
production execution, live finance import, invoice/payment/staging import, or
committing raw artefact or patient-level contents.

`finance_import_ready=false`. Migration/import is not complete. Production
readiness is not established. Live finance import remains out of scope.

## Package Scope

| Field | Value |
| --- | --- |
| Request ID | `r4ob-full-eligible-request-20260509-000001` |
| Manifest ID | `r4ob-full-eligible-20260509-000001` |
| Source system | R4 `PatientStats` opening-balance source context |
| Source artefact SHA256 | `357400cf5c1a53a8b34b6b0d7589b57b76754603946282d794b1881f71f75755` |
| Manifest checksum | `3b902805b138700441ba99b15eb2dadef34829fa3d3544383c0e387142f5a51b` |
| Package summary SHA256 | `25c15e9ebcd018c108dfca758ce04d6463f0520af0c918c4ee97f7cfc8aeb872` |
| Source `PatientStats` rows considered | `17017` |
| Eligible row count | `1018` |
| Excluded row count | `15999` |
| Expected total | `-131187.13` |
| Expected total pence | `-13118713` |
| Currency/decimal policy | GBP values stored as exact pence; any later rounding or precision discrepancy stops validation/apply. |
| Storage classification | Non-repo and access-controlled. |

The non-repo artefact store uses an owner-local, access-controlled directory
with mode `700`, and package files use mode `600`. The exact path is not
committed. Redacted storage shape:
`<owner-local-nonrepo-r4-artefact-store>/r4ob-full-eligible-request-20260509-000001/`.

## Classification Summary

| Classification | Count |
| --- | ---: |
| Eligible opening-balance rows | `1018` |
| Excluded/no-op zero-balance rows | `15999` |

| Raw sign | Count |
| --- | ---: |
| Negative | `727` |
| Positive | `291` |

| Proposed PMS direction | Count |
| --- | ---: |
| Decrease debt or credit | `727` |
| Increase debt | `291` |

Eligible package rows are non-zero `PatientStats` balances with a valid patient
code, exact pence amount, and passing component and treatment split checks.
Zero-balance rows are excluded/no-op. Negative balances are classified as
decrease-debt-or-credit candidates and remain subject to later validation/apply
guards before any execution proof.

Duplicate eligible `PatientStats` patient codes fail closed. No duplicate
eligible patient codes were detected in this package.

## Artefact And Manifest Handling

- The source artefact is stored outside the repository.
- The manifest is stored outside the repository.
- Raw source rows are not committed.
- Patient-level row contents are not committed.
- The committed docs record only safe hashes, counts, totals, classifications,
  and guard outcomes.

Redacted command shape:

```text
python <standalone package extraction script>
  [R4 SQL Server env loaded from owner-local secret file]
  [SELECT-only PatientStats query]
  [write source artefact and manifest to non-repo access-controlled store]
```

The command shape is redacted to omit hostnames, usernames, passwords, DSNs,
exact storage paths, and patient-level output.

## Access And Guard Outcomes

| Guard | Result |
| --- | --- |
| R4 access occurred | Yes, limited to SELECT-only `PatientStats` extraction for the approved package request. |
| Real artefact access occurred | Yes, limited to creating, hashing, and manifesting the approved non-repo package. |
| Patient-level contents committed | No |
| Raw artefact committed | No |
| PMS DB connection occurred | No |
| Local scratch SQLite DB opened or queried | No |
| Validation/no-write run | No |
| Guarded apply/write run | No |
| Finance import started | No |
| Live/default PMS DB writes | No |
| Actual PMS Postgres writes | No |
| Invoice/payment/staging import | No |

## Non-Authorisation

This evidence summary does not authorise validation/no-write.

This evidence summary does not authorise guarded apply/write.

This evidence summary does not authorise live finance import, production
execution, live/default PMS DB writes, actual PMS Postgres writes, invoice
import, payment import, staging import, or full migration/import completion.

## Remaining Future Gates

Any later slice must still pass the documented gates and stop conditions before
it proceeds:

1. manifest/checksum/expected-total review and sign-off;
2. scratch/test target approval;
3. validation/no-write authorisation;
4. validation/no-write evidence recording and sign-off;
5. guarded apply/write readiness check;
6. separate guarded apply/write authorisation;
7. guarded apply/write proof evidence recording and sign-off;
8. any live import decision, which remains separate and unauthorised.
