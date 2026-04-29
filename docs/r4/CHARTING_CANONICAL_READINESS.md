# R4 Charting Canonical Readiness

Status date: 2026-04-29

Baseline: `master@a89c2ee59aba469e37939dc287fc557dee63842e`

R4 policy: strictly read-only / SELECT-only. This report is a repo-evidence readiness map only. No live R4 query was run for this report.

## Purpose

Create one current map of the R4 charting canonical domains so future work can move by readiness class instead of continuing one isolated gap at a time.

Scope is the charting canonical path centered on:

- `backend/app/scripts/r4_import.py --entity charting_canonical`
- `backend/app/scripts/r4_cohort_select.py`
- `backend/app/scripts/r4_parity_run.py`
- `backend/app/services/r4_charting/sqlserver_extract.py`
- `backend/app/services/r4_charting/canonical_importer.py`

## Summary

- Active CLI domains are aligned and guarded across `r4_import`, `r4_cohort_select`, and `r4_parity_run`: 15 domains.
- Active extraction/import/parity gaps found in the 15-domain CLI set: none.
- Remaining active-flow work is scale/proof work, not basic wiring.
- Reference-only charting rows exist outside the active CLI set; they should not be mixed into scale-out work unless they are deliberately promoted to first-class parity domains.
- Highest-risk charting gap is still historic odontogram rendering rule confidence, not the canonical importer plumbing.
- PR #558 completed the backend test-only active-domain allowlist guard in `backend/tests/r4_import/test_r4_domain_allowlists.py`.
- PR #560 completed the backend proof-only live deterministic scale-out proof for `perio_plaque`, `completed_questionnaire_notes`, and `old_patient_notes` in `backend/tests/r4_import/test_live_charting_scaleout_proof.py`.
- PR #562 completed the backend proof-only `appointment_notes` accepted-cohort closure in `backend/tests/r4_import/test_appointment_notes_scaleout_proof.py`.
- PR #566 fixed the SQL Server treatment-plan TP range blocker and completed the current-master all-domain charting canonical scratch dry-run/apply/idempotency/parity transcript.

## Current All-Domain Transcript

PR #566 completed the combined active 15-domain scratch transcript using the
scratch target `dental_pms_charting_scratch` and artefacts under
`/home/amir/dental-pms-charting-scratch-execution/.run/charting_canonical_all_domain_dentalpms_charting_scratch_20260428_220858/`.

- SQL Server blocker fixed: treatment-plan TP range filters now preserve the
  internal `AND` instead of generating `ti.TPNumber >= ?  ti.TPNumber <= ?`.
- Dry-run passed with `total_records=70140` and `unmapped_patients=0`.
- Scratch apply passed with `created=70140`, `updated=0`, and
  `unmapped_patients_total=0`.
- Idempotency rerun passed with `created=0` and `skipped=70140`.
- Consolidated parity passed with `overall.status=pass`, `domains_failed=0`,
  and `domains_no_data=3`.
- The no-data domains were `chart_healing_actions`, `old_patient_notes`, and
  `perio_plaque`.
- R4 access remained SELECT-only with no R4 writes; PMS writes were limited to
  the scratch database.

## Active Canonical Domain Matrix

Legend:

- Full: live evidence records accepted-cohort closure or exhaustion for the current scoped window.
- Partial: live or test evidence exists, but not full accepted-cohort closure.
- Proof-only: unit/simulated proof exists without live scale-out evidence in this slice.
- N/A: not meaningful for reference-only or no-data domains.

