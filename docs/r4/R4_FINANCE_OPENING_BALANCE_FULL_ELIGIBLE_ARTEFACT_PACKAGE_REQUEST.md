# R4 Finance Opening-Balance Full Eligible-Row Artefact Package Request

Status date: 2026-05-09

Baseline: `origin/master@af8e8c61532cc59abf69f63dd19eedc82db6dff3`

This is a request, proposal, and template document only. It defines what would
need to be requested and approved before any future full eligible-row
opening-balance artefact package can be created, accessed, hashed, stored,
validated, or executed.

This document does not authorise artefact creation, artefact access, artefact
copying, artefact hashing, artefact storage, validation/no-write, guarded
apply/write, execution, import, or production use.

No R4 access occurred. No real R4 artefact was accessed. No real patient data
was used. No PMS database connection occurred. No scratch execution is
authorised by this request/template.

`finance_import_ready=false`. Live finance import remains out of scope.
Migration/import is not complete. Production readiness is not established.

Owner sign-off for this request/template is recorded separately at:
`docs/r4/R4_FINANCE_OPENING_BALANCE_FULL_ELIGIBLE_ARTEFACT_PACKAGE_REQUEST_SIGNOFF.md`.
That sign-off accepts this request/template as the required structure for any
future full eligible-row artefact package request only. It does not authorise
R4 access, real artefact access, artefact creation/copying/hashing/storage,
validation, execution, real patient data use, PMS DB connection, guarded
scratch apply, CLI validation/no-write, live/default PMS writes, actual PMS
Postgres writes, finance import, invoice/payment/staging import, production
execution, or full eligible-row artefact execution.

A later readiness/gap assessment for creating a specific request record is
recorded at:
`docs/r4/R4_FINANCE_OPENING_BALANCE_FULL_ELIGIBLE_ARTEFACT_PACKAGE_REQUEST_READINESS.md`.
That note does not create a specific request record and does not authorise
artefact creation, artefact access, validation/no-write, guarded apply/write,
finance import, live import, or production use.

A later docs-only candidate request record is recorded at:
`docs/r4/R4_FINANCE_OPENING_BALANCE_FULL_ELIGIBLE_ARTEFACT_PACKAGE_REQUEST_CANDIDATE.md`.
That candidate records role labels and owner approval to create the candidate
repo record only. It does not create or authorise any artefact, R4 access,
patient data use, PMS DB connection, validation/no-write, guarded apply/write,
finance import, live import, or production use.

A later owner-authorised docs-only request record is recorded at:
`docs/r4/R4_FINANCE_OPENING_BALANCE_FULL_ELIGIBLE_ARTEFACT_PACKAGE_REQUEST_RECORD_20260509.md`.
That record fills owner-authorised, non-sensitive request metadata and request
ID `r4ob-full-eligible-request-20260509-000001`. It remains a request record
only and does not authorise artefact creation/access, R4 access, validation,
guarded apply/write, PMS DB connection, finance import, live import, production
use, or full eligible-row artefact execution.

## Relationship To Completed Bounded Fixture Pathway

The bounded-fixture pathway is complete through signed-off local isolated
scratch/test guarded apply/write proof evidence for the approved bounded fixture
only. That proof is bounded to manifest `ob-bounded-fixture-20260507-000001`,
fixture/source SHA256
`2afabfcb903b0f4e5a94702ae93b7752e9309e30116a4d01e1f55ec84465b53d`, and
manifest SHA256
`66cc1c7ac16a4e677dfea6994cef86a5b7c496a00fbfec10336fa7641d98bb67`.

This request concerns future full eligible-row artefact package governance only.
It does not prove the full eligible-row artefact path, does not authorise another
scratch execution, and does not imply live finance import or production
migration readiness. The full eligible-row artefact proof is not done.

## Requested Package Contents

A future full eligible-row artefact package request must define:

