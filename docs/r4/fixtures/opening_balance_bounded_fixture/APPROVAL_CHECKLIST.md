# Opening-Balance Bounded Fixture Approval Checklist

Status date: 2026-05-07

Package status: owner-approved bounded fixture package for future
scratch/test-only preserved-evidence execution.

This checklist must be completed before any future guarded scratch apply
execution uses this package. This checklist does not authorise execution by
itself.

## Package Identity

- Manifest ID: `ob-bounded-fixture-20260507-000001`
- Fixture SHA256:
  `2afabfcb903b0f4e5a94702ae93b7752e9309e30116a4d01e1f55ec84465b53d`
- Manifest SHA256:
  `66cc1c7ac16a4e677dfea6994cef86a5b7c496a00fbfec10336fa7641d98bb67`
- Expected total: `7.35`
- Eligible count: `3`
- Target classification: scratch/test only
- Approval status: approved for future scratch/test-only package use; execution
  still requires a separate explicitly authorised execution slice
- Approval record: `APPROVAL_RECORD_20260507.md`

`fixture.json` and `manifest.json` are intentionally unchanged by the approval
record so the approved fixture hash and manifest checksum remain valid.

## Completed Package Approval Checks

- [x] Owner approval explicitly records this as an approved bounded fixture for
      scratch/test-only proof.
- [x] Reviewer confirms the fixture data is synthetic or otherwise
      non-sensitive.
- [x] Reviewer confirms no real R4 patient codes, patient names, DOBs,
      addresses, phone numbers, emails, clinical details, real account numbers,
      unredacted DSNs, secrets, or real R4 artefact contents are present.
- [x] Reviewer confirms future execution remains scratch/test-only.
- [x] Reviewer confirms no live/default/production PMS target is authorised.
- [x] Reviewer confirms no finance import is authorised.
- [x] Reviewer confirms no finance import/staging models are authorised.
- [x] Reviewer confirms no invoices or payments may be created.
- [x] Reviewer confirms validation/no-write must run before any apply command.
- [x] Reviewer confirms future apply requires `--apply`,
      `--confirm SCRATCH_OPENING_BALANCE_APPLY`, and `--actor-id`.
- [x] Reviewer confirms fixture SHA256, manifest SHA256, expected total,
      eligible count, and repo SHA must match before execution.
- [x] Reviewer confirms no patient-sensitive values will be committed in future
      execution evidence.
- [x] Reviewer confirms future evidence will include validation, first apply,
      and second-run idempotency summaries.
- [x] Reviewer confirms `finance_import_ready=false` remains unchanged.

## Required Future Execution Checks

- [ ] Future execution slice is explicitly authorised.
- [ ] Future execution target is confirmed scratch/test only.
- [ ] Future validation/no-write result is captured and reviewed before apply.
- [ ] Future fixture SHA256, manifest SHA256, expected total, eligible count,
      and repo SHA are revalidated.
- [ ] Future rollback/cleanup expectations are recorded for the exact target.
- [ ] Future evidence path and redaction rules are confirmed before execution.

Until every future execution check above is satisfied inside a separately
authorised slice, this package remains:

- approved package evidence only;
- not executable by this checklist alone;
- not evidence of live migration readiness;
- not authorisation for finance import.

## Approval Record

Approval owner: explicit owner approval in task input

Approval timestamp: 2026-05-07

Approval note: `APPROVAL_RECORD_20260507.md`

Approved for future scratch/test-only execution package use: yes

Execution authorised by this checklist: no
