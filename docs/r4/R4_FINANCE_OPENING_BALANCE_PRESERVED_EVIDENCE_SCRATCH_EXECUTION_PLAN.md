# R4 Finance Opening-Balance Preserved-Evidence Scratch Execution Plan

Status date: 2026-05-07

Baseline: `origin/master@4fac5b0f818a9b672b3230d4d987ce3ce9056c9c`

Safety: this is a planning document only. It does not execute guarded scratch
apply, access R4, read a real R4 artefact, connect to a real PMS database, write
PMS Postgres rows, create finance records, authorise finance import, or
authorise live/default PMS use.

## Current State

PR #614 added the guarded scratch-only opening-balance apply CLI prototype. The
CLI defaults to validation/no-write mode, refuses non-scratch targets before
opening a session, and writes only manifest-scoped `PatientLedgerEntry`
adjustment rows when all scratch write guards are supplied.

PR #615 added a bounded synthetic scratch execution proof. That proof used only
generated non-R4 data, synthetic identifiers, and a local SQLite scratch/test
database under pytest `tmp_path`. It proved validation/no-write mode, guarded
scratch writes, and idempotency for two synthetic rows. It did not use real R4
artefacts, real patient data, a real PMS database, or actual PMS Postgres.

The synthetic proof does not prove live migration readiness, does not prove a
preserved-evidence scratch apply, and does not authorise finance import.
`finance_import_ready=false`.

The execution package decision is recorded in:

- `docs/r4/R4_FINANCE_OPENING_BALANCE_EXECUTION_PACKAGE_DECISION.md`

That decision recommends Option B, an approved bounded fixture package, for the
next explicitly authorised scratch/test-only execution proof. A complete
eligible-row artefact package remains blocked until provenance, redaction,
storage, hashes, and owner approval are established.

The current candidate bounded fixture package is recorded in:

- `docs/r4/R4_FINANCE_OPENING_BALANCE_BOUNDED_FIXTURE_PACKAGE.md`
- `docs/r4/fixtures/opening_balance_bounded_fixture/`

The candidate package is pending approval and does not authorise execution.

## Purpose

A future explicitly authorised slice may execute the guarded scratch apply CLI
against a bounded preserved-evidence artefact in an isolated scratch/test target.
That execution should prove only the opening-balance scratch write mechanics
against accepted evidence:

- artefact identity and provenance checks;
- default/live target refusal;
- validation/no-write mode;
- scratch-only apply with explicit operator intent;
- first-run created/skipped/refused counts;
- second-run idempotency counts;
- invoice and payment counts unchanged;
- preserved evidence capture without sensitive patient data in committed docs.

It remains separate from:

- the completed synthetic scratch proof;
- historical invoice import;
- normal payment import;
- full finance import;
- live/default PMS cutover.

## Required Artefact Type

The execution input must be an opening-balance dry-run report accepted by the
guarded apply CLI. The report must contain a complete eligible-row payload for
the exact bounded execution set under `samples.eligible_opening_balance`.

Two input shapes are acceptable only after explicit approval:

- full preserved-evidence shape: all `1018` eligible non-zero opening-balance
  rows are present in the accepted dry-run report;
- deliberately bounded preserved-evidence shape: a smaller eligible-row subset
  is declared in the manifest with explicit bounds, inclusion rules, exclusion
  rules, and owner approval that the subset is a proof fixture only.

The current preserved dry-run report has bounded eligible samples, not a full
eligible-row apply payload. It must not be used for scratch apply unless the
future slice first supplies an approved full eligible-row artefact or an
approved bounded fixture.

For the next execution proof, use the approved bounded fixture package defined
by the package decision. Do not proceed to a complete eligible-row package until
the Option A blockers in that decision are cleared.

## Required Provenance

The artefact package must identify:

- source process that produced the dry-run report;
- source artefact path and SHA256;
- dry-run report path and SHA256;
- mapping artefact path and SHA256, when separate;
- report generation timestamp;
- dry-run repo SHA;
- apply repo SHA;
- operator-approved bounded execution set;
- evidence directory where stdout, stderr, exit code, command summary, and JSON
  reports will be preserved.

Do not commit full artefact contents. Committed docs may reference hashes,
counts, redacted paths, and bounded summaries only.

