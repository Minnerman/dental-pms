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

### SQL example (manual override)
```
insert into r4_manual_mappings (id, legacy_source, legacy_patient_code, target_patient_id, note)
values (
  gen_random_uuid(),
  'r4',
  1012195,
  12345,
  'Manual override: verified in PMS'
);
```

### Effect on report/queue/import
- Linkage report treats override-resolved patient codes as mapped.
- Queue loader skips missing mappings when an override resolves the patient code.
- R4 charting and treatment plan imports treat override-resolved codes as mapped (no skips).

### Admin API (staff only)
Requires an admin/staff role (external users are blocked with 403).

Create override:
```
curl -X POST "$API_URL/admin/r4/manual-mappings" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"legacy_patient_code":1012195,"target_patient_id":12345,"note":"Manual override"}'
```

List overrides:
```
curl "$API_URL/admin/r4/manual-mappings?legacy_patient_code=1012195" \
  -H "Authorization: Bearer $TOKEN"
```

### UI option (staff only)
Use the internal admin page:
- `/admin/r4/manual-mappings`
- View, add, and delete manual mappings (no PHI shown).

### Finding patient UUIDs from demographics
If you identify the patient in R4 by name/DOB, use this helper to find UUIDs:
```
docker compose exec -T backend python -m app.scripts.find_patient_uuid \\
  --first "FIRST" --last "LAST" --dob YYYY-MM-DD
```
Optional filters: `--postcode`, `--email`, `--phone`.

### Candidate packs
Generated candidate packs based on internal signals:
- `docs/r4/R4_MANUAL_MAPPING_CANDIDATES_2026-01-28.md`

## Stage 173 remediation pass (2026-01-28 14:23 UTC)

- Mappings added (safe exact legacy_id match): 0
- Needs review list: `docs/r4/R4_MANUAL_MAPPINGS_NEEDS_REVIEW_2026-01-28.csv`
- Safe mappings file (empty): `docs/r4/R4_MANUAL_MAPPINGS_SAFE_2026-01-28.csv`
- Report after: `docs/r4/R4_LINKAGE_REPORT_2025-01-01_2026-01-28_AFTER_2026-01-28.json`

Before → After (same window):
- missing_patient_mapping: 45 → 45
- missing_patient_code: 5 → 5
- mapped: 0 → 0

Top remaining unmapped codes (after):
- 1012195 (10)
- 1007995 (2)
- 1016090 (1)
- 1015376 (1)
- 1011407 (1)
- 1012098 (1)
- 1010864 (1)
- 1013684 (1)
- 1015469 (1)
- 1012223 (1)

## Stage 173c remediation pass (2026-01-28)

- Mappings added: 1 (legacy_patient_code 1012195 -> patient_id 321)
- Report after: `docs/r4/R4_LINKAGE_REPORT_2025-01-01_2026-01-28_AFTER_1012195_2026-01-28.json`

Before → After (same window):
- missing_patient_mapping: 45 → 35
- missing_patient_code: 5 → 5
- mapped: 0 → 10

Top remaining unmapped codes (after):
- 1007995 (2)
- 1016090 (1)
- 1015376 (1)
- 1011407 (1)
- 1012098 (1)
- 1010864 (1)
- 1013684 (1)
- 1015469 (1)
- 1012223 (1)
- 1014004 (1)
