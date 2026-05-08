# R4 Finance Opening Balance Bounded Fixture Completion Summary

Status date: 2026-05-08

This summary records the current final status of the approved opening-balance
bounded fixture pathway after PR #625.

## Status

The bounded-fixture scratch/test pathway is complete through signed-off guarded
apply/write proof evidence for the approved bounded fixture only.

Completed pathway records:

- bounded fixture package:
  `docs/r4/R4_FINANCE_OPENING_BALANCE_BOUNDED_FIXTURE_PACKAGE.md`
- fixture approval record:
  `docs/r4/fixtures/opening_balance_bounded_fixture/APPROVAL_RECORD_20260507.md`
- execution-readiness verification:
  `docs/r4/R4_FINANCE_OPENING_BALANCE_BOUNDED_FIXTURE_EXECUTION_READINESS.md`
- validation/no-write evidence:
  `docs/r4/R4_FINANCE_OPENING_BALANCE_BOUNDED_FIXTURE_VALIDATION_NOWRITE_EVIDENCE.md`
- validation/no-write sign-off:
  `docs/r4/fixtures/opening_balance_bounded_fixture/VALIDATION_NOWRITE_SIGNOFF_20260508.md`
- guarded apply/write readiness check:
  `docs/r4/R4_FINANCE_OPENING_BALANCE_BOUNDED_FIXTURE_GUARDED_APPLY_READINESS.md`
- guarded apply/write proof evidence:
  `docs/r4/R4_FINANCE_OPENING_BALANCE_BOUNDED_FIXTURE_GUARDED_APPLY_EVIDENCE.md`
- guarded apply/write proof evidence sign-off:
  `docs/r4/fixtures/opening_balance_bounded_fixture/GUARDED_APPLY_EVIDENCE_SIGNOFF_20260508.md`

## Bounds

This completion status is bounded to:

- manifest ID: `ob-bounded-fixture-20260507-000001`
- row count: `3`
- eligible count: `3`
- expected total: `7.35`
- fixture/source SHA256:
  `2afabfcb903b0f4e5a94702ae93b7752e9309e30116a4d01e1f55ec84465b53d`
- manifest SHA256:
  `66cc1c7ac16a4e677dfea6994cef86a5b7c496a00fbfec10336fa7641d98bb67`
- first apply JSON SHA256:
  `802d4ca94762e060037b97dc68bdd08ad40d17541f04493378f5a0125a567837`
- second idempotency JSON SHA256:
  `e83a3faf7a6b22045d11a98559f342618d81a192841079864d0e2688cdfa5e2b`
- local query verification JSON SHA256:
  `db8846ca82489a67a0979a5524fbb1e8f0cefe6d36db12630180e13293b762f0`
- local isolated scratch/test proof scope only.

## Non-Authorisations

`finance_import_ready=false`.

This completion status does not authorise:

- live/default PMS database writes;
- actual PMS Postgres writes;
- R4 access;
- real R4 artefact access;
- real patient data use;
- finance import;
- invoice, payment, or staging import;
- full eligible-row artefact execution;
- production execution.

It does not mark migration or import complete, does not imply live finance import
is authorised, and does not establish production migration readiness.

## Conservative Next Options

Recommended next options are:

- pause after bounded-fixture pathway completion;
- perform a final owner review/status sign-off if desired;
- plan a separate full eligible-row artefact track with provenance, redaction,
  storage, hashes, and owner approval;
- do not proceed to live import from this bounded-fixture pathway.