## Required Manifest Fields

The dry-run/apply manifest must include:

- manifest ID;
- manifest checksum or report SHA256;
- source artefact hash;
- dry-run report hash;
- mapping artefact hash, if applicable;
- row count for the bounded execution set;
- eligible count;
- expected total balance for the bounded execution set;
- mapping coverage for non-zero candidates;
- unmapped non-zero candidate count;
- component-mismatch count among would-write rows;
- `dry_run=true`;
- `manifest.no_write=true` on the input report;
- `manifest.apply_mode=false` on the input report;
- `import_ready=false`;
- `finance_import_ready=false`;
- dry-run repo SHA;
- apply repo SHA;
- source drift acknowledgement when the report records drift;
- scratch/test target classification;
- operator/actor ID if safe and non-sensitive.

## Required Guards

The future execution must use validation/no-write mode first. Scratch apply may
start only after the validation output is reviewed and all guards pass.

Identity guards:

- `--expected-report-sha256 <sha256>`;
- `--expected-total-balance <decimal>`;
- `--expected-eligible-count <count>`;
- `--expected-repo-sha <dry-run-repo-sha>`;
- `--acknowledge-source-drift` when the accepted report records drift.

Target guards:

- target must be isolated scratch/test data only;
- target database name must clearly contain `scratch` or `test`;
- target must not be `dental_pms`;
- target DSN, host, database name, tenant, and environment label must not look
  like production, prod, live, default, or operational PMS data;
- target must have recorded before-counts for `patient_ledger_entries`,
  `invoices`, and `payments`;
- target must have no existing opening-balance markers except exact idempotency
  rerun markers for the same manifest.

Write guards:

- `--apply`;
- `--confirm SCRATCH_OPENING_BALANCE_APPLY`;
- `--actor-id <scratch-operator-user-id>`;
- manifest ID;
- output JSON path under the evidence directory.

The command must fail closed before session creation for default/live-looking or
ambiguous targets.

## Command Shape

Validation/no-write command shape:

```bash
python -m app.scripts.r4_opening_balance_guarded_scratch_apply \
  --dry-run-report-json /redacted/evidence/opening_balance_snapshot_dryrun_report.json \
  --database-url 'postgresql+psycopg://<user>:<redacted>@<host>:<port>/<scratch_db>' \
  --manifest-id <manifest_id> \
  --output-json /redacted/evidence/opening_balance_guarded_apply_validate.json \
  --expected-report-sha256 <dry_run_report_sha256> \
  --expected-total-balance <expected_total> \
  --expected-eligible-count <eligible_count> \
  --expected-repo-sha <dry_run_repo_sha> \
  --acknowledge-source-drift
```

Scratch apply command shape, only after validation is accepted:

```bash
python -m app.scripts.r4_opening_balance_guarded_scratch_apply \
  --dry-run-report-json /redacted/evidence/opening_balance_snapshot_dryrun_report.json \
  --database-url 'postgresql+psycopg://<user>:<redacted>@<host>:<port>/<scratch_db>' \
  --manifest-id <manifest_id> \
  --output-json /redacted/evidence/opening_balance_guarded_apply_report.json \
  --expected-report-sha256 <dry_run_report_sha256> \
  --expected-total-balance <expected_total> \
  --expected-eligible-count <eligible_count> \
  --expected-repo-sha <dry_run_repo_sha> \
  --acknowledge-source-drift \
  --apply \
  --confirm SCRATCH_OPENING_BALANCE_APPLY \
  --actor-id <scratch-operator-user-id>
```

Secrets, unredacted DSNs, and full artefact contents must not be committed.

## Evidence Capture

The future execution must preserve:

- validation report JSON;
- apply report JSON, if apply is authorised;
- idempotency rerun report JSON;
- rollback report JSON, if rollback is included;
- stdout, stderr, and exit code for every command;
- redacted command shape;
- manifest ID;
- manifest/report checksum;
- source artefact hash;
- dry-run report hash;
- mapping artefact hash, if applicable;
- row count and eligible count;
- expected total;
- created, updated, skipped, and refused counts;
- before and after counts for `patient_ledger_entries`, `invoices`, and
  `payments`;
