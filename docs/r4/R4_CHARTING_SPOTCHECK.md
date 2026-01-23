# R4 charting spot-check (patient-level fidelity)

Goal: compare SQL Server charting rows and Postgres imports for a single patient.

## Why two patients (current data)

In this R4 instance:
- `dbo.BPEFurcation` and `dbo.PerioProbe` do not expose `PatientCode`.
- Linkage is confirmed via `BPE.RefId` (fallback for `BPE.BPEID`) and `Transactions.RefId`,
  respectively.
- Two patients are used for spot-checks to cover both linkage paths.

Use two patients for spot-checks:
- Patient 1000000: PerioProbe evidence.
- Patient 1000035: BPE entry + BPEFurcation evidence.

## Preconditions

Patient mappings must exist before spot-checking. If missing, run patients import
or pass `--ensure-mapping` to auto-create mappings for the target patient.

Import the patients and charting rows (bounded):

```bash
docker compose exec -T backend python -m app.scripts.r4_import --source sqlserver --entity patients --apply --confirm APPLY --patients-from 1000000 --patients-to 1000000 --stats-out /tmp/stage131/patients_1000000.json
docker compose exec -T backend python -m app.scripts.r4_import --source sqlserver --entity patients --apply --confirm APPLY --patients-from 1000035 --patients-to 1000035 --stats-out /tmp/stage131/patients_1000035.json

docker compose exec -T backend python -m app.scripts.r4_import --source sqlserver --entity charting --apply --confirm APPLY --patients-from 1000000 --patients-to 1000000 --stats-out /tmp/stage131/charting_1000000.json
docker compose exec -T backend python -m app.scripts.r4_import --source sqlserver --entity charting --apply --confirm APPLY --patients-from 1000035 --patients-to 1000035 --stats-out /tmp/stage131/charting_1000035.json
```

Note: The `--patients-from/--patients-to` filter does not scope `BPEFurcation` or `PerioProbe`
in this dataset because those tables do not expose `PatientCode`. Their linkage is derived
from `BPE.RefId` (fallback for `BPE.BPEID`) and `Transactions.RefId`, respectively.

## Spot-check tool (SQL Server + Postgres)

Generate a JSON side-by-side comparison (fails fast if mapping is missing):

```bash
docker compose exec -T backend python -m app.scripts.r4_charting_spotcheck --patient-code 1000000 --limit 20 > /tmp/stage131/spotcheck_1000000.json
docker compose exec -T backend python -m app.scripts.r4_charting_spotcheck --patient-code 1000035 --limit 20 > /tmp/stage131/spotcheck_1000035.json
```

The output includes:
- SQL Server rows for patient-scoped entities (notes, temporary notes, BPE entries).
- SQL Server BPEFurcation rows via `BPE.RefId`/`BPEID` join.
- SQL Server PerioProbe rows via `Transactions.RefId` join.
- Postgres rows for the imported tables, using the same keys.

To auto-create missing mappings on demand:

```bash
docker compose exec -T backend python -m app.scripts.r4_charting_spotcheck --patient-code 1000000 --ensure-mapping --limit 20 > /tmp/stage131/spotcheck_1000000.json
```

## PerioProbe dedupe semantics

PerioProbe rows are de-duplicated on import by the legacy key:
`trans_id + tooth + probing_point`.

The CSV `index.csv` includes both sample counts and full totals for PerioProbe:

- `sqlserver_count`: sample rows written to CSV (honors `--limit`)
- `sqlserver_total`: total rows for the patient after linkage
- `sqlserver_unique_count` / `sqlserver_duplicate_count`: unique/deduped split
- `postgres_count`: sample rows written to CSV (honors `--limit`)
- `postgres_total`: total imported rows for the patient

If the backend container does not mount the repo, write to container `/tmp` and copy out:

```bash
docker compose cp backend:/tmp/stage131/spotcheck_1000000.json /tmp/stage131/spotcheck_1000000.json
docker compose cp backend:/tmp/stage131/spotcheck_1000035.json /tmp/stage131/spotcheck_1000035.json
```

## Link explain tool (PerioProbe)

Explain the PerioProbe linkage pipeline for a single patient:

```bash
docker compose exec -T backend python -m app.scripts.r4_charting_link_explain --patient-code 1000000 --entity perio_probes > /tmp/stage135/perio_probe_explain_1000000.json
```

Add `--ensure-mapping` to auto-create the patient mapping if missing.

## Manual SQL (optional)

SQL Server (patient 1000035, BPE):

```sql
SELECT TOP (20) b.BPEID, b.PatientCode, b.Date, b.Sextant1, b.Sextant2, b.Sextant3, b.Sextant4, b.Sextant5, b.Sextant6
FROM dbo.BPE b WITH (NOLOCK)
WHERE b.PatientCode = 1000035
ORDER BY b.Date;

SELECT TOP (20) bf.pKey, bf.BPEID, bf.Furcation1, bf.Furcation2, bf.Furcation3, bf.Furcation4, bf.Furcation5, bf.Furcation6
FROM dbo.BPEFurcation bf WITH (NOLOCK)
JOIN dbo.BPE b WITH (NOLOCK) ON COALESCE(b.BPEID, b.RefId) = bf.BPEID
WHERE b.PatientCode = 1000035
ORDER BY bf.BPEID;
```

SQL Server (patient 1000000, PerioProbe via Transactions):

```sql
SELECT TOP (20) pp.TransId, pp.Tooth, pp.ProbingPoint, pp.PocketDepth, pp.Bleeding, pp.SubPlaque, pp.SupraPlaque
FROM dbo.PerioProbe pp WITH (NOLOCK)
JOIN dbo.Transactions t WITH (NOLOCK) ON t.RefId = pp.TransId
WHERE t.PatientCode = 1000000
ORDER BY pp.TransId;
```

Postgres (patient 1000035, BPE):

```sql
SELECT legacy_bpe_id, legacy_patient_code, recorded_at, sextant_1, sextant_2, sextant_3, sextant_4, sextant_5, sextant_6
FROM r4_bpe_entries
WHERE legacy_patient_code = 1000035
ORDER BY recorded_at
LIMIT 20;

SELECT legacy_bpe_furcation_key, legacy_bpe_id, tooth, furcation, sextant
FROM r4_bpe_furcations
WHERE legacy_bpe_id IN (
  SELECT legacy_bpe_id FROM r4_bpe_entries WHERE legacy_patient_code = 1000035
)
LIMIT 20;
```

Postgres (patient 1000000, PerioProbe by trans_id list from SQL Server):

```sql
SELECT legacy_probe_key, legacy_trans_id, tooth, probing_point, depth, bleeding, plaque
FROM r4_perio_probes
WHERE legacy_trans_id IN (<TRANS_ID_LIST_FROM_SQLSERVER>)
ORDER BY legacy_trans_id
LIMIT 20;
```
