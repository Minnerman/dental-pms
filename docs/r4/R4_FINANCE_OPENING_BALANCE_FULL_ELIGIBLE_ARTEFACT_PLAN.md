# R4 Finance Opening-Balance Full Eligible-Row Artefact Plan

Status date: 2026-05-08

Baseline: `origin/master@bc6d1eb2f5b9c8ba5950d531879467e8c58310bc`

This is a planning document only. It starts the future full eligible-row
opening-balance artefact track, but it does not create, access, inspect, copy,
hash, store, validate, or execute a real full eligible-row artefact.

No full eligible-row artefact exists in the repository from this slice.

## Planning Boundary

This slice did not:

- access R4;
- access, inspect, copy, hash, store, or create a real R4 artefact;
- use real patient data;
- connect to a PMS database;
- open or query a local scratch SQLite database;
- execute guarded scratch apply;
- rerun guarded scratch apply;
- run CLI validation/no-write;
- use `--apply`;
- use `--confirm`;
- create scratch-test finance records;
- perform live/default PMS database writes;
- perform actual PMS Postgres writes;
- start finance import;
- create finance import or staging models;
- perform invoice, payment, or staging import.

`finance_import_ready=false`. Live finance import remains out of scope.
Migration/import is not complete. Production readiness is not established.
Scratch execution is not authorised by this plan.

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

That completion is deliberately bounded. It does not prove the full eligible-row
artefact path, does not authorise another scratch execution, and does not imply
live finance import or production migration readiness. The full eligible-row
artefact proof is not done.

## Future Package Requirements

A future full eligible-row artefact package must exist and be approved before
any validation/no-write or guarded apply/write slice is considered. The package
must record:

- artefact owner and explicit approval record;
- source system and provenance statement;
- extraction method description, without performing extraction in this plan;
- creation timestamp;
- artefact storage location policy, without committing artefact contents;
- source artefact SHA256 hash;
- manifest ID;
- manifest checksum;
- eligible row count;
- excluded row count, if applicable;
- expected total;
- currency and decimal policy;
- repo SHA;
- tool, CLI version, or commit SHA used to produce the artefact;
- redacted command shape;
- target classification: scratch/test only;
- inclusion and exclusion rules;
- treatment of zero and negative balances, if applicable;
- duplicate handling policy;
- patient-sensitive data handling and redaction rules;
- evidence retention policy;
- rollback and cleanup expectations for scratch/test targets.

The artefact package must not commit real patient names, DOBs, addresses, phone
numbers, email addresses, clinical details, unredacted DSNs, secrets, or full
real artefact contents.

## Approval Gates

Future work must pass these gates in order:

1. Artefact provenance approval.
2. Redaction and storage approval.
3. Manifest, checksum, and expected-total approval.
4. Scratch/test target approval.
5. Validation/no-write authorisation.
6. Validation/no-write evidence review and sign-off.
7. Guarded apply/write readiness check.
8. Separate guarded apply/write authorisation.
9. Guarded apply/write evidence review and sign-off.
10. Decision after full artefact proof: pause, revise, or plan a later migration
    rehearsal.
11. Live import remains separate and unauthorised.

No gate is satisfied by this planning document alone.

## Required Future Validation/No-Write Evidence

A future validation/no-write slice must preserve:

- manifest ID;
- manifest checksum;
- source artefact hash;
- eligible row count;
- expected total;
- target classification;
- repo SHA;
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
- expected total;
- target classification;
- repo SHA;
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
only. It must not be live/default PMS, actual PMS Postgres, production-looking,
or ambiguous.

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
- real patient names, DOBs, addresses, phone numbers, emails, clinical details,
  or full artefact contents in committed docs;
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

## Planning-Slice Stop Conditions

Stop this planning track if any future task would require:

- R4 access for the planning slice;
- real R4 artefact access for the planning slice;
- patient data for the planning slice;
- PMS DB connection or write for the planning slice;
- CLI validation or guarded apply execution in the planning slice;
- backend, frontend, Docker, compose, runtime, or ops changes;
- wording that implies live import, production readiness, or completed full
  eligible-row artefact execution.

## Linked Governance Proposal

The separate provenance and redaction proposal is recorded at
`docs/r4/R4_FINANCE_OPENING_BALANCE_FULL_ELIGIBLE_ARTEFACT_PROVENANCE_REDACTION_PROPOSAL.md`.
It is also planning-only and does not create, access, inspect, copy, hash,
store, validate, or execute a real artefact.

## Next Conservative Slice

The next safe slice is owner review of this plan and the linked provenance and
redaction proposal. Do not proceed to live import. Do not run validation/no-write
or guarded apply/write until a future task explicitly authorises that exact
gate.