- request ID convention;
- requesting owner;
- approving owner or role;
- artefact owner;
- source system description;
- extraction purpose;
- extraction method description, without performing extraction in this request;
- extraction window or effective date requirement;
- creation timestamp requirement;
- operator or actor identifier requirement where safe and non-sensitive;
- source artefact naming convention;
- manifest naming convention;
- manifest ID convention;
- source artefact SHA256 requirement;
- manifest checksum requirement;
- repo SHA requirement;
- tool, CLI version, or commit SHA requirement;
- expected total requirement;
- eligible row count requirement;
- excluded row count requirement, if applicable;
- inclusion and exclusion rules;
- zero and negative balance policy;
- duplicate handling policy;
- currency and decimal precision policy;
- storage location approval requirement;
- scratch/test-only target classification requirement;
- redacted command shape requirement.

The request must not include full artefact contents or patient-level rows.

## Required Approvals Before Artefact Creation Or Access

Future work must pass these approvals and gates in order:

1. Owner approval to create or obtain the artefact.
2. Provenance approval.
3. Redaction and storage approval.
4. Artefact storage and access-control approval.
5. Manifest, checksum, and expected-total approval.
6. Scratch/test target approval.
7. Validation/no-write authorisation.
8. Validation/no-write evidence review and sign-off.
9. Guarded apply/write readiness check.
10. Separate guarded apply/write authorisation.
11. Guarded apply/write evidence review and sign-off.
12. Post-proof decision.
13. Live import remains separate and unauthorised.

No gate is satisfied by this request/template alone.

## Request Form Template

Use placeholder text only. Do not fill this template with real patient data,
real artefact details, real R4 row contents, unredacted DSNs, or secrets.

| Field | Placeholder |
| --- | --- |
| Request ID | `<request-id>` |
| Requested by | `<requesting-owner-or-role>` |
| Artefact owner | `<artefact-owner-or-role>` |
| Approving owner | `<approving-owner-or-role>` |
| Source system | `<source-system-description>` |
| Extraction purpose | `<purpose-summary>` |
| Extraction method | `<method-description-without-performing-extraction>` |
| Extraction effective date | `<effective-date-or-window>` |
| Creation timestamp | `<creation-timestamp-to-be-recorded-later>` |
| Operator/actor identifier | `<safe-non-sensitive-operator-or-actor-id>` |
| Expected artefact location policy | `<approved-storage-location-policy>` |
| Manifest ID | `<manifest-id>` |
| Source artefact SHA256 | `<source-artefact-sha256>` |
| Manifest checksum | `<manifest-checksum>` |
| Expected total | `<expected-total>` |
| Eligible row count | `<eligible-row-count>` |
| Excluded row count | `<excluded-row-count-if-applicable>` |
| Repo SHA | `<repo-sha>` |
| Tool/CLI version or commit SHA | `<tool-or-cli-version-or-commit-sha>` |
| Inclusion rules | `<inclusion-rules>` |
| Exclusion rules | `<exclusion-rules>` |
| Zero/negative balance policy | `<zero-negative-balance-policy>` |
| Duplicate handling policy | `<duplicate-handling-policy>` |
| Currency/decimal policy | `<currency-decimal-policy>` |
| Storage approval | `<storage-approval-status>` |
| Redaction approval | `<redaction-approval-status>` |
| Scratch/test target approval | `<scratch-test-target-approval-status>` |
| Validation/no-write authorisation | `<validation-no-write-authorisation-status>` |
| Guarded apply/write authorisation | `<guarded-apply-write-authorisation-status>` |
| Notes | `<non-sensitive-notes>` |

## Redaction And Storage Rules

Future artefact handling must satisfy these rules before artefact creation or
use:

- no full artefact contents in committed docs;
- no real patient names in committed docs;
- no DOBs in committed docs;
- no addresses in committed docs;
- no phone numbers in committed docs;
- no emails in committed docs;
- no clinical details in committed docs;
- no unredacted DSNs or secrets in committed docs;
- no production/live-looking target details in committed docs;
- artefact storage location must be approved before artefact creation or use;
- storage must be access-controlled;
- stored artefact should be immutable for the evidence window;
- evidence docs may record hashes, counts, and totals, but not patient-level
  contents;
