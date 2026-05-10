# Dental PMS Production Readiness And Cutover Plan

Status date: 2026-05-10

Baseline:
`origin/master@26e2dc14d9af0620388b9b1db9ba25a522fa434e`

This is a docs-only accelerated production readiness and cutover planning
track. It does not perform readiness work, access R4, access/hash/inspect real
artefacts, use patient data, connect to any PMS database, run
validation/no-write, run guarded apply/write, perform finance import, perform
invoice/payment/staging import, perform live/default PMS DB writes, perform
actual PMS Postgres writes, or perform production cutover.

R4 remains the live/main PMS until a separate explicit owner cutover approval.
Dental PMS is not live yet and is not authorised as the live/main PMS by this
plan. Production readiness is not complete.

The R4 opening-balance full eligible-row non-live pathway is complete through
signed-off scratch/test-only guarded apply/write proof. `finance_import_ready`
remains `false`. Live finance import, live/default PMS DB writes, actual PMS
Postgres writes, invoice/payment/staging import, production execution, and
cutover remain unauthorised.

The business reconciliation plan and owner-provided business reconciliation
sign-off are now recorded. The execution tracker for the remaining production
readiness gaps is `docs/PRODUCTION_READINESS_EXECUTION_TRACKER.md`.

No patient-level contents, raw artefact contents, exact artefact paths, DSNs,
or secrets belong in this plan or any follow-up planning record.

## Acceleration Model

The project can move faster by running planning workstreams in parallel while
keeping all live writes and production execution behind explicit owner
approvals.

| Workstream | Output | May Proceed Before Cutover Approval? |
| --- | --- | --- |
| Business reconciliation | Owner/business review of signed-off non-live evidence and later docs-only sign-off record | Yes, docs-only |
| Production environment readiness | Health checklist for the target Dental PMS production environment | Yes, inspection/planning only |
| Backup/restore readiness | Backup inventory, restore proof plan, and restore acceptance criteria | Yes, planning; execution needs explicit ops approval |
| Rollback planning | Written rollback triggers, roles, data reset approach, and communication path | Yes, docs-only |
| Data migration readiness | Included/excluded data manifest and remaining import decision gates | Yes, docs-only |
| UAT/workflow testing | Human workflow checklist for reception, clinical, documents, recalls, finance views | Yes, test planning only |
| Smoke/regression testing | Pre-cutover and post-cutover smoke suite definition | Yes, planning and non-live test execution when separately approved |
| Go/no-go approval | Final owner decision record | No, requires explicit owner approval |

## Production Prerequisites

Production readiness cannot be claimed until all of the following are accepted:

- confirmed current backups for the existing live system and Dental PMS;
- restore proof for the Dental PMS production backup path;
- production environment health accepted, including application, worker,
  storage, certificates, and service availability checks;
- domain, DNS, and access readiness accepted where applicable;
- user roles and access reviewed, including admin, clinical, reception, and
  finance permissions;
- audit logging enabled and reviewed for login, patient, appointment, document,
  finance, and administrative actions;
- monitoring and alert ownership defined;
- cutover communication prepared for owner, operators, and support contacts;
- support owner named for cutover day and the first production support window;
- rollback owner named and authorised to stop the cutover if criteria are met;
- no unredacted DSNs, credentials, secrets, or exact artefact paths appear in
  committed planning records.

## Data Migration Prerequisites

The final readiness record must define the data scope exactly before any live
write or production execution approval:

- included data domains, by source and target domain;
- excluded data domains, with reason and owner acceptance;
- opening-balance status, including the completed non-live proof and business
  reconciliation sign-off status;
- patient data status, including included demographics, archive/deceased
  handling, duplicate policy, and known exclusions;
- appointment status, including past appointments, future diary policy, null
  patient handling, clinician mapping, and conflict policy;
- treatments and charting status, including canonical charting transcript
  status and any clinical rule confidence gaps;
- recalls status, including whether R4 recall import is excluded, deferred, or
  separately proven;
- finance import status, with `finance_import_ready=false` unless a later
  explicit owner-approved readiness record changes it;
- invoice/payment/staging import status, currently unauthorised and not
  included in this planning slice;
- all live/default PMS DB writes and actual PMS Postgres writes kept behind
  explicit owner approval.

## Go/No-Go Criteria

A go decision can be considered only if all criteria are met:

- PR #643 has been merged or otherwise superseded by an accepted reconciliation
  plan;
- business reconciliation sign-off has been recorded in a separate docs-only
  PR;
- production readiness checklist is complete and accepted;
- backup and restore proof is accepted;
- rollback plan is accepted and owned;
- production-like rehearsal is complete in a non-live target and reviewed;
- included/excluded data scope is accepted by the owner;
- UAT workflow checklist is complete or explicitly waived by the owner;
- smoke/regression plan is accepted with pass/fail thresholds;
- known blockers are either resolved or explicitly accepted as non-blocking;
- owner approval explicitly authorises any live/default PMS DB write, actual
  PMS Postgres write, production execution, live finance import,
  invoice/payment/staging import, and Dental PMS live/main PMS status.

A no-go decision is required if any of the following apply:

- business reconciliation is absent, incomplete, disputed, or blocked;
- backups or restore proof are missing or stale;
- production environment health is unknown or failing;
- rollback ownership or rollback trigger criteria are unclear;
- included/excluded data scope is ambiguous;
- `finance_import_ready` is still `false` and a live finance import is being
  requested;
- patient, appointment, charting, recall, or finance migration scope has a
  material unresolved business blocker;
- UAT or smoke/regression checks fail without explicit owner acceptance;
- any requested action would make Dental PMS live/main PMS without a separate
  explicit owner cutover approval.

## Rollback Criteria

Cutover planning must define rollback before production execution. Rollback is
triggered if any accepted threshold is breached, including:

- production login, patient search, appointment booking, or patient record
  access fails after cutover;
- clinical charting or treatment history is materially unavailable for the
  agreed launch scope;
- opening balances or finance views diverge from the accepted migration scope;
- audit logging is unavailable for patient or finance actions;
- user roles or access controls are materially wrong;
- production performance blocks normal reception or clinical workflows;
- support owner or rollback owner cannot be reached during the support window;
- any live/default PMS DB write, actual PMS Postgres write, finance import, or
  production execution occurs outside the approved cutover envelope.

Rollback planning must define who decides, what data is retained for diagnosis,
how operators are notified, how R4 remains or returns as live/main PMS, and how
Dental PMS is prevented from accepting live operational changes after rollback.

## Explicit Approvals Still Required

This plan does not authorise any of the following. Each requires a separate,
explicit owner approval:

- live/default PMS DB writes;
- actual PMS Postgres writes;
- production execution;
- production cutover;
- live finance import;
- invoice/payment/staging import;
- Dental PMS becoming the live/main PMS.

## Fast-Track Sequence

The fastest safe sequence is:

1. Keep the independent business reconciliation plan and owner sign-off on
   `master`.
2. Use `docs/PRODUCTION_READINESS_EXECUTION_TRACKER.md` to close readiness
   evidence gaps in parallel.
3. Complete this production readiness checklist without performing live writes
   or cutover.
4. Run a production-like rehearsal only after a separately scoped approval
   defines the target, data scope, rollback handling, and evidence to collect.
5. Review the go/no-go decision with the owner.
6. Only then consider live import, live/default PMS DB writes, actual PMS
   Postgres writes, production execution, or Dental PMS live/main PMS cutover.

Until that sequence reaches an explicit owner go decision, R4 remains the
live/main PMS and Dental PMS remains not live.
