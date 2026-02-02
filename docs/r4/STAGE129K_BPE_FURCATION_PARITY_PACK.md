# Stage 129K - BPEFurcation parity pack

## Scope

- Source table: `dbo.BPEFurcation` (SQL Server, SELECT-only)
- Patient/date bounds are inherited from parent `dbo.BPE` rows via `BPEFurcation.BPEID -> BPE.(BPEID|RefId|ID)`
- Canonical domain: `bpe_furcation`

## Semantics

- `unique_key`: `bpe_furcation|dbo.BPEFurcation|<BPEID>|<PatientCode>` (fallback uses `pkey` when needed)
- `latest_key` per patient: max(`recorded_at`, `bpe_id`)
- `latest_digest`: `recorded_at` + `furcation_1..furcation_6`
- Domain outcome:
  - `pass`: latest key and digest match
  - `fail`: mismatch
  - `no_data`: no SQL rows in bounds

## Validation checklist

1. Import mapped patients for cohort.
2. Run `charting_canonical --apply` with `--patient-codes` and bounded dates.
3. Rerun apply to confirm idempotency (`updated = 0`).
4. Run `r4_bpe_furcation_parity_pack.py` and compare SQL Server vs canonical.

## Validation result (2026-02-02)

- Cohort (5 active furcation patients): `1007995,1010772,1016933,1016945,1012221`
- `patients` import created mappings for all 5 (`patients_created=5`).
- `charting_canonical` apply+rerrun:
  - first apply: `created=54, updated=0, skipped=0, unmapped_patients=0`
  - rerun: `created=0, updated=0, skipped=54, unmapped_patients=0` (idempotent)
- Parity pack output:
  - latest key matched for all 5 (`recorded_at + bpe_id`)
  - latest digest matched for all 5 (`furcation_1..furcation_6`)
  - SQL/raw and canonical distinct key counts matched per patient.

## Commands

```bash
# Import canonical rows for bounded cohort
python -m app.scripts.r4_import \
  --entity charting_canonical \
  --source sqlserver \
  --patient-codes "<CSV>" \
  --charting-from 2017-01-01 --charting-to 2026-02-01 \
  --limit 500 --confirm APPLY --apply

# Run parity
python -m app.scripts.r4_bpe_furcation_parity_pack \
  --patient-codes "<CSV>" \
  --date-from 2017-01-01 --date-to 2026-02-01 \
  --row-limit 500 \
  --output-json /tmp/stage129k_bpe_furcation_parity.json \
  --output-csv /tmp/stage129k_bpe_furcation_parity.csv
```