| Domain | Canonical domain | R4 source identified | SQL Server extractor | Source/fixture support | Canonical importer | `r4_import` CLI | `r4_cohort_select` | `r4_parity_run` | Parity pack | Scale-out proof status | Known drop/filter rules | Remaining gap | Next action | Risk |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `bpe` | `bpe_entry` | `dbo.BPE` | Yes | Fixture + SQL source | Yes | Yes | Yes | Yes | Yes | Full: Stage 139 exhausted `1108` patients. | Requires patient/date columns; date bounds drop missing/out-of-range rows. | None for active flow; PR #566 all-domain transcript passed. | No new isolated slice; use PR #566 as current evidence baseline. | Low |
| `bpe_furcation` | `bpe_furcation` | `dbo.BPEFurcation` joined to `dbo.BPE` where needed. | Yes | Fixture + SQL source | Yes | Yes | Yes | Yes | Yes | Full: Stage 140 exhausted `1108` patients. | Requires BPE linkage columns; date bounds via linked BPE where selector path is used. | None for active flow; PR #566 all-domain transcript passed. | No new isolated slice; use PR #566 as current evidence baseline. | Low |
| `perioprobe` | `perio_probe` | `dbo.PerioProbe`, with transaction linkage fallback in source layer. | Yes | Fixture + SQL source | Yes | Yes | Yes | Yes | Yes | Full for eligible window: Stage 138 exhausted `6` patients. | Undated rows are eligible in bounded imports; source linkage prefers `PerioProbe.RefId` then `TransId` fallback. | Small live population only; PR #566 all-domain transcript passed for current window. | Expand only if future windows expose more rows. | Medium |
| `perio_plaque` | `perio_plaque` | `dbo.PerioPlaque` | Yes | Fixture + SQL source | Yes | Yes | Yes | Yes | Yes | Proof complete: PR #560 added the combined live deterministic scale-out proof with completed questionnaire and old patient notes. | Undated rows are eligible in bounded imports; patient/tooth keyed from plaque rows. | PR #566 all-domain transcript passed; broader cutover still needs full migration reconciliation. | No new isolated scale-out slice by default. | Medium |
| `chart_healing_actions` | `chart_healing_action` | `dbo.ChartHealingActions` | Yes | Fixture + SQL source | Yes | Yes | Yes | Yes | Yes | No-data/exhausted for prior in-window evidence; PR #538 added parity-pack proof. | Undated rows are included when bounded; selector can fall back to ID ordering when no date column is present. | Decide whether a different window has meaningful rows before more work. | Keep out of isolated scale-out unless inventory finds data. | Low-medium |
| `restorative_treatments` | `restorative_treatment` | `dbo.vwTreatments` | Yes | SQL source; no `FixtureSource` fixture. | Yes | Yes | Yes | Yes | Yes | Full: Stage 163C closed `974` accepted patients, full-cohort parity pass. | Completed rows only; status description allowlist; requires tooth, code id, valid surface; drops non-restorative statuses and not-completed rows. | PR #566 all-domain transcript passed; rendering rules remain separate risk. | Continue odontogram rule-confidence review only if charting stays the chosen track. | Medium-high |
| `completed_treatment_findings` | `completed_treatment_finding` | `dbo.vwCompletedTreatmentTransactions` | Yes | SQL source; no `FixtureSource` fixture. | Yes | Yes | Yes | Yes | Yes | Full: Stage 163F closed `2886` accepted patients, full-cohort parity pass. | Drops missing patient/tooth/code, out-of-window rows, duplicate keys, and rows classified as already-covered restorative treatments. | None for active flow; PR #566 all-domain transcript passed. | No new isolated slice; use PR #566 as current evidence baseline. | Medium |
| `appointment_notes` | `appointment_note` | `dbo.vwAppointmentDetails.notes` | Yes | SQL source; no `FixtureSource` fixture. | Yes | Yes | Yes | Yes | Yes | Proof complete: Stage 163H chunk 1 proved `200/1136`; PR #555 added proof-only continuation coverage; PR #562 completed accepted-cohort closure for the full `1136` accepted pool. | Requires patient code, appointment id, date, nonblank notes; drops missing patient/appt/date, out-of-window, blank notes, duplicate keys. | PR #566 all-domain transcript passed; broader cutover still needs full migration reconciliation. | No new isolated appointment-note scale-out slice by default. | Medium |
| `completed_questionnaire_notes` | `completed_questionnaire_note` | `dbo.CompletedQuestionnaire.Notes` | Yes | SQL source; no `FixtureSource` fixture. | Yes | Yes | Yes | Yes | Yes | Proof complete: PR #553 added the first combined proof with old patient notes; PR #560 added the combined live deterministic scale-out proof with `perio_plaque`. | Requires patient/date/note; drops missing patient/date, out-of-window, blank notes, duplicate keys. | PR #566 all-domain transcript passed; broader cutover still needs full migration reconciliation. | No new isolated scale-out slice by default. | Medium |
| `patient_notes` | `patient_note` | `dbo.PatientNotes` | Yes | Fixture + SQL source | Yes | Yes | Yes | Yes | Yes | Full/exhausted for current window: Stage 142 completed `4` patient cohort. | Requires note date under bounded runs; source id uses note number or note digest fallback. | Tiny eligible population only; PR #566 all-domain transcript passed. | Expand only if a wider window is selected. | Low-medium |
| `old_patient_notes` | `old_patient_note` | `dbo.OldPatientNotes` | Yes | Fixture + SQL source | Yes | Yes | Yes | Yes | Yes | Proof complete: PR #546 wired active flow; PR #553 added the first combined proof with completed questionnaire notes; PR #560 added the combined live deterministic scale-out proof with `perio_plaque`. | Requires note date under bounded runs; source id uses note number or note digest fallback; preserves tooth/surface/fixed note metadata. | PR #566 all-domain transcript passed; broader cutover still needs full migration reconciliation. | No new isolated scale-out slice by default. | Medium |
| `temporary_notes` | `temporary_note` | `dbo.TemporaryNotes` | Yes | Fixture + SQL source | Yes | Yes | Yes | Yes | Yes | Full: Stage 163G closed `1730` accepted patients, full-cohort parity pass. | Requires patient/date/note; blank notes dropped for accepted-cohort scale-out; duplicates tracked. | None for active flow; PR #566 all-domain transcript passed. | No new isolated slice; use PR #566 as current evidence baseline. | Low |
| `treatment_plans` | `treatment_plan` | `dbo.TreatmentPlans` | Yes | Fixture + SQL source | Yes | Yes | Yes | Yes | Yes | Full: Stage 135 closed `3109` patients. | Date anchored on creation date; undated rows can be included by importer and reported as undated. | PR #566 all-domain transcript passed; cutover proof still needed in broader treatment-plan migration. | No new isolated charting-canonical slice by default. | Medium |
| `treatment_plan_items` | `treatment_plan_item` | `dbo.TreatmentPlanItems` with parent `TreatmentPlans` date semantics. | Yes | Fixture + SQL source | Yes | Yes | Yes | Yes | Yes | Full: Stage 136 closed `3040` patients; Stage 141 tail probe exhausted. | Date anchored on parent plan creation date to avoid item-date false drops. | PR #566 all-domain transcript passed; SQL TP range fix is covered. | Keep date-anchor and TP-range guards covered in tests. | Medium |
| `treatment_notes` | `treatment_note` | `dbo.TreatmentNotes` plus optional `TreatmentPlanItems` tooth/surface lookup. | Yes | Fixture + SQL source | Yes | Yes | Yes | Yes | Yes | Full: Stage 137 closed `139` patients. | Requires note date; tooth/surface enriched from matching `(patient_code,tp_number,tp_item)` when unambiguous. | None for active flow; PR #566 all-domain transcript passed. | No new isolated slice; use PR #566 as current evidence baseline. | Low-medium |

