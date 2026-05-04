# R4 Migration Readiness

Status date: 2026-05-03

Baseline: `master@d59e83b4c940cae6692919848fdb83e420127be5`

R4 policy: strictly read-only / SELECT-only. This document is a planning and readiness guide only. It does not authorise writes to R4, broad imports, or live cutover.

## Purpose

Move the R4 migration from one-small-gap-at-a-time work to a structured readiness programme. Future work should still use small PRs, but the PRs should now align to explicit readiness tracks:

- Track 1: finish small R4 charting and clinical lanes.
- Track 2: finance, payment, and balance source discovery/import/reconciliation.
- Track 3: appointments and recalls full import plus future diary proof.
- Track 4: full dry-run migration and cutover checklist.

## Current Migration Readiness Table

| R4 data area | R4 source identified? | Importer exists? | Parity/reconciliation exists? | Scale-out/full cohort proven? | Frontend/workflow support exists? | Remaining gap | Risk | Size |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Patients | Yes: `dbo.Patients` via `R4SqlServerSource.stream_patients`. | Yes: `r4_import --entity patients`. | Partial: mapping-quality reports, Postgres window verify, patient mapping/admin tooling. | Partial: 5,000-patient windows and many charting cohorts proven; full all-patient cutover dry-run not recorded. | Yes: core patient record, search, demographics, recalls, ledger, documents. | Full all-patient dry-run in isolated target DB, final mapping-quality report, duplicate/contact-data policy. | Medium | Medium |
| Past appointments | Yes: `dbo.vwAppointmentDetails`; live SELECT-only inventory records 101,051 appointments from 2001-10-27 to 2027-02-01, with 100,994 before the 2026-04-29 cutover date. The PR #584 scratch transcript used newer R4 source data with `101057` appointments and the same `100994` past rows. | Yes: `r4_import --entity appointments` into `r4_appointments`. | Strong for raw R4 staging and promotion planning: linkage report/queue, manual mappings, unmapped appointments admin, live inventory evidence, PR #571 pure helper proof, the 2026-04-30 scratch transcript mapped `99299` rows with `1752` expected null-patient rows and `0` actionable unmapped rows, PR #574's no-core-write promotion dry-run/report classified the full `101051` rows, PR #576 added the pure promotion plan helper/proof, PR #578 added the timezone/local-time proof, PR #580 added the conflict predicate proof, PR #582 added the guarded no-DB-write apply-plan prototype, and PR #584 completed the scratch-only guarded apply transcript. | Strong for scratch-only evidence: raw staging import created `101051`, idempotency rerun created `0` and skipped `101051`; PR #574 found `94156` status-policy promote candidates and kept core `appointments` unchanged at `0` before/after; PR #584 used current R4 data, created `94162` core appointments inside scratch only, reran idempotently with `skipped=94162`, refused `6895`, and proved default `dental_pms` refusal before session/open. | Partial: read-only R4 calendar/admin linking plus core appointments UI. | Scratch evidence is recorded and cleanup is complete; live/default core diary promotion remains out of scope until a separate explicit cutover decision. | High | Medium-large |
| Future appointments | Yes: same `dbo.vwAppointmentDetails`; live inventory records 57 rows on/after 2026-04-29, including `Cancelled`, `Pending`, and `Deleted` examples through 2027-02-01. The PR #584 scratch transcript saw `63` future rows from fresher R4 data. | Yes: same appointment importer. | Strong for scratch-only promotion planning and proof: live inventory evidence, PR #571 fail-closed status helper tests, full scratch raw import/linkage evidence, PR #574 promotion dry-run evidence, PR #576 promotion plan helper/proof, PR #578 timezone/local-time proof, PR #580 conflict predicate proof, PR #582 guarded apply-plan prototype, and PR #584 scratch-only guarded apply transcript are complete. | Strong for scratch-only reporting/planning/apply: PR #574 classified future booked/cancelled/deleted rows without core writes; PR #576 proves deterministic row-level planning without importer/apply wiring; PR #578 proves Europe/London local-wall-time handling; PR #580 proves overlap predicate semantics; PR #584 applied eligible rows only in scratch and reran idempotently. | Partial: core diary, booking, R4 calendar read-only. | Scratch evidence is recorded and cleanup is complete; no live/default active future diary promotion is authorised. | High | Medium-large |
| Clinical notes | Yes: `PatientNotes`, `TreatmentNotes`, `TemporaryNotes`, `OldPatientNotes`, `vwAppointmentDetails.notes`, `CompletedQuestionnaire.Notes`. | Yes for active canonical domains including patient, treatment, temporary, appointment, completed questionnaire, and old patient notes. | Yes for import/parity packs and deterministic cohort selectors for active note/finding domains, including PR #551 support for `appointment_notes`, `temporary_notes`, and `completed_treatment_findings`. | Strong for the active charting path: PR #560 completed the live deterministic scale-out proof covering completed questionnaire notes and old patient notes with `perio_plaque`; PR #562 completed `appointment_notes` accepted-cohort closure; PR #566 included the active note domains in the successful all-domain scratch dry-run/apply/idempotency/parity transcript. | Partial: charting notes/history surfaces exist, but not every note style has direct UI affordance. | No active canonical transcript gap; remaining note risk belongs to broader cutover policy/UI affordance review. | Medium | Medium |
| Odontogram/charting | Yes: treatment plans/items, treatments, BPE/BPEFurcation, PerioProbe, PerioPlaque, restorative treatments, completed treatment findings, chart healing actions, tooth systems/surfaces, notes. | Yes: `charting_canonical`, legacy charting tables, and raw support for charting foundations. | Yes: domain parity packs, consolidated parity runner, spotcheck/export tests, golden-corpus docs. | Strong: full cohort proven for treatment plans/items, BPE, furcations, perioprobe, restorative treatments, completed treatment findings, temporary notes; PR #560 completed the live deterministic scale-out proof for `perio_plaque`, `completed_questionnaire_notes`, and `old_patient_notes`; PR #562 completed `appointment_notes` accepted-cohort closure; PR #566 completed the current-master all-domain scratch dry-run/apply/idempotency/parity transcript. | Yes: charting API, odontogram, perio/BPE, treatment-plan overlays, charting viewer/export proofs. | Combined charting canonical transcript is complete; charting engine rule maturity/golden corpus remains high importance before broad historic cutover. | Medium-high | Medium |
| Treatment plans | Yes: `TreatmentPlans`, `TreatmentPlanItems`, `TreatmentPlanReviews`, `Treatments/Codes`. | Yes: raw `treatment_plans`, `treatments`; canonical `treatment_plans` and `treatment_plan_items`. | Yes for plans/items; reviews are imported in raw plan model but not a first-class canonical parity domain. | Partial/strong: Stage 105 raw full import, Stage 135/136 canonical cohorts exhausted; raw plan patient-id backfill/mapping still needs cutover proof. | Partial: admin R4 treatment-plan viewer and patient clinical treatment planning. | Decide whether `treatment_plan_reviews` needs canonical/parity lane; reconcile raw R4 plan tables against canonical display path. | Medium | Medium |
| Treatment transactions/history | Yes: `dbo.Transactions`. | Yes: `r4_import --entity treatment_transactions`. | Partial: idempotency/statistics; patient transaction API/UI proofs. | Partial: 184,505 transactions proven for 5,000-patient window, not full all-patient cutover. | Yes: read-only patient transactions tab. | Full-range import/reconcile, fee/cost semantics review before using as financial truth. | Medium | Medium |
| Users/clinicians | Yes: `dbo.Users`. | Yes: `r4_import --entity users`. | Basic idempotency and display-name usage in transaction/calendar views. | Partial: user import pilot recorded 77 users. | Partial: clinician names in R4 calendar/transactions; core PMS user/RBAC remains separate. | Cutover policy for R4 clinician identity vs PMS login accounts. | Low | Small |
| Recalls | Not confirmed in repo audit. PMS recall workflow exists, but no R4 recall source mapping was found. | No R4 recall importer found. | No R4 recall parity/reconciliation found. | No. | Yes: recalls dashboard, communications, letters, KPI, patient recall tab. | SELECT-only R4 recall source discovery, mapping of due dates/status/contact history, import/reconciliation design. | High | Large |
| Finance ledger | Yes: PR #586 identified `dbo.PatientStats`, `dbo.vwPayments`, `dbo.Adjustments`, `dbo.Transactions`, `dbo.PaymentAllocations`, `dbo.vwAllocatedPayments`, lookup tables, and scheme/classification sources; PR #587 added repeatable SELECT-only inventory evidence. | No R4 finance importer found. | No import reconciliation yet; PR #587 inventory records balance/payment/adjustment/transaction/allocation counts and key risks, and `docs/r4/R4_FINANCE_SIGN_CANCELLATION_ALLOCATION_POLICY.md` records the fail-closed source/sign/cancellation/allocation policy. | Inventory and policy only: live SELECT-only report complete, no finance records written. | Yes: PMS patient ledger, payments/adjustments, cash-up/outstanding/trends reports. | Pure finance classification/sign helper; opening balance reconciliation; decide whether `dbo.Transactions` costs are clinical history only or financial source. | High | Large |
| Invoices | No explicit R4 invoice/statement source confirmed; finance evidence suggests charges may need `dbo.Transactions`, `dbo.SundryCharges`, and adjustment/payment reconciliation rather than one-to-one invoice import. | No R4 invoice importer found. | No R4 invoice reconciliation found. | Inventory only. | Yes: PMS invoice, lines, issue/void, PDF. | Invoice/statement absence policy, numbering/history policy, VAT/discount/write-off semantics. | High | Large |
| Payments | Yes: `dbo.vwPayments` and `dbo.Adjustments` are high-confidence payment/refund/credit/cancellation sources; `PaymentAllocations`/`vwAllocatedPayments` provide sparse allocation/refund/advanced-payment evidence. | No R4 payment importer found. | No payment reconciliation yet; PR #587 found `44906` `vwPayments`, `47731` `Adjustments`, and `3130` allocation rows in each allocation source. | Inventory and policy only: no payment records written. | Yes: invoice payments, receipts, patient quick payments. | Pure classifier proof, refund mismatch reconciliation, allocation semantics, payment method mapping. | High | Large |
| Balances | Yes: `dbo.PatientStats` is the high-confidence balance/aged-debt snapshot source. | No R4 balance importer found. | No balance reconciliation yet; PR #587 found `17012` PatientStats rows, `1018` non-zero balances, total balance `-131342.13`, and aged debt 30-60 `379.84`, 60-90 `579.00`, 90+ `9370.98`. | Inventory only: no balance records written. | Yes: PMS patient balance and outstanding reports from ledger. | Opening-balance policy and reconciliation against transactions, payments, refunds, credits, allocations, and aged debt. | High | Medium |
| Documents/attachments | Not confirmed in R4 source audit. | No R4 document/attachment importer found. | No R4 document/attachment reconciliation found. | No. | Yes: PMS attachments, generated documents, PDFs, templates. | SELECT-only discovery for document/attachment metadata and binary storage; storage-size and PHI handling plan. | Medium-high | Large |
| Treatment/code catalog | Yes: `Treatments`, `Codes`, surface/material tables. | Yes: treatments importer and treatment-code sync helpers. | Partial: importer tests and code-label usage in charting. | Partial: treatments imported for treatment-plan work. | Yes: PMS treatments/fees admin and labels in charting. | Separate fee schedule vs clinical code semantics; sync policy for missing code labels. | Medium | Medium |

