# Stage 129J: parity consolidation runner

Purpose: run all validated charting parity packs in one command and emit a single combined report.

## Unified runner

- Script: `backend/app/scripts/r4_parity_run.py`

Inputs:

- `--patient-codes` (required CSV)
- `--output-json` (required)
- `--output-dir` (optional per-domain JSON artefacts)
- `--domains` (optional subset: `bpe,perioprobe,patient_notes,treatment_notes`; default all)
- `--date-from`, `--date-to`, `--row-limit` (optional bounds)

## Domain outcomes

Each domain summary returns one status:

- `pass`: compared rows and all latest key/digest checks matched.
- `fail`: compared rows and at least one latest key/digest check mismatched.
- `no_data`: no SQL Server rows in bounds for that domain/patient cohort.

Overall status:

- `pass` if no domain is `fail`
- `fail` if any domain is `fail`

`overall.has_data` indicates whether at least one requested domain had comparable rows.

## Active cohort selectors

Added SELECT-only deterministic helpers in `backend/app/services/r4_charting/sqlserver_extract.py`:

- `get_distinct_bpe_patient_codes(...)`
- `get_distinct_patient_notes_patient_codes(...)`
- `get_distinct_treatment_notes_patient_codes(...)`

Ordering for all selectors: `MAX(date_col) DESC, PatientCode ASC`.

## Usage

```bash
cd ~/dental-pms
export R4_SQLSERVER_READONLY=true

docker compose exec -T -e R4_SQLSERVER_READONLY=true backend \
  python -m app.scripts.r4_parity_run \
  --patient-codes 1015167,1012195,1015066,1015329,1015317 \
  --date-from 2010-01-01 \
  --date-to 2026-02-01 \
  --output-json /tmp/stage129j_parity_combined.json \
  --output-dir /tmp/stage129j_domains
```

## Known limitations

- PerioProbe remains cohort-limited in this environment (single active patient in current dataset).
- `no_data` is reported explicitly and does not force overall `fail`.
