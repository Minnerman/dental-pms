# Stage 129H: PatientNotes parity pack (scaffold)

Chosen source: `dbo.PatientNotes`.

Why this source is next safest (from `docs/r4/R4_CHARTING_DISCOVERY.md`):

1. Direct patient identity via `PatientCode`.
2. Has note timestamp (`NoteDate`) suitable for bounds.
3. Stable row semantics (`NoteNumber`, note text, tooth/surface metadata).
4. Low mapping ambiguity for canonical domain `patient_note`.

## Script

- `backend/app/scripts/r4_patient_notes_parity_pack.py`

## Parity definition

Per patient, compare canonical vs SQL Server for:

- totals: raw and distinct unique keys
- latest key: `note_date + note_number`
- latest digest: `note`, `tooth`, `surface`

## Usage

```bash
cd ~/dental-pms
export R4_SQLSERVER_READONLY=true

docker compose exec -T -e R4_SQLSERVER_READONLY=true backend \
  python -m app.scripts.r4_patient_notes_parity_pack \
  --patient-codes 1000035,1000036,1000037,1000363,1000365 \
  --date-from 2017-01-01 \
  --date-to 2026-02-01 \
  --row-limit 500 \
  --output-json /tmp/stage129h_patient_notes_parity.json
```

## Checklist

1. Confirm selected patients have non-zero SQL Server rows.
2. Verify canonical rows exist for same patients (after bounded apply as needed).
3. Compare latest key parity.
4. Compare latest digest parity.
5. Record outcome in `docs/STATUS.md`.

## Note

This is scaffold-only. No extractor wiring changes are included in Stage 129H scaffold.
