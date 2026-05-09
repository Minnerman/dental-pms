# R4 Finance Opening-Balance Full Eligible-Row Validation/No-Write Sign-Off

Status date: 2026-05-09

Latest origin/master at sign-off time:
`aa36669d86d85dac45e33d172eaa4467c6a0f246`

This is an owner sign-off record for the full eligible-row validation/no-write
evidence only.

This sign-off does not access R4, access/hash/inspect a real artefact, use
patient data, connect to a PMS database, rerun validation/no-write, run guarded
apply/write, create or change finance records, or perform finance import.

`finance_import_ready=false`. Migration/import is not complete. Production
readiness is not established. At this sign-off time, full eligible-row guarded
apply/write had not run.

## Evidence Boundaries

| Field | Signed-off value |
| --- | --- |
| Request ID | `r4ob-full-eligible-request-20260509-000001` |
| Manifest ID | `r4ob-full-eligible-20260509-000001` |
| Validation/no-write evidence document | `docs/r4/R4_FINANCE_OPENING_BALANCE_FULL_ELIGIBLE_VALIDATION_NOWRITE_EVIDENCE.md` |
| Source artefact SHA256 | `357400cf5c1a53a8b34b6b0d7589b57b76754603946282d794b1881f71f75755` |
| Manifest checksum | `3b902805b138700441ba99b15eb2dadef34829fa3d3544383c0e387142f5a51b` |
| Package summary SHA256 | `25c15e9ebcd018c108dfca758ce04d6463f0520af0c918c4ee97f7cfc8aeb872` |
| Eligible row count | `1018` |
| Excluded row count | `15999` |
| Expected total | `-131187.13` |
| Validation input JSON SHA256 | `29f42c0c8e8396cea0eba5e5a76fb37dceb2f24b5ce4a8c001e97a52239ed43b` |
| Validation output JSON SHA256 | `8f5831649d96b19881c330aa0798da40b6fb851bc6acf72ec6e914f70a6a273d` |
| Source aggregate check JSON SHA256 | `31be7121c2c753c665b7a43529a203bed085e5b76309b602198be586d9b0577f` |
| Actual write counts | `created=0`, `updated=0`, `skipped=0`, `refused=0` |
| Plan-only counts | `would_create=1018`, `would_refuse=15999` |

The owner accepts that validation/no-write completed with no `--apply`, no
`--confirm`, no PMS DB connection, no DB writes, no live/default PMS DB, no
actual PMS Postgres, no guarded apply/write, no finance import, no committed
patient-level contents, and no committed raw artefact contents.

## Sign-Off Scope

The validation/no-write evidence review is accepted for the values listed
above. This clears the validation/no-write evidence-review gate for the next
standing-authorised non-live stage: scratch/test-only guarded apply/write
proof.

At this sign-off time, guarded apply/write remained a future non-live slice
under the standing authorisation. That future slice had to re-check all documented provenance,
manifest, checksum, expected-total, count, repo-SHA, scratch/test target, and
command guards before any proof run.

This sign-off record does not run guarded apply/write and does not record
guarded apply/write evidence.

Guarded apply/write proof evidence for the next non-live slice is now recorded
separately at
`docs/r4/R4_FINANCE_OPENING_BALANCE_FULL_ELIGIBLE_GUARDED_APPLY_EVIDENCE.md`.
That evidence remains scratch/test-only and does not authorise live/default PMS
DB writes, actual PMS Postgres writes, production execution, live finance
import, or invoice/payment/staging import.

## Explicit Non-Authorisations

This sign-off does not authorise:

- live/default PMS DB writes;
- actual PMS Postgres writes;
- production execution;
- live finance import;
- invoice, payment, or staging import;
- committing raw R4 artefact contents;
- committing patient names, dates of birth, addresses, phone numbers, emails,
  clinical details, or unredacted DSNs/secrets.

This sign-off does not permit patient-level contents, raw artefact contents,
exact storage paths, unredacted DSNs, or secrets in committed docs, PRs, logs,
or evidence summaries.

## Current Stop Point

The next eligible slice is scratch/test-only guarded apply/write proof for
request `r4ob-full-eligible-request-20260509-000001`, subject to all standing
authorisation guards and stop conditions.

That proof evidence is now recorded in
`docs/r4/R4_FINANCE_OPENING_BALANCE_FULL_ELIGIBLE_GUARDED_APPLY_EVIDENCE.md`;
the next gate is owner review/sign-off of that proof evidence.

Live/default PMS DB writes, actual PMS Postgres writes, production execution,
live finance import, invoice/payment/staging import, and committing raw
artefact or patient-level contents remain unauthorised.
