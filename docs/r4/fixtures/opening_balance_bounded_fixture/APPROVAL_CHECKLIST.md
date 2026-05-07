# Opening-Balance Bounded Fixture Approval Checklist

Status date: 2026-05-07

Package status: candidate bounded fixture package pending approval.

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
- Approval status: not approved

## Required Approval Checks

- [ ] Owner approval explicitly records this as an approved bounded fixture for
      scratch/test-only proof.
- [ ] Reviewer confirms the fixture data is synthetic or otherwise
      non-sensitive.
- [ ] Reviewer confirms no real R4 patient codes, patient names, DOBs,
      addresses, phone numbers, emails, clinical details, real account numbers,
      unredacted DSNs, secrets, or real R4 artefact contents are present.
- [ ] Reviewer confirms future execution remains scratch/test-only.
- [ ] Reviewer confirms no live/default/production PMS target is authorised.
- [ ] Reviewer confirms no finance import is authorised.
- [ ] Reviewer confirms no finance import/staging models are authorised.
- [ ] Reviewer confirms no invoices or payments may be created.
- [ ] Reviewer confirms validation/no-write must run before any apply command.
- [ ] Reviewer confirms future apply requires `--apply`,
      `--confirm SCRATCH_OPENING_BALANCE_APPLY`, and `--actor-id`.
- [ ] Reviewer confirms fixture SHA256, manifest SHA256, expected total,
      eligible count, and repo SHA must match before execution.
- [ ] Reviewer confirms rollback/cleanup expectations are understood before
      execution.
- [ ] Reviewer confirms no patient-sensitive values will be committed in future
      execution evidence.
- [ ] Reviewer confirms future evidence will include validation, first apply,
      and second-run idempotency summaries.
- [ ] Reviewer confirms `finance_import_ready=false` remains unchanged.

## Explicit Non-Approval

Until every checkbox above is completed and an owner approval record is added,
this package remains:

- candidate only;
- pending approval;
- not executable;
- not evidence of live migration readiness;
- not authorisation for finance import.

## Approval Record

Approval owner:

Approval timestamp:

Approval note:

Approved for future scratch/test-only execution: no
