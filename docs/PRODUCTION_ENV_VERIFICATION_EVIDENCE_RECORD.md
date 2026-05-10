# Production Environment Verification Evidence Record

Status date: 2026-05-10

Baseline:
`origin/master@6d20b6d06acbb52b240e609efecf18eac054bffe`

This is a docs-only production environment evidence record. It does not perform
verification itself, connect to production, connect to any PMS database, access
R4, access/hash/inspect real artefacts, use patient data, run
validation/no-write, run guarded apply/write, perform finance import, perform
invoice/payment/staging import, write live/default PMS data, write actual PMS
Postgres data, or perform production cutover.

## Evidence Status

At the time this record was created, non-sensitive production environment
evidence was not yet available in committed docs or in the task input. No
production values were inferred or invented.

This record is therefore a blocked/gap evidence record.

Follow-up non-invasive collection is recorded in
`docs/PRODUCTION_ENV_VERIFICATION_EVIDENCE_COLLECTION.md`. That follow-up
records owner/operator-supplied production labels, roles, backup targets, and
restore target classification; verifies unauthenticated read-only
frontend/backend/app health availability; and leaves deployment target
verification, latest safe backup timestamp, and restore rehearsal execution
blocked.

## Original Missing Evidence

This blocked record originally listed the following missing non-sensitive
evidence before the follow-up collection record:

- production environment label;
- deployment target label;
- frontend availability result;
- backend availability result;
- app health check result;
- backup owner/role;
- backup schedule/frequency;
- backup retention policy;
- latest safe backup timestamp;
- restore rehearsal target classification;
- restore rehearsal status;
- monitoring/logging owner role;
- support contact role.

## Boundary

This record contains no secrets, DSNs, tokens, passwords, patient data, raw
database dumps, exact private filesystem paths, live credentials, or production
operator personal details.

R4 remains the live/main PMS. Dental PMS is not live/main PMS.
`finance_import_ready=false`. Live/default PMS DB writes, actual PMS Postgres
writes, production execution, live finance import, invoice/payment/staging
import, and production cutover remain unauthorised.

## Next Action

The next action is for the owner/operator to supply the requested
non-sensitive production evidence, or to authorise a separate non-invasive
verification execution slice with explicit scope, redaction rules, and stop
conditions.

After the follow-up collection record, the remaining blocked evidence is the
deployment target verification, actual backup schedule/retention verification,
latest safe backup timestamp, and restore rehearsal execution/status.

This record does not authorise production writes, live finance import,
invoice/payment/staging import, production execution, or cutover.
