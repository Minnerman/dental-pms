# Opening-Balance Bounded Fixture Guarded Apply Evidence Sign-Off

Sign-off date: 2026-05-08

Package: `ob-bounded-fixture-20260507-000001`

Sign-off source: explicit owner sign-off provided in task input for this
repository continuity slice.

## Sign-Off Scope

This sign-off accepts the guarded apply/write proof evidence for the approved
bounded fixture only. The accepted evidence is recorded at:

`docs/r4/R4_FINANCE_OPENING_BALANCE_BOUNDED_FIXTURE_GUARDED_APPLY_EVIDENCE.md`

The sign-off is limited to:

- manifest ID: `ob-bounded-fixture-20260507-000001`
- fixture/source hash:
  `2afabfcb903b0f4e5a94702ae93b7752e9309e30116a4d01e1f55ec84465b53d`
- manifest checksum:
  `66cc1c7ac16a4e677dfea6994cef86a5b7c496a00fbfec10336fa7641d98bb67`
- row count: `3`
- eligible count: `3`
- expected total: `7.35`
- first apply JSON SHA256:
  `802d4ca94762e060037b97dc68bdd08ad40d17541f04493378f5a0125a567837`
- second idempotency JSON SHA256:
  `e83a3faf7a6b22045d11a98559f342618d81a192841079864d0e2688cdfa5e2b`
- local query verification JSON SHA256:
  `db8846ca82489a67a0979a5524fbb1e8f0cefe6d36db12630180e13293b762f0`

The sign-off is not transferable to other fixtures, manifests, hashes, evidence
outputs, row counts, eligible counts, expected totals, targets, or a full
eligible-row artefact execution.

## Accepted Guarded Apply Evidence

The signed-off evidence recorded:

- target classification: local isolated SQLite scratch/test only;
- first guarded apply exit: `0`;
- first guarded apply counts: `created=3`, `updated=0`, `skipped=0`, `refused=0`;
- second idempotency exit: `0`;
- second idempotency counts: `created=0`, `updated=0`, `skipped=3`, `refused=0`;
- query verification: `ledger_count=3`, total `7.35`, unique manifest references `3`;
- invoice count: `0`;
- payment count: `0`;
- `--apply` was used for the proof;
- exact `--confirm SCRATCH_OPENING_BALANCE_APPLY` was used for the proof;
- `--actor-id 990000` was used for the proof.

The evidence remains scratch/test proof evidence only. `finance_import_ready`
remains `false`.

## Explicit Non-Authorisations

This sign-off does not authorise:

- live/default PMS database writes;
- actual PMS Postgres writes;
- R4 access;
- real R4 artefact access;
- real patient data use;
- finance import;
- finance import or staging models;
- invoice, payment, or staging import;
- production execution;
- full eligible-row artefact execution.

This sign-off does not mark migration or import complete, does not imply live
finance import is authorised, and does not imply production readiness.

## Sensitive Data Boundary

No patient names, DOBs, addresses, phone numbers, emails, clinical details,
unredacted DSNs, secrets, or full real artefact contents are included in this
sign-off record.
