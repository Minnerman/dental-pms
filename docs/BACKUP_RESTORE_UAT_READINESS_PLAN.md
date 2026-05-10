# Backup/Restore Rehearsal And UAT Readiness Plan

Status date: 2026-05-10

Baseline:
`origin/master@22f22757befcbf5b62cab90c16596098fe2e66d7`

This is a docs-only readiness plan. It does not execute backup, restore, UAT,
smoke tests, production writes, production cutover, live/default PMS DB writes,
actual PMS Postgres writes, PMS database connections, R4 access, real artefact
access, validation/no-write, guarded apply/write, finance import, or
invoice/payment/staging import.

R4 remains the live/main PMS. Dental PMS is not live/main PMS.
`finance_import_ready=false`. Live finance import, production execution,
production cutover, live/default PMS DB writes, actual PMS Postgres writes, and
invoice/payment/staging import remain unauthorised. Production readiness is
not complete.

No secrets, exact private paths, DSNs, passwords, tokens, raw database dumps,
credentials, patient data, or patient-level contents belong in this plan or in
the later evidence records.

## Backup/Restore Rehearsal Prerequisites

The current prerequisite state is:

| Item | Current value | Status |
| --- | --- | --- |
| Backup owner | Project owner / production operator | Identified |
| Backup schedule target | Daily | Target only, pending verification |
| Backup retention target | Minimum 30 days | Target only, pending verification |
| Restore target | Non-live restore test only | Target classification identified |
| Latest safe backup timestamp | Not yet available | Required before rehearsal |
| Restore rehearsal execution | Not yet performed | Required before readiness can advance |

Backup and restore evidence must remain redacted. It must not expose backup
storage paths, credentials, DSNs, raw dumps, patient data, or private host
details.

## Later Restore Rehearsal Execution Checklist

A later explicit execution slice should complete the following before and
during any restore rehearsal:

- identify a safe non-live restore target;
- confirm the target cannot receive live/default PMS writes;
- confirm no patient data or raw dump content will be committed;
- confirm no secrets, DSNs, passwords, tokens, private URLs, or exact private
  filesystem paths will be exposed;
- confirm no production write is required;
- confirm the latest safe backup timestamp and backup source classification;
- perform restore only into the approved non-live target;
- record redacted command shapes and high-level pass/fail evidence only;
- record restore timing and operator role;
- record validation result without exposing patient-level contents;
- record rollback notes and whether the restored target was retained or
  discarded;
- stop immediately if the target is ambiguous, live-looking, or requires
  production writes.

This plan does not authorise the restore rehearsal. The rehearsal requires a
separate explicit execution slice.

## UAT/Practice Workflow Readiness Checklist

A later UAT execution slice should record owner/practice acceptance for:

- login and access check;
- user role and access review;
- patient search workflow;
- patient summary and navigation workflow;
- appointment booking, move, cancel, and day-sheet workflow;
- treatment and clinical notes workflow;
- finance/opening-balance visibility check, without live finance import;
- reporting, checkout, and cash-up workflow;
- document/template workflow if in scope;
- error, audit, and log review at a redacted high level;
- known issue list and go/no-go impact.

UAT must not commit patient data, screenshots containing patient-level
contents, secrets, credentials, or private paths.

## Production Smoke Test Readiness Checklist

A later smoke execution slice should record redacted pass/fail evidence for:

- frontend availability;
- backend static health endpoint;
- frontend health proxy or app health endpoint;
- no-auth public route check;
- not-found route behaviour where applicable;
- static asset availability if applicable;
- authenticated route checklist as a manual owner task if credentials are
  required;
- error/log review without exposing secrets or patient data.

Authenticated checks must remain manual owner/operator tasks unless a later
slice explicitly authorises a safe credential handling process. This plan does
not authorise credential use or database access.

## Stop Conditions

Stop before execution if any of the following apply:

- no safe non-live restore target is identified;
- latest safe backup timestamp is unavailable;
- backup or restore evidence would expose secrets, credentials, DSNs, private
  URLs, exact private paths, raw database dumps, or patient data;
- restore requires live/default PMS writes;
- any step requires actual PMS Postgres writes;
- UAT requires patient data to be committed;
- smoke tests require database connection outside an approved slice;
- live finance import is requested;
- production cutover or Dental PMS live/main PMS status is requested before a
  separate go/no-go approval.

## Immediate Next Execution Candidates

The next safe execution candidates are:

1. Owner/operator supplies the latest safe backup timestamp.
2. Owner/operator confirms the safe non-live restore target.
3. Separate non-live restore rehearsal execution slice.
4. Separate UAT checklist execution slice.
5. Separate read-only production smoke execution slice if the scope remains
   non-invasive and does not require database connection, secrets exposure, or
   live writes.

Until those are separately authorised and recorded, backup/restore proof,
UAT acceptance, production smoke evidence, production readiness, live finance
import, production execution, and cutover remain incomplete and unauthorised.
