# R4 Finance Opening-Balance Full Eligible-Row Artefact Provenance And Redaction Proposal

Status date: 2026-05-08

Baseline: `origin/master@f8b07039595874e59bdfb79b8862b29e8f238184`

This is a proposal and planning document only. It defines governance for a
future full eligible-row opening-balance artefact package, but it does not
create, access, inspect, copy, hash, store, validate, or execute any real
full eligible-row artefact.

No full eligible-row artefact is included in this repository from this slice.
No R4 access occurred. No real artefact was accessed. No patient data was used.
No PMS database connection occurred. No scratch execution is authorised by this
proposal.

`finance_import_ready=false`. Live finance import remains out of scope.
Migration/import is not complete. Production readiness is not established.

## Relationship To Bounded Fixture Pathway

The bounded-fixture pathway is complete through signed-off local isolated
scratch/test guarded apply/write proof evidence for the approved bounded fixture
only:

- manifest ID: `ob-bounded-fixture-20260507-000001`
- fixture/source SHA256:
  `2afabfcb903b0f4e5a94702ae93b7752e9309e30116a4d01e1f55ec84465b53d`
- manifest SHA256:
  `66cc1c7ac16a4e677dfea6994cef86a5b7c496a00fbfec10336fa7641d98bb67`
- first apply evidence SHA256:
  `802d4ca94762e060037b97dc68bdd08ad40d17541f04493378f5a0125a567837`
- second idempotency evidence SHA256:
  `e83a3faf7a6b22045d11a98559f342618d81a192841079864d0e2688cdfa5e2b`
- local query verification evidence SHA256:
  `db8846ca82489a67a0979a5524fbb1e8f0cefe6d36db12630180e13293b762f0`

That bounded completion does not prove the full eligible-row artefact path. This
proposal concerns future full eligible-row artefact governance only. The full
eligible-row artefact proof is not done.

## Future Artefact Provenance Package

A future full eligible-row artefact package must be approved before any
validation/no-write or guarded apply/write slice is considered. The package must
record:

- artefact owner;
- approving owner or role;
- source system description;
- extraction purpose;
- extraction method description, without performing extraction in this proposal;
- extraction timestamp requirement;
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
- target classification requirement: scratch/test only;
- redacted command shape requirement.

The package must make provenance review possible without committing patient-level
contents or full artefact rows.

## Redaction And Storage Policy

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
- stored artefact should be hashable and immutable for the evidence window;
- evidence docs may record hashes, counts, and totals, but not patient-level
  contents;
- runtime output must be reviewed before committing any summary;
- redacted command shape must not include secrets.

The approved storage policy must define who can access the artefact, how the
artefact is named, how the immutable evidence window is enforced, and when the
artefact may be deleted or retained.

## Approval Gates

Future work must pass these gates in order:

1. Owner approval for creating or obtaining the artefact.
2. Provenance approval.
3. Redaction and storage approval.
4. Manifest, checksum, and expected-total approval.
5. Scratch/test target approval.
6. Validation/no-write authorisation.
7. Validation/no-write evidence review and sign-off.
8. Guarded apply/write readiness check.
9. Separate guarded apply/write authorisation.
10. Guarded apply/write evidence review and sign-off.
11. Post-proof decision: pause, revise, bounded rehearsal, or future migration
    planning.
12. Live import remains separate and unauthorised.

No gate is satisfied by this proposal alone.

## Required Future Validation/No-Write Evidence

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

## Required Future Guarded Apply/Write Evidence

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

Reject the future package or stop before execution if any item is present:

- missing owner approval;
- missing provenance;
- missing redaction/storage approval;
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

## Proposal-Slice Stop Conditions

Stop this planning/proposal slice if any future task would require:

- R4 access;
- real R4 artefact access;
- patient data;
- PMS DB connection or write;
- CLI validation or guarded apply execution;
- backend, frontend, Docker, compose, runtime, or ops changes;
- wording that implies live import or production readiness;
- real artefact contents or patient-level details in committed docs.

## Next Conservative Slice

The next safe slice is owner review of this proposal. Any artefact creation or
use remains separate and unauthorised until the appropriate owner approval,
provenance approval, redaction/storage approval, and target approval gates are
explicitly satisfied in later slices. Do not proceed to live import.
