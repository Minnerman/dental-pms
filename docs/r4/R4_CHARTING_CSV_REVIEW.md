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

## Stage 134 review (2026-01-23)

### Patient 1000000 (perio-heavy + edge)
- Artefacts: `tmp/stage134/patient_1000000/`
- Entities reviewed: `perio_probes`, `temporary_notes`, `tooth_surfaces` (others empty).
- Outcome:
  - Perio probes mismatch: SQL Server count=20, Postgres count=0.
  - Temporary notes match (1 vs 1).
  - Tooth surfaces match (20 vs 20).
  - BPEFurcation comparison unavailable (linkage unsupported).

### Patient 1011978 (BPE-heavy)
- Artefacts: `tmp/stage134/patient_1011978/`
- Entities reviewed: `bpe`, `temporary_notes`, `tooth_surfaces`.
- Outcome:
  - BPE match (16 vs 16).
  - Temporary notes match (1 vs 1).
  - Tooth surfaces match (20 vs 20).
  - BPEFurcation comparison unavailable (linkage unsupported).

### Patient 1012056 (notes-heavy)
- Artefacts: `tmp/stage134/patient_1012056/`
- Entities reviewed: `patient_notes`, `bpe`, `temporary_notes`, `tooth_surfaces`.
- Outcome:
  - Patient notes match (20 vs 20).
  - BPE match (4 vs 4).
  - Temporary notes match (1 vs 1).
  - Tooth surfaces match (20 vs 20).
  - BPEFurcation comparison unavailable (linkage unsupported).

### Patient 1013684 (BPE-heavy)
- Artefacts: `tmp/stage134/patient_1013684/`
- Entities reviewed: `bpe`, `temporary_notes`, `tooth_surfaces`.
- Outcome:
  - BPE match (15 vs 15).
  - Temporary notes match (1 vs 1).
  - Tooth surfaces match (20 vs 20).
  - BPEFurcation comparison unavailable (linkage unsupported).

### Mismatch punch list (feeds Stage 135)
1) Perio probes missing in Postgres for patient 1000000.
   - SQL Server: `sqlserver_perio_probes.csv` shows 20 rows.
   - Postgres: `postgres_perio_probes.csv` shows 0 rows.
   - Suspected source: patient linkage or import filter logic for PerioProbe via Transactions.
2) BPEFurcation linkage unsupported in this R4 schema.
   - SQL Server BPE table lacks `BPEID`; `BPEFurcation` has `BPEID`.
   - Comparison currently blocked; need confirmed join key (likely `BPE.RefId`) or alternate linkage.
