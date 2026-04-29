# R4 Charting Canonical Dry-Run / Parity Summary

Status date: 2026-04-29

Baseline: `master@a89c2ee59aba469e37939dc287fc557dee63842e`

R4 policy: strictly read-only / SELECT-only. The completed scratch transcript used SELECT-only R4 access, performed no R4 writes, and limited PMS writes to the isolated scratch database.

## Scope

This report summarizes the current active `charting_canonical` state after PR #566. It is based on repo evidence in:

- `docs/STATUS.md`
- `docs/R4_MIGRATION_READINESS.md`
- `docs/r4/CHARTING_CANONICAL_READINESS.md`
- `backend/app/scripts/r4_import.py`
- `backend/app/scripts/r4_cohort_select.py`
- `backend/app/scripts/r4_parity_run.py`
- `backend/app/services/r4_charting/`
- `backend/tests/r4_import/`

This is a report-only slice. It does not change importer, extractor, parity, runtime, Docker, compose, ops, frontend, finance, appointments cutover, recalls, or document code.

## Completed Scratch Transcript

PR #566 fixed the SQL Server treatment-plan TP range blocker that had generated
invalid SQL of the form `ti.TPNumber >= ?  ti.TPNumber <= ?`. The fix preserves
the internal range `AND` with `removeprefix("AND")`.

The all-domain scratch transcript then completed successfully against:

- scratch project: `dentalpms_charting_scratch_20260428_220858`
- scratch DB: `dental_pms_charting_scratch`
- artefacts: `/home/amir/dental-pms-charting-scratch-execution/.run/charting_canonical_all_domain_dentalpms_charting_scratch_20260428_220858/`

Key results:

- dry-run: `total_records=70140`, `unmapped_patients=0`
- scratch apply: `created=70140`, `updated=0`, `unmapped_patients_total=0`
- idempotency rerun: `created=0`, `skipped=70140`
- consolidated parity: `overall.status=pass`, `domains_failed=0`,
  `domains_no_data=3`
- no-data domains: `chart_healing_actions`, `old_patient_notes`,
  `perio_plaque`
- final scratch counts: `r4_patient_mappings=3367`,
  `r4_charting_canonical_records=70140`
- data safety: no R4 writes; PMS writes were scratch-only

## Current Active Domain Set

The active CLI set is guarded across:

- `r4_import._CHARTING_CANONICAL_DOMAINS`
- `r4_cohort_select.ALL_DOMAINS`
- `r4_parity_run.ALL_DOMAINS`

The active 15-domain set is:

- `appointment_notes`
- `bpe`
- `bpe_furcation`
- `chart_healing_actions`
- `completed_questionnaire_notes`
- `completed_treatment_findings`
- `old_patient_notes`
- `patient_notes`
- `perio_plaque`
- `perioprobe`
- `restorative_treatments`
- `temporary_notes`
- `treatment_notes`
- `treatment_plan_items`
- `treatment_plans`

Reference-only charting rows remain outside the active patient-cohort parity set:

- `fixed_note`
- `note_category`
- `tooth_surface`
- `tooth_system`
- `treatment_plan_review`

## All-Domain Readiness Summary

All 15 active domains have current extractor/import/cohort/parity wiring. No active-domain wiring gap was found on current master.

Domains with recorded full, exhaustion, or accepted-cohort closure evidence for the current scoped window:

- `appointment_notes`
- `bpe`
- `bpe_furcation`
- `completed_treatment_findings`
- `patient_notes`
- `perioprobe`
- `restorative_treatments`
- `temporary_notes`
- `treatment_notes`
- `treatment_plan_items`
- `treatment_plans`

Domains with recorded deterministic proof closure that were included in the PR #566 all-domain scratch transcript:

- `completed_questionnaire_notes`
- `old_patient_notes`
- `perio_plaque`

Domain with prior no-data/exhaustion evidence for the scoped window:

- `chart_healing_actions`

No active 15-domain CLI member currently needs first wiring, first parity-pack support, or another isolated scale-out proof before an all-domain run.

## Dry-Run / Parity Execution Shape

The completed PR #566 run followed the isolated scratch approach below. R4 access remains SELECT-only; any `--apply --confirm APPLY` command below writes only to the isolated PMS database, not to R4.

Use the explicit domain list for auditability:

```bash
DOMAINS=appointment_notes,bpe,bpe_furcation,chart_healing_actions,completed_questionnaire_notes,completed_treatment_findings,old_patient_notes,patient_notes,perio_plaque,perioprobe,restorative_treatments,temporary_notes,treatment_notes,treatment_plan_items,treatment_plans
```

