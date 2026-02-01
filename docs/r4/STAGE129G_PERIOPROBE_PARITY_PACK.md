# Stage 129G: PerioProbe parity spot-check pack

Purpose: produce a repeatable, patient-level PerioProbe parity report from canonical data and SQL Server (SELECT-only).

## Guardrails

- R4 SQL Server is read-only (`R4_SQLSERVER_READONLY=true`).
- No schema changes or writes on SQL Server.
- This stage verifies import fidelity only; no UI changes.

## Script

- `backend/app/scripts/r4_perioprobe_parity_pack.py`

## "Latest" definition

PerioProbe may be undated in some datasets.

1. If a row has a reliable `recorded_at`, latest selection is by `recorded_at` then `trans_id`.
2. If no date is available, latest selection falls back to max `trans_id`.

The report includes `mode` in the latest key to make this explicit.

## Report fields (per patient)

- `sqlserver_total_rows`, `canonical_total_rows`
- `sqlserver_distinct_unique_keys`, `canonical_distinct_unique_keys`
- `sqlserver_latest_key`, `canonical_latest_key`
- `latest_match`
- `sqlserver_latest_digest`, `canonical_latest_digest`
- `latest_digest_match`

Unique key for dedupe visibility: `trans_id:tooth:probing_point`.

## Usage

```bash
cd ~/dental-pms
export R4_SQLSERVER_READONLY=true

docker compose exec -T -e R4_SQLSERVER_READONLY=true backend \
  python -m app.scripts.r4_perioprobe_parity_pack \
  --patient-codes 1000035,1000036,1000037,1000363,1000365 \
  --charting-from 2017-01-01 \
  --charting-to 2026-02-01 \
  --row-limit 500 \
  --output-json /tmp/stage129g_perioprobe_parity.json
```

Canonical-only mode:

```bash
docker compose exec -T backend python -m app.scripts.r4_perioprobe_parity_pack \
  --patient-codes 1000035,1000036 \
  --skip-sqlserver
```

## Checklist

1. Confirm totals are non-zero for targeted patients.
2. Compare `latest_key` parity first.
3. Compare latest digest parity (tooth/probing_point/depth/bleeding/plaque).
4. If mismatched, inspect duplicate/raw vs distinct counts before changing mapping logic.