- runtime output must be reviewed before committing any summary;
- redacted command shape must not include secrets.

## Future Validation/No-Write Evidence Requirements

A future validation/no-write slice must preserve:

- manifest ID;
- manifest checksum;
- source artefact hash;
- eligible row count;
- excluded row count, if applicable;
- expected total;
- target classification;
- repo SHA;
- tool, CLI version, or commit SHA;
- redacted command shape;
- confirmation that `--apply` was not used;
- confirmation that no apply confirmation was supplied;
- confirmation that no actor ID was supplied unless the current design requires
  one for no-write validation;
- CLI exit code and result;
- created, updated, skipped, and refused counts;
- confirmation of no DB writes, or if local scratch/test connection is required,
  exact target classification and confirmation that no rows were created;
- confirmation no live/default PMS database and no actual PMS Postgres were
  used;
- confirmation no R4 access occurred during validation;
- evidence output path and SHA256.

Validation/no-write evidence must not be treated as apply/write authorisation.

## Future Guarded Apply/Write Evidence Requirements

A future guarded apply/write slice must be separately authorised and must
preserve:

- manifest ID;
- manifest checksum;
- source artefact hash;
- eligible row count;
- excluded row count, if applicable;
- expected total;
- target classification;
- repo SHA;
- tool, CLI version, or commit SHA;
- redacted command shape;
- confirmation that `--apply` was used;
- confirmation that exact `--confirm SCRATCH_OPENING_BALANCE_APPLY` was used;
- confirmation that `--actor-id` was used;
- first-run created, updated, skipped, and refused counts;
- first-run total;
- second-run idempotency counts;
- duplicate protection result;
- manifest-scoped reference checks;
- query verification count and total;
- invoice count;
- payment count;
- confirmation no live/default PMS database and no actual PMS Postgres were
  used;
- confirmation no R4 access occurred during apply proof;
- confirmation no finance import, staging import, invoice import, or payment
  import occurred;
- evidence output paths and SHA256 hashes.

The future apply/write proof must use a clearly isolated scratch/test target
only. It must not use live/default PMS, actual PMS Postgres, production-looking,
or ambiguous targets.

## Rejection Criteria

Reject the future package request or stop before artefact creation/access if any
item is present:

- missing owner approval;
- missing provenance;
- missing redaction/storage approval;
- missing artefact storage/access-control approval;
- missing source artefact hash;
- missing manifest checksum;
- missing expected total;
- missing eligible count;
- missing repo SHA;
- unredacted DSN or secret;
- patient names, DOBs, addresses, phone numbers, emails, clinical details, or
  full artefact contents in committed docs;
- target not clearly scratch/test;
- target resembles live/default/production;
- actual PMS Postgres target;
- checksum, total, count, or repo SHA mismatch;
- missing validation/no-write evidence;
- missing validation/no-write sign-off;
- missing guarded apply authorisation;
- missing `--apply` for an apply slice;
- wrong `--confirm` value;
- missing `--actor-id`;
- unexpected write path;
- idempotency failure;
- rollback or cleanup ambiguity;
- invoice, payment, or staging intent;
- any finance import request.

## Request-Slice Stop Conditions

Stop this request/proposal slice if any future task would require:

- R4 access;
- real R4 artefact access;
- patient data;
- PMS DB connection or write;
- CLI validation or guarded apply execution;
- backend, frontend, Docker, compose, runtime, or ops changes;
- wording that implies live import or production readiness;
- real artefact contents or patient-level details in committed docs.

## Next Conservative Slice

The next safe slice is owner review of this package request/template. Any
artefact creation, artefact access, validation/no-write, guarded apply/write,
or live import remains separate and unauthorised until the appropriate approval
gates are explicitly satisfied in later slices.