## Acceleration Opportunities

### Small Gaps Safe To Batch

- PR #551 completed the safe `r4_cohort_select` batch for `appointment_notes`, `temporary_notes`, and `completed_treatment_findings`; future batching should focus on guard tests or proof-only scale-out, not more selector plumbing for these domains.
- PR #553 completed the first combined proof for `completed_questionnaire_notes` and `old_patient_notes`; future work should treat those domains as ready for all-domain charting summary rather than repeating first-proof wiring.
- PR #555 completed the `appointment_notes` scale-out continuation proof, and PR #562 completed `appointment_notes` accepted-cohort closure; future appointment-note work should be driven by all-domain readiness evidence rather than another isolated continuation slice by default.
- PR #557 completed the all-domain charting canonical readiness report, and PR #558 completed the lightweight domain-set guard test comparing `r4_import`, `r4_parity_run`, and `r4_cohort_select` allowlists.
- PR #560 completed the live deterministic scale-out proof for `perio_plaque`, `completed_questionnaire_notes`, and `old_patient_notes`; next charting work should continue to follow `docs/r4/CHARTING_CANONICAL_READINESS.md`.
- PR #566 fixed the SQL Server treatment-plan TP range blocker and completed the all-domain charting canonical scratch dry-run/apply/idempotency/parity transcript with parity passing across the active 15-domain set.
- Batch docs/runbook alignment for canonical charting dry-run commands after the selector set is complete, if kept docs-only.

