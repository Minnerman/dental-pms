# R4 Finance Opening-Balance Execution Package Decision

Status date: 2026-05-07

Baseline: `origin/master@c813bbdbc7e3f15674860a70f450ead601fbfa1b`

Safety: this is a decision and planning document only. It does not execute
guarded scratch apply, access R4, open a real R4 export, open a real R4
artefact, use real patient data, connect to a PMS database, write PMS Postgres
rows, create finance records, authorise finance import, or authorise
live/default PMS use.

`finance_import_ready=false`. Finance import remains out of scope.

## Decision Summary

Recommended next execution package: **Option B, approved bounded fixture**.

Reason: there is no explicitly approved complete eligible-row artefact package
yet. The current preserved dry-run report has bounded eligible samples, and the
guarded apply CLI requires every eligible row for the selected execution set.
An approved bounded fixture is the smallest safe next package after PR #615's
synthetic scratch proof because it can prove the preserved-evidence execution
workflow, evidence capture, target refusal, guarded apply, and idempotency while
reducing evidence-handling risk.

Option A, a complete eligible-row artefact package, remains the stronger later
scratch rehearsal package. It should follow only after artefact provenance,
redaction controls, storage rules, and explicit owner approval are established.

This decision does not authorise either package to run. Any execution remains a
future explicitly authorised scratch/test-only slice.

## Current State

Completed:

- PR #614: guarded scratch-only opening-balance apply CLI prototype.
- PR #615: bounded synthetic scratch execution proof using generated non-R4 data
  and local SQLite scratch/test under pytest `tmp_path`.
- PR #616: preserved-evidence scratch execution plan.
- PR #617: execution package decision selecting Option B next.

Candidate package prepared after this decision:

- `docs/r4/R4_FINANCE_OPENING_BALANCE_BOUNDED_FIXTURE_PACKAGE.md`
- `docs/r4/fixtures/opening_balance_bounded_fixture/`

That package is candidate/pending approval only. It does not authorise
execution.

Not completed:

- no preserved-evidence scratch apply execution;
- no complete `1018`-row apply artefact approval;
- no owner approval for the candidate bounded fixture package;
- no live/default PMS write approval;
- no finance import.

## Option A: Complete Eligible-Row Artefact Package

Description: a full preserved-evidence package containing every eligible row for
the current opening-balance scratch apply candidate set.

Required package elements:

- full eligible-row manifest for all selected rows;
- source artefact hash;
- dry-run report hash;
- mapping artefact hash, when separate;
- manifest checksum;
- expected total;
- eligible row count;
- dry-run repo SHA;
- apply repo SHA;
- provenance and creation timestamp;
- source drift acknowledgement, if applicable;
- redacted validation and apply command shapes;
- scratch/test target classification;
- evidence capture directory;
- owner approval that the full eligible-row artefact is allowed for scratch/test
  execution.

Pros:

- closest to a realistic scratch rehearsal;
- strongest reconciliation signal;
- exercises full eligible-row count and aggregate total;
- makes first-run and idempotency counts meaningful for the current `1018`
  candidate evidence;
- better at surfacing edge cases across the complete candidate population.

Cons:

- higher evidence-handling risk;
- requires stronger provenance and redaction controls;
- requires explicit artefact approval before use;
- requires careful storage rules for non-committed row-level evidence;
- increases review burden before execution;
- may be blocked until a full eligible-row dry-run artefact is generated or
  approved.

Decision for Option A: not the next package. It remains blocked until the full
eligible-row artefact has approved provenance, approved redaction rules,
approved storage location, manifest checksum, source/report/mapping hashes, and
owner approval.

## Option B: Approved Bounded Fixture Package

Description: a deliberately bounded package for the next scratch/test-only
execution proof. The fixture may be synthetic or an explicitly bounded
preserved-evidence subset, but it must be approved before execution and must not
commit real patient-level artefact contents.

Required package elements:

- deliberately bounded row set;
- manifest ID;
- manifest checksum;
- fixture hash or source artefact hash, depending on fixture type;
- dry-run report hash, when a dry-run report is the fixture carrier;
- expected total;
- eligible row count;
- dry-run repo SHA;
- apply repo SHA;
- fixture approval record;
- inclusion and exclusion rules;
- redacted validation and apply command shapes;
- scratch/test target classification;
- evidence capture directory.

Pros:

- lower risk;
- easier to inspect;
- easier to redact and approve;
- better next step after the synthetic proof;
- limits blast radius while proving the preserved-evidence execution workflow;
- can exercise validation, guarded apply, idempotency, and report capture
  without requiring a full `1018`-row package.

Cons:

- weaker coverage than a complete eligible-row artefact;
- may not exercise all edge cases;
- aggregate totals are proof-scope totals, not full population totals;
- still requires explicit owner approval and strict evidence controls;
- cannot be used to infer full-population readiness.

Decision for Option B: use this for the next explicitly authorised
scratch/test-only execution proof.

## Option B Acceptance Criteria

The bounded fixture package is acceptable only if all criteria pass:

- explicit approval records the package as a bounded scratch/test proof fixture;
- manifest ID is stable and unique;
- manifest checksum is present;
- fixture hash or source artefact hash is present;
- dry-run report hash is present when applicable;
- expected total is present and matches the fixture;
- eligible row count is present and matches the fixture;
- dry-run repo SHA is present;
- apply repo SHA is present before execution;
- row set is deliberately bounded with written inclusion/exclusion rules;
- fixture has complete eligible rows for its selected bounded set;
- fixture has no component mismatches among would-write rows;
- fixture has no unmapped non-zero rows;
- source drift is either absent or explicitly acknowledged;
- validation/no-write mode is planned before apply;
- scratch/test target classification is present;
- redacted command shape is present;
- explicit guarded write flags are included only for the apply step:
  `--apply`, `--confirm SCRATCH_OPENING_BALANCE_APPLY`, and `--actor-id`;