## Reference / Legacy Charting Rows Outside The Active CLI Set

These are represented in models, source methods, fixtures, or the legacy `charting` importer, but they are not first-class active `charting_canonical` CLI domains in `r4_cohort_select` or `r4_parity_run`.

| Domain | R4 source identified | Current support | Active canonical gap | Recommended action | Risk |
| --- | --- | --- | --- | --- | --- |
| `tooth_system` | `dbo.ToothSystems` | Source methods, fixtures, legacy structured importer, and canonical fallback from generic `R4Source`. | Not exposed through active SQL Server `charting_canonical` extractor/cohort/parity flow. | Keep as reference import support unless cutover dry-run requires first-class parity. | Low |
| `tooth_surface` | `dbo.ToothSurfaces` | Source methods, fixtures, legacy structured importer, and canonical fallback from generic `R4Source`. | Not exposed through active SQL Server `charting_canonical` extractor/cohort/parity flow. | Keep as reference import support; validate via odontogram rule/golden corpus work. | Medium |
| `fixed_note` | `dbo.FixedNotes` | Source methods, fixtures, legacy structured importer, and canonical fallback from generic `R4Source`. | Not exposed through active SQL Server `charting_canonical` extractor/cohort/parity flow. | Treat as lookup/reference data for note interpretation; do not make patient-cohort parity unless needed. | Low |
| `note_category` | `dbo.NoteCategories` | Source methods, fixtures, legacy structured importer, and canonical fallback from generic `R4Source`. | Not exposed through active SQL Server `charting_canonical` extractor/cohort/parity flow. | Treat as lookup/reference data for note interpretation; do not make patient-cohort parity unless needed. | Low |
| `treatment_plan_review` | `dbo.TreatmentPlanReviews` | Source methods, fixtures, raw plan model support, and canonical fallback from generic `R4Source`. | Not a first-class active canonical/cohort/parity domain. | Decide whether reviews need a canonical parity lane or remain attached to treatment-plan raw/review metadata. | Medium |

