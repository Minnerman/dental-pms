# Opening-Balance Bounded Fixture Approval Record

Approval date: 2026-05-07

Package: `ob-bounded-fixture-20260507-000001`

Approval source: explicit owner approval provided in task input for this
repository continuity slice.

## Approved Package

This approval is limited to the committed bounded fixture package with:

- fixture/source hash:
  `2afabfcb903b0f4e5a94702ae93b7752e9309e30116a4d01e1f55ec84465b53d`
- manifest checksum:
  `66cc1c7ac16a4e677dfea6994cef86a5b7c496a00fbfec10336fa7641d98bb67`
- expected row count: `3`
- eligible count: `3`
- expected total: `7.35`
- target classification: scratch/test only
- required first step for any later execution: validation/no-write

The approved synthetic fixture identifiers are:

- `TEST-R4OB-BF-001`
- `TEST-R4OB-BF-002`
- `TEST-R4OB-BF-003`

## Approval Scope

The package is approved for a future scratch/test-only preserved-evidence
execution slice. This record does not execute the guarded apply CLI and does
not authorise execution by itself.

Any future guarded apply must be separately authorised and must use the existing
guards:

- `--apply`
- `--confirm SCRATCH_OPENING_BALANCE_APPLY`
- `--actor-id`

Validation/no-write must run first, and the future execution slice must confirm
the fixture hash, manifest checksum, row count, eligible count, expected total,
repo SHA, scratch/test target classification, and redacted evidence location
before any guarded scratch apply is attempted.

## Explicit Non-Authorisations

This approval does not authorise:

- live/default PMS database writes;
- actual PMS Postgres writes;
- R4 access;
- real R4 artefact access;
- real patient data use;
- finance import;
- finance import or staging models;
- invoice, payment, or staging import;
- production execution.

`finance_import_ready=false`. Finance import remains out of scope.

## Hash Preservation

`fixture.json` and `manifest.json` are intentionally not modified by this
approval record. The approval is tied to their existing committed byte content
and hashes. Any future change to either file invalidates this approval and
requires a new approval record.
