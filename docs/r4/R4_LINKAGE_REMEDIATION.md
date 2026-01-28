# R4 Linkage Remediation Plan + Resolution Queue

Date window (pilot): 2025-01-01 to 2026-01-28 (limit 50)

## Pilot report summary
- Appointments scanned: 50
- Unmapped: 50
- Reasons:
  - missing_patient_mapping: 45
  - missing_patient_code: 5
- Top unmapped patient codes:
  - 1012195 (10), 1007995 (2), remaining codes appear once

Raw outputs:
- `docs/r4/R4_LINKAGE_REPORT_2025-01-01_2026-01-28.json`
- `docs/r4/R4_LINKAGE_REPORT_2025-01-01_2026-01-28.csv`

## Buckets + remediation actions

Bucket | Description | Suggested action
--- | --- | ---
missing_patient_code | R4 appointment row has no patient code | Flag for data quality; treat as unresolvable without upstream fix.
missing_patient_mapping | Patient code exists, but no mapping in Postgres | Create mapping via standard R4 patient import; if high value, add manual override for patient code.
mapped_to_deleted_patient | Mapping exists but points to a soft-deleted patient | Decide whether to restore patient or remap; record decision in overrides/notes.
pmsrecordid_parse_failure | PMSRecordID exists but failed conversion | Inspect data format; expand parser or add manual override.
duplicate_mapping | Multiple possible targets for same legacy id | Investigate duplicates; resolve with manual override + audit note.

## Resolution queue (Postgres)

Tables:
- `r4_linkage_issues`: queue of unresolved items (one per legacy id).
- `r4_manual_mappings` (optional): manual overrides for high-value cases.

Key behavior:
- Queue upserts are keyed by `(legacy_source, entity_type, legacy_id)`.
- Loads are idempotent; existing status is preserved (open/resolved/ignored).

## Workflow (minimal)

1) Generate report (read-only R4):
```
docker compose exec -T backend python -m app.scripts.r4_linkage_report \
  --from 2025-01-01 --to 2026-01-28 --limit 50 \
  --output-json /tmp/r4_linkage.json --output-csv /tmp/r4_linkage.csv
```

2) Load queue from CSV:
```
docker compose exec -T backend python -m app.scripts.r4_linkage_queue_load \
  --input-csv /tmp/r4_linkage.csv --input-json /tmp/r4_linkage.json
```

3) Review buckets:
- Use `r4_linkage_issues` counts by reason/status to prioritise.
- Keep manual overrides small and auditable.

## Manual override guidance

Use `r4_manual_mappings` for a small, explicit set of mappings:
- One row per legacy patient code (or person key).
- Include a note with the decision rationale and source evidence.
- Do not auto-guess mappings; only human-confirmed entries go here.