## Findings

### Domains Fully Ready For Current Active Flow

These have end-to-end active-flow support and recorded full/exhaustion evidence for the current scoped window:

- `bpe`
- `bpe_furcation`
- `perioprobe`
- `restorative_treatments`
- `completed_treatment_findings`
- `patient_notes`
- `temporary_notes`
- `treatment_plans`
- `treatment_plan_items`
- `treatment_notes`
- `appointment_notes`

These have end-to-end active-flow support, recorded deterministic scale-out proof closure, and inclusion in the PR #566 all-domain scratch transcript:

- `perio_plaque`
- `completed_questionnaire_notes`
- `old_patient_notes`

### Domains Needing Scale-Out Only

None in the active 15-domain CLI set after PR #562.

### Domains Needing Extraction / Import / Parity Work

- Active 15-domain CLI set: none found.
- Reference-only set: `treatment_plan_review` is the main decision point if reviews need first-class canonical parity. Tooth systems, tooth surfaces, fixed notes, and note categories are reference rows and should stay out of patient-cohort scale-out unless a dry-run/cutover proof requires them.

### Highest-Risk Charting Gaps

- Odontogram rendering/rule confidence remains the main clinical risk. `restorative_treatments` and `completed_treatment_findings` are imported/parity-covered, but visible tooth-state interpretation still depends on evidence-backed rule maturity.
- Appointment-note accepted-cohort closure is complete as of PR #562 and included in the PR #566 all-domain scratch transcript.
- PR #560 closes the prior live deterministic scale-out proof gap for `perio_plaque`, `completed_questionnaire_notes`, and `old_patient_notes`; PR #566 includes those domains in the all-domain scratch transcript.
- Reference rows are not dangerous by themselves, but promoting them into active parity domains without a clear cutover need would broaden scope.

## Completed Follow-Up

- PR #558 added the active-domain allowlist guard test for `r4_import._CHARTING_CANONICAL_DOMAINS`, `r4_cohort_select.ALL_DOMAINS`, and `r4_parity_run.ALL_DOMAINS`.
- The guard pins the active 15-domain charting canonical scope and keeps reference-only charting domains out of broad active parity scope.
- PR #560 added `backend/tests/r4_import/test_live_charting_scaleout_proof.py`, proving combined deterministic union cohort selection, batched `charting_canonical` import CLI wiring, and consolidated parity for `perio_plaque`, `completed_questionnaire_notes`, and `old_patient_notes`.
- PR #562 added `backend/tests/r4_import/test_appointment_notes_scaleout_proof.py`, proving `appointment_notes` accepted-cohort closure across the remaining tail, deterministic import batching, and consolidated parity over the full accepted pool.
- PR #566 fixed the SQL Server treatment-plan TP range filter bug in `backend/app/services/r4_import/sqlserver_source.py`, added focused SQL-shape coverage in `backend/tests/r4_import/test_sqlserver_source.py`, and completed the current-master all-domain scratch transcript.

## Recommended Next Charting Slices

1. Keep the PR #566 all-domain scratch transcript as the current charting canonical evidence baseline.
   - Target: avoid repeating canonical dry-run/parity plumbing unless later code changes invalidate the transcript.
   - Why: active 15-domain dry-run, scratch apply, idempotency rerun, and consolidated parity all completed successfully.
   - Likely files: docs/evidence refresh only when the baseline changes.
   - Validation: use the PR #566 artefacts and future CI for code changes.
   - Risk: low for canonical plumbing; medium-high remains for clinical display/rule confidence.

2. If charting work continues before non-charting readiness, focus on odontogram golden-corpus/rule confidence.
   - Target: visible clinical rendering confidence rather than importer/parity wiring.
   - Why: the highest charting risk is now interpretation of historic charting into safe displays.
   - Likely files: focused docs/golden-corpus evidence or narrowly scoped charting tests.
   - Validation: existing charting parity/export tests plus any focused rule proof.
   - Risk: medium-high.

## Do Not Batch Yet

- Do not mix charting scale-out with finance, payments, invoices, balances, appointments cutover, recalls, or documents.
- Do not start broad odontogram rendering rule rewrites from this report.
- Do not promote reference-only domains into active parity domains unless a cutover proof requires that exact scope.
