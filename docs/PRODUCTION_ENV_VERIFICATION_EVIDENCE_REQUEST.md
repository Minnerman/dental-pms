# Production Environment Verification Evidence Request

Status date: 2026-05-10

Baseline:
`origin/master@7f027fa26cba14cc21822e8e92506f47b16c862e`

This is a docs-only evidence request and execution checklist for production
environment, backup, and restore readiness. It does not run verification,
connect to production, expose secrets, connect to any PMS database, access R4,
access/hash/inspect real artefacts, use patient data, run validation/no-write,
run guarded apply/write, perform finance import, perform invoice/payment/staging
import, write live/default PMS data, write actual PMS Postgres data, or perform
production cutover.

R4 remains the live/main PMS. Dental PMS is not live/main PMS.
`finance_import_ready=false`. Live finance import, production execution,
production cutover, live/default PMS DB writes, actual PMS Postgres writes, and
invoice/payment/staging import remain unauthorised.

Actual verification execution remains a later separate slice with explicit
scope and approval. This request defines the non-sensitive evidence the
production operator/admin should provide for review.

## Requested Non-Sensitive Evidence

The production operator/admin should provide only redacted, non-sensitive
evidence for:

- production environment name or label, non-secret;
- deployment target identity, non-secret;
- application health check result, redacted;
- frontend availability result, redacted;
- backend availability result, redacted;
- backup owner or owner role;
- backup schedule/frequency;
- backup retention policy;
- latest backup timestamp, if safe to disclose;
- restore rehearsal target classification;
- restore rehearsal status;
- monitoring/logging owner;
- support contact role, non-personal if preferred.

## Forbidden Outputs

Do not provide or commit:

- passwords;
- tokens;
- DSNs;
- patient data;
- secret URLs;
- raw database dumps;
- exact private filesystem paths unless explicitly approved;
- production passwords or live credentials;
- screenshots or logs containing secrets or patient-level data.

## Pass/Fail Criteria For Later Evidence

Later evidence can pass only if:

- production target is identified;
- application health check passes;
- frontend availability check passes;
- backend availability check passes;
- backup owner and schedule are known;
- restore proof plan or restore evidence is present;
- no secrets are exposed;
- no patient data is exposed;
- no live/default PMS DB writes, actual PMS Postgres writes, live finance
  import, invoice/payment/staging import, or production cutover occur unless
  separately authorised.

Later evidence fails or remains blocked if any pass condition is missing.

## Stop Conditions

Stop before evidence collection or review if:

- production identity is unclear;
- no backup owner is identified;
- no restore path exists;
- secrets would be exposed;
- live writes are requested;
- patient data is required;
- a PMS database connection is required outside a separately approved execution
  slice;
- live finance import, invoice/payment/staging import, or production cutover is
  requested.

## Boundary

This evidence request does not authorise production verification execution,
live/default PMS DB writes, actual PMS Postgres writes, production execution,
live finance import, invoice/payment/staging import, or cutover. It also does
not claim production readiness is complete.
