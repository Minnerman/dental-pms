# R4 Finance Opening-Balance Full Eligible-Row Artefact Package Evidence Sign-Off

Status date: 2026-05-09

Latest origin/master at sign-off time:
`edebf6d6803561a55de2ed5199015f4248fdf120`

This is an owner sign-off record for the full eligible-row artefact package
evidence only.

This sign-off does not access R4, access/hash/inspect a real artefact, use
patient data, connect to a PMS database, run validation/no-write, run guarded
apply/write, create or change finance records, or perform finance import.

`finance_import_ready=false`. Migration/import is not complete. Production
readiness is not established. Full eligible-row validation/no-write has not
run. Full eligible-row guarded apply/write has not run.

## Evidence Boundaries

| Field | Signed-off value |
| --- | --- |
| Request ID | `r4ob-full-eligible-request-20260509-000001` |
| Manifest ID | `r4ob-full-eligible-20260509-000001` |
| Evidence document | `docs/r4/R4_FINANCE_OPENING_BALANCE_FULL_ELIGIBLE_ARTEFACT_PACKAGE_EVIDENCE.md` |
| Source artefact SHA256 | `357400cf5c1a53a8b34b6b0d7589b57b76754603946282d794b1881f71f75755` |
| Manifest checksum | `3b902805b138700441ba99b15eb2dadef34829fa3d3544383c0e387142f5a51b` |
| Package summary SHA256 | `25c15e9ebcd018c108dfca758ce04d6463f0520af0c918c4ee97f7cfc8aeb872` |
| Eligible row count | `1018` |
| Excluded row count | `15999` |
| Expected total | `-131187.13` |

The owner accepts that the evidence records no committed patient-level contents
and no committed raw artefact contents.

## Sign-Off Scope

The package-evidence review is accepted for the values listed above. This
clears the package-evidence review gate, making scratch/test-only
validation/no-write the next standing-authorised non-live stage for this
request.

Validation/no-write remains a future non-live slice under the standing
authorisation. This sign-off record does not run validation/no-write and does
not record validation/no-write evidence.

Validation/no-write evidence for the next non-live slice is now recorded
separately at
`docs/r4/R4_FINANCE_OPENING_BALANCE_FULL_ELIGIBLE_VALIDATION_NOWRITE_EVIDENCE.md`.
That evidence remains no-write only and does not authorise guarded apply/write.

## Explicit Non-Authorisations

This sign-off does not authorise:

- guarded apply/write;
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

The next eligible slice is scratch/test-only validation/no-write for request
`r4ob-full-eligible-request-20260509-000001`, subject to all standing
authorisation guards and stop conditions.

Guarded apply/write remains unauthorised by this sign-off and must receive
separate explicit authorisation after validation/no-write evidence review and
sign-off.