- before-counts for `patient_ledger_entries`, `invoices`, and `payments` are
  required in the future execution evidence;
- no patient-sensitive details or full artefact contents are committed.

Passing Option B proves only the bounded fixture workflow. It does not prove the
full `1018`-row preserved evidence population and does not make finance import
ready.

## Option A Acceptance Criteria Before Later Use

A later complete eligible-row artefact package is acceptable only if all
criteria pass:

- full eligible-row manifest is present for the selected source snapshot;
- selected source snapshot and cutover timestamp are approved;
- source artefact hash is present;
- dry-run report hash is present;
- mapping artefact hash is present when separate;
- manifest checksum is present;
- expected full total is present;
- eligible row count is present and expected to be `1018` unless a newer
  approved dry-run records explained drift;
- dry-run repo SHA is present;
- apply repo SHA is present before execution;
- provenance and creation timestamp are recorded;
- redaction controls are approved;
- storage location for non-committed artefacts is approved;
- explicit artefact approval is recorded;
- validation/no-write command is planned before apply;
- scratch/test target classification is present;
- no patient-sensitive details or full artefact contents are committed.

## Rejection Criteria

Reject either package before execution if any of these are true:

- missing manifest checksum;
- missing expected total;
- missing eligible count;
- missing repo SHA;
- missing fixture approval for Option B;
- missing full eligible-row approval for Option A;
- unredacted DSN;
- secret in command, logs, manifest, report, or committed docs;
- patient names in committed docs;
- DOBs or dates of birth in committed docs;
- addresses in committed docs;
- phone numbers in committed docs;
- emails in committed docs;
- clinical details in committed docs;
- full artefact contents in committed docs;
- non-scratch target;
- target resembles default, live, production, or operational PMS;
- target is `dental_pms`;
- invoice intent;
- payment intent;
- finance staging intent;
- balance mutation outside the selected ledger adjustment representation;
- ambiguous rollback;
- ambiguous cleanup;
- any request to execute finance import;
- any request to use live/default PMS data.

## Required Future Execution Evidence

The future execution proof must preserve:

- manifest ID;
- manifest checksum;
- source artefact hash or fixture hash;
- dry-run report hash, when applicable;
- mapping artefact hash, when applicable;
- row count;
- eligible row count;
- expected total;
- validation/no-write result;
- first guarded apply result;
- second-run idempotency result;
- created, updated, skipped, and refused counts;
- invoice and payment before/after counts;
- target classification;
- scratch DB name with secrets redacted;
- dry-run repo SHA;
- apply repo SHA;
- command shape with secrets redacted;
- timestamp;
- safe non-sensitive actor/operator ID where applicable;
- rollback result, if rollback is included;
- cleanup or retained-target decision.

The committed summary after execution may include counts, hashes, redacted paths,
redacted command shapes, timestamps, repo SHAs, and target classification. It
must not include full row-level artefacts.

## Must Not Be Committed

Do not commit:

- full artefact contents;
- real patient names;
- DOBs or dates of birth;
- addresses;
- phone numbers;
- emails;
- clinical details;
- unredacted DSNs;
- secrets;
- broad row dumps;
- full mapping payloads;
- full dry-run report payloads when they contain patient-level rows.

## Future Execution Stop Conditions

The future scratch/test-only execution slice must stop if any of these occur:

- target is not clearly scratch/test;
- target resembles live, default, production, or operational PMS;
- target is `dental_pms`;
- manifest checksum mismatch;
- source or fixture hash mismatch;
- expected-total mismatch;
- eligible-count mismatch;
- repo-SHA mismatch;
- missing explicit confirmation token;
- missing `--actor-id` for apply;
- validation/no-write step fails;
- unexpected write path appears;
- sensitive output would be logged or committed;
- first apply creates invoices or payments;
- first apply creates finance staging rows;
- first apply mutates balances outside the selected ledger adjustment
  representation;
- idempotency rerun creates duplicate rows;
- idempotency rerun updates rows;
- rollback or cleanup cannot be scoped to the manifest and scratch target;
- any finance import request appears;
- any live/default PMS write request appears;
- R4 access or real R4 artefact access becomes necessary without separate
  explicit authorisation.

## Separation Of States

Completed synthetic scratch proof:

- PR #615 proved the guarded CLI write path and idempotency with generated
  non-R4 rows and local SQLite scratch/test data only.

This package decision:

- selects Option B as the next package;
- records acceptance criteria, rejection criteria, evidence requirements, and
  stop conditions;
- does not execute anything.

Future preserved-evidence scratch execution:

- remains a separate explicitly authorised slice;
- must be scratch/test-only;
- must use the accepted package and the PR #616 execution plan;
- must preserve redacted evidence and prove idempotency.

Live finance import:

- remains unauthorised;
- remains out of scope;
- remains blocked by accounting sign acceptance, cutover timestamp policy,
  owner approval, double-counting controls, and full scratch rehearsal.

## Recommended Next Slice

Next slice after this decision, only after explicit instruction:

- review and approve or revise the candidate Option B bounded fixture package
  for scratch/test-only execution, without running guarded scratch apply until
  package approval is recorded and a separate execution slice is explicitly
  authorised.

Expected scope for that next slice:

- docs/evidence package manifest, or a tiny fixture-generation/proof support
  change only if explicitly authorised;
- no R4 access unless separately authorised;
- no real patient data in committed docs;
- no live/default PMS writes;
- no finance import.
