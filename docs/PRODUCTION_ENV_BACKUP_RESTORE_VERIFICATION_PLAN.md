# Production Environment Backup/Restore Verification Plan

Status date: 2026-05-10

Baseline:
`origin/master@53fd57ba46ec1511ae83922ca5b28e6f89b2bf7c`

This is a docs-only planning slice for production-environment, backup, and
restore verification. It does not verify production yet, connect to production,
connect to any PMS database, access R4, access/hash/inspect real artefacts, use
patient data, run validation/no-write, run guarded apply/write, perform finance
import, perform invoice/payment/staging import, write live/default PMS data,
write actual PMS Postgres data, or perform production cutover.

R4 remains the live/main PMS. Dental PMS is not live/main PMS.
`finance_import_ready=false`. Live finance import, production execution,
production cutover, live/default PMS DB writes, actual PMS Postgres writes, and
invoice/payment/staging import remain unauthorised.

This plan defines what a later explicit execution slice should verify and what
evidence it should record. It must not expose secrets, DSNs, passwords, patient
data, exact artefact paths, or live credentials.

## Production-Environment Verification Checklist

The later execution PR should record redacted evidence for:

- environment identity: intended production environment name, owner, and
  confirmation that the target is understood before inspection;
- deployment target identity: target host/service/container identity, recorded
  without secrets or live credentials;
- app health endpoint or smoke check plan: redacted command shape, expected
  health response, and pass/fail criteria;
- frontend availability plan: URL or route class to check, expected reachable
  state, and failure criteria, without publishing credentials;
- backend availability plan: health route or service check, expected reachable
  state, and failure criteria;
- database connectivity check plan: planned connectivity verification only,
  without performing it in this slice and without exposing DSNs;
- environment variable and secrets presence check plan: presence-only checks,
  no secret values, no copied secrets, and no committed credentials;
- logging and monitoring check plan: log availability, alert destination,
  monitoring owner, and escalation path;
- user/access check plan: admin, reception, clinical, finance, and support
  access review without testing with patient data.

## Backup Readiness Checklist

The later execution PR should identify and record:

- backup owner;
- backup target;
- backup frequency;
- backup retention;
- backup integrity proof method;
- restore rehearsal requirement;
- evidence location policy, excluding secrets, patient-level contents, DSNs,
  production passwords, and live credentials.

## Restore Proof Checklist

The later restore proof must be separately approved before execution and should
record:

- restore target, which must be non-live and safe;
- restore timing and duration;
- restore validation steps;
- rollback decision point;
- data retained for diagnosis;
- operator notification path;
- explicit confirmation that no live/default PMS DB writes, actual PMS
  Postgres writes, live finance import, invoice/payment/staging import, or
  production cutover occurred unless separately authorised.

## Stop Conditions

Stop and escalate before execution if any of the following apply:

- production target is unknown or ambiguous;
- backup owner is missing;
- restore proof target is missing, live, or ambiguous;
- rollback path is unclear;
- secret exposure risk exists;
- any request would write production data;
- any request would connect to a PMS database outside the approved execution
  slice;
- any request would perform live finance import, invoice/payment/staging
  import, or production cutover.

## Expected Evidence For Later Execution PR

A later execution PR should include only safe, redacted evidence:

- timestamp;
- actor or owner;
- redacted command shapes;
- pass/fail status;
- no secrets;
- no patient data;
- no DSNs, passwords, or live credentials;
- production-environment identity and backup/restore owner confirmation;
- backup integrity result;
- restore rehearsal result if separately approved and executed;
- rollback notes and decision point;
- explicit confirmation that R4 remained live/main PMS and Dental PMS was not
  made live/main PMS.

## Boundary

Actual production-environment verification, backup proof, and restore proof
remain separate explicit execution slices. This planning record does not claim
production readiness is complete and does not authorise live/default PMS DB
writes, actual PMS Postgres writes, live finance import, invoice/payment/staging
import, production execution, or cutover.
