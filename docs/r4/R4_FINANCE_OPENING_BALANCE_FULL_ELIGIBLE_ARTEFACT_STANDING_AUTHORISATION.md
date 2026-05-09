# R4 Finance Opening-Balance Full Eligible-Row Artefact Standing Authorisation

Status date: 2026-05-09

Standing authorisation baseline:
`origin/master@f0f04be22ce55d29a6b214ce52b5fcc13eef72d1`

Request ID: `r4ob-full-eligible-request-20260509-000001`

This is a standing owner authorisation record. It records standing owner
authorisation for the non-live R4 opening-balance full eligible-row artefact
package pathway for the approved request ID above.

This PR itself is docs-only. This PR did not access R4, access a real R4
export, access/create/inspect/copy/hash/store/validate/execute a real full
eligible-row artefact, use real patient data, connect to any PMS database, open
or query a local scratch SQLite database, run validation/no-write, run guarded
apply/write, create or change finance records, or start finance import.

`finance_import_ready=false`. Migration/import is not complete. Production
readiness is not established. Full eligible-row artefact package creation,
validation/no-write, guarded apply/write proof, and idempotency proof have not
happened in this PR.

## Owner Roles

The owner is the business owner, project owner, data owner, artefact owner,
requesting owner, and approving owner for this Dental PMS migration work.

Use role labels only in committed docs for this pathway. Do not record personal
names.

## Scope Of Standing Authorisation

This standing authorisation is limited to the approved full eligible-row
artefact package request:

- request record:
  `docs/r4/R4_FINANCE_OPENING_BALANCE_FULL_ELIGIBLE_ARTEFACT_PACKAGE_REQUEST_RECORD_20260509.md`
- request ID: `r4ob-full-eligible-request-20260509-000001`

It authorises the following non-live stages, subject to every documented guard
and stop condition:

1. creation/access of the full eligible-row artefact from R4;
2. approved non-repo artefact storage;
3. artefact SHA256 hashing;
4. manifest creation;
5. manifest checksum creation;
6. eligible and excluded row count calculation;
7. expected total calculation;
8. redacted evidence summary creation;
9. scratch/test-only validation/no-write;
10. validation/no-write evidence recording;
11. scratch/test-only guarded apply/write proof;
12. second-run idempotency proof;
13. guarded apply/write proof evidence recording;
14. documentation/status updates and PRs required to record the above.

This standing authorisation allows R4 access and real artefact access only for
the approved artefact package pathway above. It does not allow broad R4 access,
unrelated artefact access, live/default PMS DB writes, actual PMS Postgres
writes, production execution, live finance import, or invoice/payment/staging
import.

## Required Guards

Every future stage remains subject to the documented provenance, redaction,
storage, manifest, checksum, expected-total, eligible-count, repo-SHA,
scratch/test target, and command-guard requirements recorded in:

- `docs/r4/R4_FINANCE_OPENING_BALANCE_FULL_ELIGIBLE_ARTEFACT_PACKAGE_REQUEST.md`
- `docs/r4/R4_FINANCE_OPENING_BALANCE_FULL_ELIGIBLE_ARTEFACT_PACKAGE_REQUEST_RECORD_20260509.md`
- `docs/r4/R4_FINANCE_OPENING_BALANCE_FULL_ELIGIBLE_ARTEFACT_PROVENANCE_REDACTION_PROPOSAL.md`
- `docs/r4/R4_FINANCE_OPENING_BALANCE_FULL_ELIGIBLE_ARTEFACT_PLAN.md`

No future stage may proceed if a guard is missing, ambiguous, failed, or
mismatched.

## Redaction Boundary

No patient-level contents may be committed in docs, PRs, logs, or evidence
summaries.

The standing authorisation does not authorise committing:

- raw R4 artefact contents;
- patient names;
- dates of birth;
- addresses;
- phone numbers;
- emails;
- clinical details;
- unredacted DSNs or secrets;
- production/live-looking target details.

Evidence summaries may record approved hashes, checksums, counts, totals,
repo SHAs, target classifications, redacted command shapes, and pass/fail
outcomes, but not patient-level rows or full artefact contents.

## Explicit Non-Authorisations

This standing authorisation does not authorise:

- live/default PMS DB writes;
- actual PMS Postgres writes;
- production execution;
- live finance import;
- invoice/payment/staging import;
- committing raw R4 artefact contents;
- committing patient names, dates of birth, addresses, phone numbers, emails,
  clinical details, or unredacted DSNs/secrets.

## Stop And Report Conditions

Codex must stop and report if:

- any guard fails;
- any checksum, total, count, repo SHA, or manifest value mismatches;
- artefact storage is not clearly approved, non-repo, and access-controlled;
- target classification is not clearly scratch/test;
- target resembles live/default/production;
- output contains patient-level contents or secrets;
- rollback or cleanup is ambiguous;
- validation/no-write produces unexpected writes;
- guarded apply/write proof creates unexpected rows;
- idempotency fails;
- finance import or live execution is requested.

## Current Stop Point

This record authorises future non-live staged work only. It is not itself an
artefact package, manifest, validation/no-write evidence, guarded apply/write
proof, idempotency proof, finance import, production execution, or migration
completion record.