### Areas That Must Stay Separate

- Finance, invoices, payments, and balances must stay separate from charting. They affect patient debt, cash-up, allocations, and live cutover risk.
- Past/future appointments must stay separate from finance and charting because future diary cutover has operational risk.
- Documents/attachments should stay separate until binary storage, PHI handling, and file-size behaviour are known.
- Odontogram engine/rule work should stay separate from importer plumbing. Rule mistakes can produce clinically misleading chart displays.

### Proof-Only Tasks Before More Code

- SELECT-only finance source discovery and inventory are complete as of PR #586 and PR #587. Finance sign/cancellation/allocation policy is recorded in `docs/r4/R4_FINANCE_SIGN_CANCELLATION_ALLOCATION_POLICY.md`; next proof should be a pure finance classification/sign helper before any importer or PMS finance writes.
- SELECT-only recall source inventory: due-date/status/contact-history tables and patient linkage.
- Isolated scratch appointment import/idempotency/linkage is complete as of the 2026-04-30 transcript: `r4_appointments` created `101051`, idempotency rerun created `0` and skipped `101051`, linkage mapped `99299` with `1752` expected null-patient rows and `0` actionable unmapped rows. Do not repeat it unless data freshness or code changes require it.
- No-core-write appointment promotion dry-run/report is complete as of PR #574: the scratch report considered `101051` rows, found `94156` status-policy promote candidates, `94156` patient-linked candidates, `94156` clinician-resolved candidates, `3726` deleted excluded rows, `1417` manual-review rows, `1752` null-patient read-only rows, and kept core `appointments` unchanged at `0` before/after.
- Appointment promotion plan helper/proof is complete as of PR #576: it classifies staging rows into eligible promotion candidates, excluded rows, manual-review rows, null-patient read-only rows, unmapped-patient rows, and clinician-unresolved rows without DB writes or importer/apply wiring.
- Appointment timezone/local-time proof is complete as of PR #578: naive R4 appointment datetimes are interpreted as Europe/London clinic-local wall times; valid local times convert to UTC-aware datetimes for future PMS core storage; invalid, missing, ambiguous fall-back, and non-existent spring-forward local times fail closed; importer/promotion behaviour remains unchanged.
- Appointment conflict predicate proof is complete as of PR #580: same-clinician exact/partial overlaps block for active existing statuses, back-to-back appointments do not conflict, `cancelled`/`no_show` and soft-deleted existing appointments do not block, missing/different clinicians do not conflict to match current core semantics, patient identity is irrelevant, aware datetimes compare by instant, and invalid/missing datetimes or missing/unknown existing statuses fail closed; route and promotion/import/apply behaviour remain unchanged.
- Guarded core-promotion apply-plan prototype is complete as of PR #582: it is backend-only and no-DB-write, requires a scratch/test DB URL and `SCRATCH_APPLY`, validates the prior no-core-write dry-run report, requires zero unmapped promote candidates, optionally requires zero unresolved clinicians, refuses null-patient/deleted/manual-review/invalid-datetime/conflicting rows, supports idempotency skip by legacy ID, and leaves routes/importers/runtime unchanged.
- Guarded scratch core-promotion CLI/prototype transcript is complete as of PR #584: the scratch run used current R4 source data with `101057` appointment rows and `63` future rows, created `94162` core appointments inside scratch DB `dental_pms_appointment_core_promotion_scratch`, reran idempotently with created `0` and skipped `94162`, refused `6895` rows (`3726` deleted/excluded, `1417` manual-review, `1752` null-patient read-only), proved default `dental_pms` refusal before session/open, kept R4 SELECT-only, made no R4 writes, and made PMS writes scratch-only.
- Current-master all-domain charting canonical scratch dry-run/parity transcript is complete as of PR #566; do not repeat it unless a later code change invalidates the evidence.
- Isolated full dry-run plan for patients, users, treatments, treatment plans, appointments, treatment transactions, and charting canonical domains before any live cutover discussion.

