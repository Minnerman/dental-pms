# Stage 163C Restorative Acceptance Rerun Checklist

Purpose: quick acceptance rerun after any restorative import/parity/tooth-state refactor.

## Preconditions
- `master` is up to date and working tree is clean.
- Stage 163C closure artefacts exist under `.run/stage163c/`:
  - `restorative_treatments_inventory.csv`
  - `stage163c_final_inventory_vs_ledger.json`
  - `stage163c_fullcohort_restorative_parity.json`
- R4 SQL Server remains SELECT-only (`R4_SQLSERVER_READONLY=true` in runtime commands).

## Fast Checks
1. Targeted backend regression pack:
```bash
docker compose exec -T backend pytest -q \
  tests/r4_import/test_sqlserver_extract.py \
  tests/r4_import/test_r4_import_cli.py \
  tests/r4_import/test_r4_restorative_treatments_drop_report.py \
  tests/r4_import/test_r4_restorative_treatments_parity_pack.py \
  tests/r4_import/test_r4_parity_run.py \
  tests/r4_import/test_r4_restorative_parity_smoke_pinned.py
```

2. Restorative parity smoke JSON (pinned 5-patient cohort):
```bash
docker compose -f docker-compose.yml -f docker-compose.r4.yml run --rm -T \
  -v "$(pwd)/.run/stage163d:/out" \
  -e R4_SQLSERVER_READONLY=true \
  backend python -m app.scripts.r4_parity_run \
    --domains restorative_treatments \
    --patient-codes 1010387,1012851,1011086,1001442,1015127 \
    --date-from 2017-01-01 \
    --date-to 2026-02-01 \
    --output-json /out/stage163d_restorative_parity_smoke.json
```

3. Real restorative odontogram proof spec:
```bash
cd frontend
ADMIN_EMAIL=... ADMIN_PASSWORD=... \
RESTORATIVE_PROOF_PATIENTS_FILE=/home/amir/dental-pms/.run/stage163d/restorative_proof_patients_stage163d.json \
RESTORATIVE_ODONTOGRAM_ARTIFACT_DIR=/home/amir/dental-pms/.run/stage163d \
npx playwright test tests/clinical-odontogram-restorative-real.spec.ts --reporter=line
```

## Expected Artefacts
- `.run/stage163d/stage163d_restorative_parity_smoke.json`
- `.run/stage163d/restorative_proof_patients_stage163d.json`
- `.run/stage163d/restorative_dropcase_patients_selected.json`
- `.run/stage163d/odontogram_restorative_real_*.png`

## Stop Conditions
- Any idempotency regression (`apply` rerun creates/updates unexpected rows).
- Any restorative parity fail (`overall.status != pass`).
- New unexpected drop-reason class appears or expected guard reasons spike materially without explanation.
- Any evidence of non-read-only SQL Server behavior.

## No-Data Interpretation
- `patients_no_data` in parity is warning-only and expected for patients with no SQL rows in-window; it is not a failure by itself.