Select a deterministic all-domain cohort:

```bash
docker compose exec -T -e R4_SQLSERVER_READONLY=true backend python -m app.scripts.r4_cohort_select \
  --domains "$DOMAINS" \
  --date-from 2017-01-01 \
  --date-to 2026-02-01 \
  --limit 50000 \
  --mode union \
  --order hashed \
  --seed 564 \
  --output /tmp/charting_all_domain_codes.csv
```

Run a SELECT-only charting canonical dry-run/report for the selected cohort:

```bash
docker compose exec -T -e R4_SQLSERVER_READONLY=true backend python -m app.scripts.r4_import \
  --source sqlserver \
  --entity charting_canonical \
  --dry-run \
  --patient-codes-file /tmp/charting_all_domain_codes.csv \
  --charting-from 2017-01-01 \
  --charting-to 2026-02-01 \
  --domains "$DOMAINS" \
  --output-json /tmp/charting_all_domain_dryrun_report.json
```

If the dry-run is clean and the target DB is isolated, import patients first so canonical rows can map:

```bash
docker compose exec -T -e R4_SQLSERVER_READONLY=true backend python -m app.scripts.r4_import \
  --source sqlserver \
  --entity patients \
  --patient-codes-file /tmp/charting_all_domain_codes.csv \
  --apply \
  --confirm APPLY \
  --stats-out /tmp/charting_all_domain_patients_stats.json
```

Then apply, rerun for idempotency, and summarize parity:

```bash
docker compose exec -T -e R4_SQLSERVER_READONLY=true backend python -m app.scripts.r4_import \
  --source sqlserver \
  --entity charting_canonical \
  --patient-codes-file /tmp/charting_all_domain_codes.csv \
  --charting-from 2017-01-01 \
  --charting-to 2026-02-01 \
  --domains "$DOMAINS" \
  --batch-size 50 \
  --state-file /tmp/charting_all_domain_state.json \
  --run-summary-out /tmp/charting_all_domain_apply_summary.json \
  --apply \
  --confirm APPLY \
  --stats-out /tmp/charting_all_domain_apply_stats.json \
  --output-json /tmp/charting_all_domain_apply_report.json

docker compose exec -T -e R4_SQLSERVER_READONLY=true backend python -m app.scripts.r4_import \
  --source sqlserver \
  --entity charting_canonical \
  --patient-codes-file /tmp/charting_all_domain_codes.csv \
  --charting-from 2017-01-01 \
  --charting-to 2026-02-01 \
  --domains "$DOMAINS" \
  --batch-size 50 \
  --state-file /tmp/charting_all_domain_rerun_state.json \
  --run-summary-out /tmp/charting_all_domain_rerun_summary.json \
  --apply \
  --confirm APPLY \
  --stats-out /tmp/charting_all_domain_rerun_stats.json \
  --output-json /tmp/charting_all_domain_rerun_report.json

docker compose exec -T -e R4_SQLSERVER_READONLY=true backend python -m app.scripts.r4_parity_run \
  --patient-codes-file /tmp/charting_all_domain_codes.csv \
  --domains "$DOMAINS" \
  --date-from 2017-01-01 \
  --date-to 2026-02-01 \
  --output-json /tmp/charting_all_domain_parity.json \
  --output-dir /tmp/charting_all_domain_parity_domains
```

## Remaining Charting Risks

- The combined current-master all-domain scratch transcript is complete as of PR #566.
- `chart_healing_actions` has prior no-data/exhaustion evidence, so a different window may be needed if cutover inventory expects rows.
- `perio_plaque`, `completed_questionnaire_notes`, `old_patient_notes`, and `appointment_notes` have recent proof/closure coverage and are now included in the all-domain transcript.
- Historic odontogram rendering/rule confidence remains higher risk than canonical importer plumbing.
- Reference-only rows should stay out of active patient-cohort parity unless a cutover proof requires promotion.
- Patient mapping and unmapped-patient thresholds must be recorded before broad dry-run migration.

## Recommended Next 3 Slices

1. Merge this docs/evidence continuity refresh so the PR #566 transcript is the current charting canonical evidence baseline.
2. Clean up the scratch stack and project-scoped volume when the artefacts are no longer needed for inspection.
3. Resume broader migration readiness from `docs/R4_MIGRATION_READINESS.md`; the next major readiness area is appointments cutover readiness proof unless a charting rule-confidence review is deliberately chosen first.