### Where Full Dry-Run Import Work Should Start

Start with an isolated target DB and non-financial domains:

1. Patients, users, treatment/code catalog.
2. Treatment plans/items and treatment transactions.
3. Charting canonical domains using the PR #566 all-domain scratch transcript as the current baseline.
4. Guarded R4 appointment core-promotion scratch transcript, using PR #574's no-core-write report, PR #576's promotion plan helper, PR #578's timezone/local-time proof, PR #580's conflict predicate proof, PR #582's guarded apply-plan prototype, and PR #584's scratch-only CLI/runbook transcript. Live/default core diary writes remain out of scope.
5. Only after the above is stable, continue finance policy/reconciliation proofs in isolation.

Do not start with finance or future diary writes into core live workflow tables.

## Recommended Next 5 Slices

1. Pure finance classification/sign helper.
   - Target: turn the fail-closed finance policy into a no-DB-write helper that classifies inventory-shaped R4 finance rows into payment, refund, credit, adjustment/write-off, cancellation/reversal, allocation, opening-balance, or manual-review categories.
   - Why next: source discovery, repeatable SELECT-only inventory, and policy are complete, but importer design remains unsafe until row-level signs, reversals, allocation semantics, and reason codes are executable and tested.
   - Likely files: backend pure helper and focused unit tests; no importer, staging model, or PMS DB session.
   - Likely validation: focused unit tests for known/unknown flag combinations, cancellation handling, sign preservation, patient-code requirement, and reason codes; no R4 writes and no PMS DB writes.
   - Backend-only/proof-only: yes.
   - Risk: high.

