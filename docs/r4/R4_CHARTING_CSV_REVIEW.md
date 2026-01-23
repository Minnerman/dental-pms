# R4 Charting CSV Review

## Purpose
Generate clinician-friendly CSV exports for a single patient from both SQL Server (R4 source) and Postgres (imported data) so the two can be compared side-by-side. This is a fidelity check only; no UI is involved.

## Command
From repo root, run the spot-check script with CSV output:

```bash
mkdir -p /tmp/stage133/patient_1000000
docker compose exec -T backend python -m app.scripts.r4_charting_spotcheck \
  --patient-code 1000000 \
  --format csv \
  --out-dir /tmp/stage133/patient_1000000
```

Optional filters:

```bash
docker compose exec -T backend python -m app.scripts.r4_charting_spotcheck \
  --patient-code 1000000 \
  --format csv \
  --out-dir /tmp/stage133/patient_1000000 \
  --entities perio_probes,bpe,bpe_furcations,tooth_surfaces,fixed_notes
```

## Outputs
The script writes:

- `index.csv`: counts + date ranges per entity and linkage method used.
- `sqlserver_<entity>.csv`: raw R4 source rows.
- `postgres_<entity>.csv`: imported rows from Postgres.

## Entities (default)
- `patient_notes`
- `temporary_notes`
- `treatment_notes`
- `chart_healing_actions`
- `bpe`
- `bpe_furcations`
- `perio_probes`
- `tooth_surfaces`
- `fixed_notes`

## Review checklist
- Counts match or have explainable differences (duplication guard, missing patient mapping).
- Date ranges align across SQL Server and Postgres for the same entity.
- Keys are stable and aligned (legacy keys, transaction IDs, BPE IDs).
- Clinical values match (tooth, surface/site, depth, sextant, notes).
- `patient_code` is consistent for all patient-scoped entities.

## Notes
- `tooth_surfaces` is a global lookup table; it is not patient-specific.
- `fixed_notes` are filtered to the fixed note codes referenced by the selected patient.
- Timestamps are normalized to ISO-8601 UTC strings.