- target classification and scratch DB name, without secrets;
- dry-run repo SHA and apply repo SHA;
- timestamp;
- operator/actor ID when safe and non-sensitive;
- final cleanup or retained-scratch-target decision.

Committed docs may summarize these values but must not include full patient-row
payloads.

## Sensitive Data Rules

Do not include the following in logs intended for committed docs, PR summaries,
or status documents:

- real patient names;
- dates of birth;
- addresses;
- phone numbers;
- email addresses;
- clinical details;
- full ledger-row note payloads if they contain sensitive source data;
- unredacted DSNs;
- secrets;
- full dry-run report contents;
- full mapping artefact contents;
- broad row dumps.

Allowed committed evidence is limited to counts, hashes, redacted command
shapes, manifest IDs, repo SHAs, timestamps, target classification, and bounded
non-sensitive summaries.

## Stop Conditions

Stop before apply and report if any of these occur:

- origin/master or expected repo SHA differs unexpectedly;
- the preserved operational diff is not intact;
- R4 access appears necessary;
- a real R4 export must be opened or regenerated without explicit
  authorisation;
- a real PMS database connection appears necessary;
- the target is default/live/production-looking or ambiguous;
- the target name does not clearly contain `scratch` or `test`;
- the target is `dental_pms`;
- the artefact lacks every eligible row for the selected bounded execution set;
- report SHA256, expected total, eligible count, or repo SHA mismatch;
- mapping coverage is incomplete for non-zero candidates;
- unmapped non-zero candidates are present;
- component mismatches are present among would-write rows;
- source drift is present and not explicitly acknowledged;
- before-counts are missing or unexpected;
- invoices or payments would be created or changed;
- a finance staging model or finance import path appears;
- existing opening-balance markers are partial, mismatched, or from a different
  manifest;
- rollback or cleanup cannot be scoped to the manifest/scratch target;
- command output would expose secrets or patient-sensitive data.

## Idempotency Expectations

The second run against the same scratch target and manifest must not duplicate
ledger rows.

Expected second-run result:

- `created=0`;
- `updated=0`;
- `skipped=<eligible_count>`;
- `refused=0`, unless the first run left a deliberately refused bounded row set;
- invoice count unchanged;
- payment count unchanged;
- ledger row count unchanged from the first apply.

Any existing row with the same manifest but a mismatched patient, amount,
reference, or representation must fail closed as manifest corruption.

## Rollback And Cleanup Expectations

Rollback, if included in the execution slice, must be manifest-scoped and
scratch-only. It may delete exact scratch ledger rows created by the apply
manifest, but it must not broadly delete patient ledger rows, invoices, payments,
or records from any other manifest.

Rollback evidence should capture:

- apply report path and hash;
- before rollback counts;
- exact manifest row count;
- deleted or reversed row count;
- after rollback counts;
- remaining manifest rows, expected `0` for delete rollback;
- invoices and payments unchanged.

Scratch cleanup must remove or retain only the explicitly named scratch target
according to the future slice instruction. It must not touch default/live PMS
containers, volumes, or databases.

## Required Report After Execution

The future execution report should state:

- manifest ID;
- source artefact hash;
- dry-run report hash;
- mapping artefact hash, if applicable;
- row count;
- eligible count;
- expected total;
- target classification;
- scratch DB name with secrets redacted;
- dry-run repo SHA;
- apply repo SHA;
- validation result;
- first-run created, updated, skipped, and refused counts;
- second-run idempotency counts;
- invoice and payment before/after counts;
- rollback result, if included;
- cleanup result;
- whether R4 was accessed;
- whether any real PMS DB was accessed;
- whether any live/default PMS DB write occurred;
- whether any actual PMS Postgres write occurred;
- whether any live finance record was created or changed;
- whether finance import remains out of scope.

## Out Of Scope

This plan does not authorise:

- R4 writes;
- R4 access in this planning slice;
- real R4 artefact execution in this planning slice;
- real patient data in committed docs;
- live/default PMS writes;
- actual PMS Postgres writes in this planning slice;
- invoices;
- payments;
- finance staging models;
- historical invoice import;
- payment import;
- full finance import;
- production readiness;
- live cutover.

`finance_import_ready=false` remains the required state.
