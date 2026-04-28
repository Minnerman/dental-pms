# R4 Migration Readiness

Status date: 2026-04-28

Baseline: `master@3effe87b52229461dd4751c02a60faacb4ab2f4c`

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
| Past appointments | Yes: `dbo.vwAppointmentDetails`; discovery records 100,812 appointments from 2001-10-27 to 2026-11-18. | Yes: `r4_import --entity appointments` into `r4_appointments`. | Partial: linkage report/queue, manual mappings, unmapped appointments admin. | Partial: Jan 2025 pilot and R4 calendar proof; full historical diary not proven. | Partial: read-only R4 calendar/admin linking plus core appointments UI. | Full historical import dry-run, status/cancelled semantics, patient-linkage closeout, decision on R4 read-only table vs core appointment migration. | High | Large |
| Future appointments | Yes: same `dbo.vwAppointmentDetails`; source has future rows through 2026-11-18 in documented discovery. | Yes: same appointment importer. | Partial: linkage report and R4 calendar filtering. | No full future diary/cutover proof recorded. | Partial: core diary, booking, R4 calendar read-only. | Future diary conflict/status proof, active appointment cutover policy, recall-linked booking behaviour after migration. | High | Large |
| Clinical notes | Yes: `PatientNotes`, `TreatmentNotes`, `TemporaryNotes`, `OldPatientNotes`, `vwAppointmentDetails.notes`, `CompletedQuestionnaire.Notes`. | Yes for active canonical domains including patient, treatment, temporary, appointment, completed questionnaire, and old patient notes. | Yes for import/parity packs and deterministic cohort selectors for active note/finding domains, including PR #551 support for `appointment_notes`, `temporary_notes`, and `completed_treatment_findings`. | Mixed/strong: patient/treatment/temporary notes have full/near-full evidence; PR #553 added the first combined proof for completed questionnaire and old patient notes; PR #555 completed the next `appointment_notes` scale-out continuation proof; PR #560 completed the live deterministic scale-out proof covering completed questionnaire notes and old patient notes with `perio_plaque`; PR #562 completed `appointment_notes` accepted-cohort closure. | Partial: charting notes/history surfaces exist, but not every note style has direct UI affordance. | Include active note domains in the future all-domain charting readiness summary; avoid repeating first-proof/continuation proof work unless a real failure appears. | Medium | Medium |
| Odontogram/charting | Yes: treatment plans/items, treatments, BPE/BPEFurcation, PerioProbe, PerioPlaque, restorative treatments, completed treatment findings, chart healing actions, tooth systems/surfaces, notes. | Yes: `charting_canonical`, legacy charting tables, and raw support for charting foundations. | Yes: domain parity packs, consolidated parity runner, spotcheck/export tests, golden-corpus docs. | Strong but mixed: full cohort proven for treatment plans/items, BPE, furcations, perioprobe, restorative treatments, completed treatment findings, temporary notes; PR #560 completed the live deterministic scale-out proof for `perio_plaque`, `completed_questionnaire_notes`, and `old_patient_notes`; PR #562 completed `appointment_notes` accepted-cohort closure. | Yes: charting API, odontogram, perio/BPE, treatment-plan overlays, charting viewer/export proofs. | All-domain dry-run/parity summary for current master; charting engine rule maturity/golden corpus still high importance before broad historic cutover. | High | Large |
| Treatment plans | Yes: `TreatmentPlans`, `TreatmentPlanItems`, `TreatmentPlanReviews`, `Treatments/Codes`. | Yes: raw `treatment_plans`, `treatments`; canonical `treatment_plans` and `treatment_plan_items`. | Yes for plans/items; reviews are imported in raw plan model but not a first-class canonical parity domain. | Partial/strong: Stage 105 raw full import, Stage 135/136 canonical cohorts exhausted; raw plan patient-id backfill/mapping still needs cutover proof. | Partial: admin R4 treatment-plan viewer and patient clinical treatment planning. | Decide whether `treatment_plan_reviews` needs canonical/parity lane; reconcile raw R4 plan tables against canonical display path. | Medium | Medium |
| Treatment transactions/history | Yes: `dbo.Transactions`. | Yes: `r4_import --entity treatment_transactions`. | Partial: idempotency/statistics; patient transaction API/UI proofs. | Partial: 184,505 transactions proven for 5,000-patient window, not full all-patient cutover. | Yes: read-only patient transactions tab. | Full-range import/reconcile, fee/cost semantics review before using as financial truth. | Medium | Medium |
| Users/clinicians | Yes: `dbo.Users`. | Yes: `r4_import --entity users`. | Basic idempotency and display-name usage in transaction/calendar views. | Partial: user import pilot recorded 77 users. | Partial: clinician names in R4 calendar/transactions; core PMS user/RBAC remains separate. | Cutover policy for R4 clinician identity vs PMS login accounts. | Low | Small |
| Recalls | Not confirmed in repo audit. PMS recall workflow exists, but no R4 recall source mapping was found. | No R4 recall importer found. | No R4 recall parity/reconciliation found. | No. | Yes: recalls dashboard, communications, letters, KPI, patient recall tab. | SELECT-only R4 recall source discovery, mapping of due dates/status/contact history, import/reconciliation design. | High | Large |
| Finance ledger | Not confirmed in R4 source audit. | No R4 finance importer found. | No R4 finance reconciliation found. | No. | Yes: PMS patient ledger, payments/adjustments, cash-up/outstanding/trends reports. | SELECT-only source discovery for finance ledger/account entries; decide whether `dbo.Transactions` costs are clinical history only or financial source. | High | Large |
| Invoices | Not confirmed in R4 source audit. | No R4 invoice importer found. | No R4 invoice reconciliation found. | No. | Yes: PMS invoice, lines, issue/void, PDF. | Source discovery for invoice/statement tables, numbering, VAT/discount/write-off semantics, PDF history policy. | High | Large |
| Payments | Not confirmed in R4 source audit. | No R4 payment importer found. | No R4 payment reconciliation found. | No. | Yes: invoice payments, receipts, patient quick payments. | Source discovery for payment rows, methods, allocations, refunds, cash-up linkage. | High | Large |
| Balances | Not confirmed in R4 source audit. | No R4 balance importer found. | No R4 balance reconciliation found. | No. | Yes: PMS patient balance and outstanding reports from ledger. | Opening-balance policy and reconciliation against R4 aged debt/statement balance. | High | Medium |
| Documents/attachments | Not confirmed in R4 source audit. | No R4 document/attachment importer found. | No R4 document/attachment reconciliation found. | No. | Yes: PMS attachments, generated documents, PDFs, templates. | SELECT-only discovery for document/attachment metadata and binary storage; storage-size and PHI handling plan. | Medium-high | Large |
| Treatment/code catalog | Yes: `Treatments`, `Codes`, surface/material tables. | Yes: treatments importer and treatment-code sync helpers. | Partial: importer tests and code-label usage in charting. | Partial: treatments imported for treatment-plan work. | Yes: PMS treatments/fees admin and labels in charting. | Separate fee schedule vs clinical code semantics; sync policy for missing code labels. | Medium | Medium |

