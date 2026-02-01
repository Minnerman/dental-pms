# Stage 129I: TreatmentNotes canonical ingestion + parity pack

Chosen source: `dbo.TreatmentNotes`.

Why this source is a safe next target:

1. Direct patient identity via `PatientCode`.
2. Dated rows via `DateAdded`.
3. Stable row id via `NoteID`.
4. Clinically meaningful text payload in `NoteBody`.

## Canonical semantics

- Domain: `treatment_note`
- Source: `dbo.TreatmentNotes`
- Unique key: `treatment_note|dbo.TreatmentNotes|<NoteID>|<PatientCode>`
- Latest key: max(`DateAdded`, then `NoteID`) per patient

Latest key JSON shape:

```json
{"recorded_at": "<DateAdded ISO>", "note_id": <NoteID>}
```

Material digest fields:

- `recorded_at`
- `tp_number`
- `tp_item`
- `note_body` (whitespace-normalised)

`TStamp` is excluded from digest.

## Parity pack script

- `backend/app/scripts/r4_treatment_notes_parity_pack.py`

Per patient report fields:

- `sqlserver_total_rows`, `canonical_total_rows`
- `sqlserver_distinct_unique_keys`, `canonical_distinct_unique_keys`
- `sqlserver_latest_key`, `canonical_latest_key`
- `latest_match`
- `sqlserver_latest_digest`, `canonical_latest_digest`
- `latest_digest_match`

## Usage

```bash
cd ~/dental-pms
export R4_SQLSERVER_READONLY=true

docker compose exec -T -e R4_SQLSERVER_READONLY=true backend \
  python -m app.scripts.r4_treatment_notes_parity_pack \
  --patient-codes 1016312,1011486,1014474,1014154,1013619 \
  --date-from 2010-01-01 \
  --date-to 2026-02-01 \
  --row-limit 500 \
  --output-json /tmp/stage129i_treatment_notes_parity.json \
  --output-csv /tmp/stage129i_treatment_notes_parity.csv
```

## Validation result (2026-02-01)

Cohort: `1015167,1012195,1015066,1015329,1015317`.

- Charting canonical apply totals:
  - first run: `created=7`, `updated=0`, `skipped=0`, `unmapped_patients=0`
  - rerun: `created=0`, `updated=0`, `skipped=7` (idempotent)
  - by source: `dbo.TreatmentNotes` fetched 7
- Parity pack for all 5:
  - `latest_key` matched (`recorded_at + note_id`)
  - `latest_digest` matched
