# Opening-Balance Bounded Fixture Validation/No-Write Sign-Off

Sign-off date: 2026-05-08

Package: `ob-bounded-fixture-20260507-000001`

Sign-off source: explicit owner sign-off provided in task input for this
repository continuity slice.

## Sign-Off Scope

This sign-off accepts the validation/no-write evidence for consideration of a
later separately authorised scratch/test-only guarded apply/write slice.

The sign-off is limited to:

- manifest ID: `ob-bounded-fixture-20260507-000001`
- fixture/source hash:
  `2afabfcb903b0f4e5a94702ae93b7752e9309e30116a4d01e1f55ec84465b53d`
- manifest checksum:
  `66cc1c7ac16a4e677dfea6994cef86a5b7c496a00fbfec10336fa7641d98bb67`
- evidence document:
  `docs/r4/R4_FINANCE_OPENING_BALANCE_BOUNDED_FIXTURE_VALIDATION_NOWRITE_EVIDENCE.md`
- evidence output path:
  `.run/opening_balance_bounded_fixture_validation_nowrite_20260508_015124/opening_balance_guarded_apply_validate.json`
- evidence SHA256:
  `c053f6514b6a9109c60561be5ae7485d81399d43cfc58bcbe58f915b5c880840`
- row count: `3`
- eligible count: `3`
- expected total: `7.35`

The sign-off is not transferable to other fixtures, manifests, hashes, evidence
outputs, row counts, eligible counts, expected totals, or targets.

## Accepted Validation/No-Write Evidence

The signed-off evidence recorded:

- `--apply` was not used;
- `--confirm` was not used;
- `--actor-id` was not used;
- PMS DB connection: no;
- SQLite scratch/test DB file created: no;
- CLI exit: `0`;
- `apply_requested=false`;
- result counts: `created=0`, `updated=0`, `skipped=0`, `refused=0`;
- finance counts: `before=null`, `after=null`.

## Explicit Non-Authorisations

This sign-off does not authorise:

- guarded apply/write execution now;
- live/default PMS database writes;
- actual PMS Postgres writes;
- R4 access;
- real R4 artefact access;
- real patient data use;
- finance import;
- finance import or staging models;
- invoice, payment, or staging import;
- production execution.

Guarded apply/write remains a later separately authorised slice. That future
slice must re-check the fixture hash, manifest checksum, evidence SHA256,
expected total, eligible count, repo SHA, scratch/test target classification,
rollback/cleanup plan, and redaction controls before any guarded apply/write is
attempted.

`finance_import_ready=false`. Finance import remains out of scope. This record
does not mark migration or import complete, does not imply live finance import
is authorised, and does not imply production readiness.

## Sensitive Data Boundary

No patient names, DOBs, addresses, phone numbers, emails, clinical details,
unredacted DSNs, secrets, or full real artefact contents are included in this
sign-off record.