## Acceleration Opportunities

### Small Gaps Safe To Batch

- PR #551 completed the safe `r4_cohort_select` batch for `appointment_notes`, `temporary_notes`, and `completed_treatment_findings`; future batching should focus on guard tests or proof-only scale-out, not more selector plumbing for these domains.
- PR #553 completed the first combined proof for `completed_questionnaire_notes` and `old_patient_notes`; future work should treat those domains as ready for all-domain charting summary rather than repeating first-proof wiring.
- PR #555 completed the `appointment_notes` scale-out continuation proof, and PR #562 completed `appointment_notes` accepted-cohort closure; future appointment-note work should be driven by all-domain readiness evidence rather than another isolated continuation slice by default.
- PR #557 completed the all-domain charting canonical readiness report, and PR #558 completed the lightweight domain-set guard test comparing `r4_import`, `r4_parity_run`, and `r4_cohort_select` allowlists.
- PR #560 completed the live deterministic scale-out proof for `perio_plaque`, `completed_questionnaire_notes`, and `old_patient_notes`; next charting work should continue to follow `docs/r4/CHARTING_CANONICAL_READINESS.md`.
- Batch docs/runbook alignment for canonical charting dry-run commands after the selector set is complete, if kept docs-only.

### Areas That Must Stay Separate

- Finance, invoices, payments, and balances must stay separate from charting. They affect patient debt, cash-up, allocations, and live cutover risk.
- Past/future appointments must stay separate from finance and charting because future diary cutover has operational risk.
- Documents/attachments should stay separate until binary storage, PHI handling, and file-size behaviour are known.
- Odontogram engine/rule work should stay separate from importer plumbing. Rule mistakes can produce clinically misleading chart displays.

### Proof-Only Tasks Before More Code

- SELECT-only finance source inventory: table names, row counts, date ranges, keys, payment methods, allocation model.
- SELECT-only recall source inventory: due-date/status/contact-history tables and patient linkage.
- Appointment future-diary proof: date-window counts, status/cancelled distribution, patient-null distribution, conflict-risk sample.
- Current-master all-domain charting canonical dry-run/parity summary from `docs/r4/CHARTING_CANONICAL_READINESS.md` after PR #562.
- Isolated full dry-run plan for patients, users, treatments, treatment plans, appointments, treatment transactions, and charting canonical domains before any live cutover discussion.

### Where Full Dry-Run Import Work Should Start

Start with an isolated target DB and non-financial domains:

1. Patients, users, treatment/code catalog.
2. Treatment plans/items and treatment transactions.
3. Charting canonical domains using deterministic cohorts and all-domain parity summaries.
4. R4 appointments into the read-only R4 appointment table, split into past and future date windows.
5. Only after the above is stable, start finance source discovery/import prototypes in isolation.