2. Recall source discovery.
   - Target: SELECT-only inventory of R4 recall due-date/status/contact-history candidates and patient linkage.
   - Why next: recalls remain a high-risk unmapped domain in the readiness table, but discovery can be kept proof-only before importer design.
   - Likely files: new discovery script or docs under `docs/r4/`, no importer initially.
   - Likely validation: command transcript, table/column/count report, no R4 writes.
   - Backend-only/docs-only: yes for discovery.
   - Risk: high.

3. Patients/users/treatment-code dry-run manifest.
   - Target: define the first isolated non-financial full-dry-run manifest for patients, users, and treatment/code catalog before broad cutover rehearsal.
   - Why next: these are the recommended starting domains for dry-run import work and avoid the higher-risk finance and future-diary write paths.
   - Likely files: docs/runbook or proof manifest only unless inspection finds a missing importer guard.
   - Likely validation: manifest review, existing importer tests for the listed domains, no R4 writes.
   - Backend-only/docs-only: likely yes.
   - Risk: medium.

4. Odontogram golden-corpus/rule-confidence review.
   - Target: review visible charting rule confidence now that canonical importer/parity evidence is stable.
   - Why next: PR #566 reduces canonical plumbing risk; clinical display interpretation remains a higher charting risk before broad historic cutover.
   - Likely files: docs/golden-corpus evidence or narrowly scoped frontend/backend charting tests if inspection finds a real rule gap.
   - Likely validation: existing charting parity/export tests plus any focused golden-corpus proof.
   - Backend/frontend: only if a visible rule gap is chosen deliberately.
   - Risk: medium-high.

5. Finance opening-balance reconciliation proof.
   - Target: after sign/cancellation/allocation policy, prove `PatientStats` balance/aged-debt reconciliation against payment, refund, credit, and allocation evidence without writing PMS finance records.
   - Why next: `1018` non-zero balances and total balance `-131342.13` are known; opening balances must reconcile before any finance import design.
   - Likely files: backend SELECT-only/report-only helper or docs evidence depending on policy outcome.
   - Likely validation: focused report tests, `git diff --check`, optional SELECT-only run, no PMS DB writes.
   - Backend-only/report-only likely: yes.
   - Risk: high.

## Cutover Readiness Gaps

### Before A Full Dry-Run Import

- Confirm isolated target DB setup, rollback/reset process, and storage sizing.
- Produce a domain manifest for every importable R4 entity and every intentionally skipped R4 entity.
- Complete active selector parity across import/parity domains.
- Define dry-run windows: all-patient patient import, full appointment range, full treatment transactions, all charting canonical domains, and treatment plans/items.
- Run mapping-quality reports for patient demographics and patient linkages.
- Define acceptable unmapped appointment and unmapped charting thresholds.
- Freeze the read-only R4 credential and environment setup in the runbook.

### Before Live Cutover

- Complete at least one isolated full dry-run and one rerun proving idempotency.
- Reconcile patient counts, appointment counts, charting domain counts, treatment-plan counts, and finance balances.
- Decide whether R4 appointments remain in `r4_appointments` read-only workflow or are promoted into core `appointments`.
- Lock future diary cutover timing and freeze rules for changes during migration.
- Complete finance opening-balance/payment allocation reconciliation.
- Complete PHI/document attachment migration policy if documents are in scope.
- Prepare operator checklist for final read-only snapshot, import, smoke tests, and rollback criteria.

### Reconciliation Required Against R4

