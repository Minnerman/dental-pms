# R4 Finance Opening-Balance Full Eligible-Row Guarded Apply Sign-Off

Status date: 2026-05-09

Latest origin/master at sign-off time:
`3df7bebe4de5a974645aa692fb4327fc84b6bd67`

This is an owner sign-off record for the full eligible-row scratch/test-only
guarded apply/write proof evidence only.

This sign-off slice does not access R4, access/hash/inspect a real artefact,
use patient data, connect to a PMS database, rerun guarded apply/write, rerun
validation/no-write, create or change finance records, or perform finance
import.

`finance_import_ready=false`. Migration/import is not complete. Production
readiness is not established. Live/default PMS execution is not authorised.
Live finance import remains unauthorised.

## Evidence Boundaries

| Field | Signed-off value |
| --- | --- |
| Request ID | `r4ob-full-eligible-request-20260509-000001` |
| Manifest ID | `r4ob-full-eligible-20260509-000001` |
| Guarded apply evidence document | `docs/r4/R4_FINANCE_OPENING_BALANCE_FULL_ELIGIBLE_GUARDED_APPLY_EVIDENCE.md` |
| Source artefact SHA256 | `357400cf5c1a53a8b34b6b0d7589b57b76754603946282d794b1881f71f75755` |
| Manifest checksum | `3b902805b138700441ba99b15eb2dadef34829fa3d3544383c0e387142f5a51b` |
| Package summary SHA256 | `25c15e9ebcd018c108dfca758ce04d6463f0520af0c918c4ee97f7cfc8aeb872` |
| Eligible row count | `1018` |
| Excluded row count | `15999` |
| Expected total | `-131187.13` |
| Target classification | local isolated SQLite scratch/test only |
| First-run counts | exit `0`, `created=1018`, `updated=0`, `skipped=0`, `refused=15999` |
| Second-run counts | exit `0`, `created=0`, `updated=0`, `skipped=1018`, `refused=15999` |
| Query verification | count `1018`, total `-131187.13`, duplicate references `0` |
| Invoice count | `0` |
| Payment count | `0` |
| Staging/import count | `0` |
| Transient apply input JSON SHA256 | `91bc8542c0a18aed36e71854d6e69e6a0730af930942d0562b4a4cf64089e8ac` |
| First output JSON SHA256 | `faa1e43d6c960bf0a9a54ae3abacbbfa469eecf658ff3e2a741c5e8d19a03b42` |
| First stdout JSON SHA256 | `0a75cf1c7bd5430c1116ac4e5ff7fb8c4b5e4413c4fa35401b85e72f461a98dd` |
| Second output JSON SHA256 | `f6aa65f54e85357c2e4d9766299079831930d6ff1ec231c133a4a12c6ee12316` |
| Second stdout JSON SHA256 | `fbd9f2fe23e1528096844298726bbf5b1d60f4eaf5b8c3de1516aa4ac027596c` |
| Query verification JSON SHA256 | `40dff20545a2ca8ac990ef077423114b95a80d441858aeb6c6910d6bcf59593c` |

The owner accepts that the proof evidence records:

- local isolated SQLite scratch/test target only;
- guarded apply/write flags and actor guard used in the original proof only;
- first run created `1018` scratch/test `PatientLedgerEntry` rows and
  refused `15999` source rows;
- second run created `0` rows and skipped `1018` existing rows;
- query verification count `1018` and total `-131187.13`;
- duplicate references `0`;
- invoice count `0`;
- payment count `0`;
- staging/import count `0`;
- no live/default PMS DB writes;
- no actual PMS Postgres writes;
- no finance import;
- no invoice/payment/staging import;
- no committed patient-level contents;
- no committed raw artefact contents.

## Sign-Off Scope

The owner accepts the full eligible-row guarded apply/write proof evidence as a
non-live scratch/test proof only.

This sign-off does not authorise a live/default PMS DB run, actual PMS
Postgres run, production execution, live finance import, invoice/payment/staging
import, migration completion, or production readiness.

## Explicit Non-Authorisations

This sign-off does not authorise:

- live/default PMS DB writes;
- actual PMS Postgres writes;
- production execution;
- live finance import;
- invoice/payment/staging import;
- committing raw R4 artefact contents;
- committing patient names, dates of birth, addresses, phone numbers, emails,
  clinical details, or unredacted DSNs/secrets.

This sign-off does not permit patient-level contents, raw artefact contents,
exact storage paths, row-level ledger references, unredacted DSNs, or secrets
in committed docs, PRs, logs, or evidence summaries.

## Current Stop Point

The scratch/test-only guarded apply/write proof evidence is accepted for the
values listed above. Any further full eligible-row finance movement requires a
separate explicit owner decision and a new scoped slice. Live/default PMS DB
writes, actual PMS Postgres writes, production execution, live finance import,
invoice/payment/staging import, and committing raw artefact or patient-level
contents remain unauthorised.

Final non-live pathway status and next-decision boundaries are recorded in
`docs/r4/R4_FINANCE_OPENING_BALANCE_FULL_ELIGIBLE_COMPLETION_SUMMARY.md`.
