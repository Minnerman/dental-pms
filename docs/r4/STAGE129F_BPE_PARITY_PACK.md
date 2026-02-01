# Stage 129F: BPE parity spot-check pack

Purpose: produce a repeatable, patient-level BPE timeline report from the canonical store and compare latest BPE values to SQL Server (SELECT-only).

## Guardrails

- R4 SQL Server is read-only (`R4_SQLSERVER_READONLY=true`).
- No schema changes or writes on SQL Server.
- Spot-check only; no UI changes in this step.

## Script

- `backend/app/scripts/r4_bpe_parity_pack.py`

The script outputs, per patient:

- full canonical BPE timeline (`recorded_at` + sextants)
- SQL Server BPE timeline (optional)
- derived latest BPE row for each source
- a simple latest-row parity check (`recorded_at`, sextants)

## Usage

```bash
cd ~/dental-pms
export R4_SQLSERVER_READONLY=true

docker compose exec -T backend python -m app.scripts.r4_bpe_parity_pack \
  --patient-codes 1000035,1000036,1000037,1000363,1000365 \
  --charting-from 2017-01-01 \
  --charting-to 2026-02-01 \
  --row-limit 100 \
  --output-json /tmp/stage129f_bpe_parity.json
```

Canonical-only mode:

```bash
docker compose exec -T backend python -m app.scripts.r4_bpe_parity_pack \
  --patient-codes 1000035,1000036 \
  --skip-sqlserver
```

## Parity checklist

For each patient in the report:

1. Confirm `canonical_count` and `sqlserver_count` are non-zero.
2. Compare `canonical_latest` vs `sqlserver_latest` (date + sextants).
3. If mismatch, review full timelines for drift:
   - imported row missing,
   - differing sextant values,
   - date mismatch (timezone/day boundary).
4. Record findings in `docs/STATUS.md` before widening scope.

## Validation result (2026-02-01)

- Cohort: 5 patients (`1000035,1000036,1000037,1000363,1000365`).
- After patient mapping + canonical backfill, parity pack reported:
  - `canonical_count == sqlserver_count` for all 5 patients.
  - Latest BPE `recorded_at` matched for all 5.
  - Latest sextant values matched for all 5.
  - No parity warnings.
- Import stability for this cohort:
  - first apply: rows created/updated as expected,
  - rerun: `updated=0` (idempotent).