- Patient counts by active/inactive/deceased/archive status if available.
- Appointment counts by date window, clinician, location, status, cancellation, and null patient code.
- Treatment plan/header/item counts and patient linkage.
- Charting canonical rows by domain and patient.
- Treatment transactions by patient and date range.
- Finance: invoices, payments, allocations, refunds/write-offs, outstanding balances, aged debt, cash-up totals.
- Recalls: due/overdue/booked/completed/declined counts and last-contact metadata.
- Documents/attachments: metadata counts, missing files, unsupported types, binary checksum strategy if available.

### Finance / Payment / Balance Risks

- R4 finance sources are now mapped at discovery/inventory level, but not imported or reconciled.
- Clinical `Transactions` costs may not equal accounting ledger truth.
- `vwPayments`, `Adjustments`, and allocation rows expose payments/refunds/credits/cancellations with sign and reversal semantics that are not yet policy-mapped.
- Refund counts differ between `vwPayments` (`110`) and `PaymentAllocations`/`vwAllocatedPayments` (`795`) and must be reconciled before ledger writes.
- Opening balances must reconcile to `PatientStats` balances and aged debt, not just imported invoices.
- Cash-up/payment-method totals must match date/method semantics used by the practice.

### Appointment Migration Risks

- Future diary migration affects live operations; mistakes are immediately user-visible.
- R4 status/cancelled/flag values now have inventory evidence, a design policy in `docs/r4/R4_APPOINTMENT_STATUS_POLICY.md`, PR #571 executable backend helper tests, a complete scratch raw `r4_appointments` import/idempotency/linkage transcript, PR #574's no-core-write promotion dry-run/report, PR #576's pure promotion plan helper/proof, PR #578's timezone/local-time proof, PR #580's conflict predicate proof, PR #582's guarded no-DB-write apply-plan prototype, and PR #584's scratch-only guarded core-promotion CLI/prototype transcript; live/default core diary promotion has not started.
- Null-patient appointments are known (`1752`) and must remain read-only/unlinked unless manually linked.
- Conflict predicate semantics are extracted/proven as of PR #580, guarded apply planning is proven as of PR #582, and scratch-only core write/idempotency evidence is complete as of PR #584; any live/default core diary promotion still needs a separate explicit cutover design, approval, and rehearsal.
- R4 clinician codes (`20`) and clinic code `1` must not be inferred as PMS users/rooms without explicit mapping.
- Recall-linked booking state must survive or be rebuilt deliberately.

### Clinical / Odontogram Parity Risks

- Odontogram rendering rules remain partly inferred from evidence rather than vendor documentation.
- Rule errors can produce clinically misleading history.
- Full historic charting import should not outrun golden-corpus/rule confidence.
- Appointment notes have accepted-cohort closure recorded in PR #562; completed questionnaire notes, old patient notes, and perio plaque have live deterministic scale-out proof recorded in PR #560.
- The PR #566 all-domain scratch transcript passed; future charting work should focus on golden-corpus/rule confidence or broader cutover reconciliation rather than repeating canonical importer/parity plumbing.

## Practical Speed-Up Strategy

### Track 1: Finish Small R4 Charting / Clinical Lanes

- Keep the PR #558 selector/import/parity allowlist guard green before widening active charting domains.
- Batch adjacent selector-only domains where code paths are identical.
- Use the PR #557 all-domain charting canonical readiness report to drive proof-only scale-out; keep future note chunks proof-only unless the report exposes a real implementation gap.
- Keep frontend work out unless a proof shows a visible workflow gap.

### Track 2: Finance / Payment / Balance

- Source discovery and repeatable SELECT-only inventory are complete as of PR #586 and PR #587.
- Finance sign/cancellation/allocation policy is recorded in `docs/r4/R4_FINANCE_SIGN_CANCELLATION_ALLOCATION_POLICY.md`.
- Next, add a pure finance classification/sign helper before any importer, staging model, or PMS finance write path.
- Keep invoices, payments, balances, and cash-up reconciliation in separate PRs.
- Do not import finance into live PMS tables until reconciliation rules are documented and tested.

### Track 3: Appointments / Recalls

- Split appointments into past diary and future diary readiness.
- Treat future diary as high risk and require dry-run evidence before implementation.
- Discover R4 recall sources separately, then map to existing PMS recall workflow.

### Track 4: Full Dry-Run Migration / Cutover

- Build an isolated full dry-run sequence that can be rerun idempotently.
- Produce a final reconciliation report by domain.
- Convert the dry-run sequence into a cutover checklist only after non-finance and finance proofs are both stable.
- Keep the preserved operational diff and runtime changes out of migration-readiness PRs unless explicitly scoped.