Do not start with finance or future diary writes into core live workflow tables.

## Recommended Next 5 Slices

1. Current-master all-domain charting canonical dry-run/parity summary.
   - Target: summarize active 15-domain charting canonical readiness from current master before broader migration dry-run work.
   - Why next: PR #557 established the active-domain readiness map, PR #558 guards the active 15-domain scope, PR #560 closes the combined deterministic scale-out proof for `perio_plaque`/`completed_questionnaire_notes`/`old_patient_notes`, and PR #562 closes `appointment_notes` accepted-cohort proof work.
   - Likely files: proof/evidence report only unless the dry-run exposes a real blocker.
   - Likely validation: deterministic cohort selection, `charting_canonical` import/rerun, consolidated parity over the selected active-domain scope.
   - Backend-only: likely yes unless a separate UI proof is explicitly chosen.
   - Risk: medium.

2. Appointments cutover readiness proof.
   - Target: SELECT-only/read-only proof pack for past vs future R4 appointment windows, status/cancelled distributions, null-patient counts, and linkage/manual-mapping backlog.
   - Why next: future diary migration is operationally high-risk and needs evidence before implementation.
   - Likely files: `backend/app/services/r4_import/sqlserver_source.py`, `backend/app/scripts/r4_linkage_report.py`, `backend/tests/appointments/test_r4_calendar.py`, docs/runbook if proof-only.
   - Likely validation: targeted appointment importer/linkage tests, R4 calendar tests, no broad frontend implementation unless proof reveals a required gap.
   - Backend-only: probably, with optional docs-only output.
   - Risk: high.

3. Finance/payment/balance source discovery.
   - Target: SELECT-only inventory of R4 finance, invoice, payment, allocation, balance, and cash-up candidate tables.
   - Why next: finance is the largest unknown and should not wait until late cutover; discovery is proof-only and does not force importer design yet.
   - Likely files: new discovery script or docs under `docs/r4/`, no importer initially.
   - Likely validation: command transcript, table/column/count report, no R4 writes.
   - Backend-only/docs-only: yes for discovery.
   - Risk: high.

4. Recall source discovery.
   - Target: SELECT-only inventory of R4 recall due-date/status/contact-history candidates and patient linkage.
   - Why next: recalls remain a high-risk unmapped domain in the readiness table, but discovery can be kept proof-only before importer design.
   - Likely files: new discovery script or docs under `docs/r4/`, no importer initially.
   - Likely validation: command transcript, table/column/count report, no R4 writes.
   - Backend-only/docs-only: yes for discovery.
   - Risk: high.

5. Patients/users/treatment-code dry-run manifest.
   - Target: define the first isolated non-financial full-dry-run manifest for patients, users, and treatment/code catalog before broad cutover rehearsal.
   - Why next: these are the recommended starting domains for dry-run import work and avoid the higher-risk finance and future-diary write paths.
   - Likely files: docs/runbook or proof manifest only unless inspection finds a missing importer guard.
   - Likely validation: manifest review, existing importer tests for the listed domains, no R4 writes.
   - Backend-only/docs-only: likely yes.
   - Risk: medium.

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

- R4 finance source tables are not yet mapped in repo evidence.
- Clinical `Transactions` costs may not equal accounting ledger truth.
- Payments may be split, partially allocated, refunded, reversed, or written off.
- Opening balances must reconcile to R4 patient statements and aged debt, not just imported invoices.
- Cash-up totals must match payment method/date semantics used by the practice.

### Appointment Migration Risks

- Future diary migration affects live operations; mistakes are immediately user-visible.
- R4 status/cancelled/flag values need deterministic mapping to PMS appointment states.
- Null-patient appointments are known and need an explicit handling policy.
- Timezone/local-time semantics must be proven for future appointments and daylight-saving boundaries.
- Recall-linked booking state must survive or be rebuilt deliberately.

### Clinical / Odontogram Parity Risks

- Odontogram rendering rules remain partly inferred from evidence rather than vendor documentation.
- Rule errors can produce clinically misleading history.
- Full historic charting import should not outrun golden-corpus/rule confidence.
- Appointment notes have accepted-cohort closure recorded in PR #562; completed questionnaire notes, old patient notes, and perio plaque have live deterministic scale-out proof recorded in PR #560.
- All-domain charting parity should be run after selector completion and recent note-lane proofs, before broad dry-run migration.

## Practical Speed-Up Strategy

### Track 1: Finish Small R4 Charting / Clinical Lanes

- Keep the PR #558 selector/import/parity allowlist guard green before widening active charting domains.
- Batch adjacent selector-only domains where code paths are identical.
- Use the PR #557 all-domain charting canonical readiness report to drive proof-only scale-out; keep future note chunks proof-only unless the report exposes a real implementation gap.
- Keep frontend work out unless a proof shows a visible workflow gap.

### Track 2: Finance / Payment / Balance

- Start with SELECT-only source discovery and a written source map.
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
