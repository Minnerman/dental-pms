# R4 charting spot-check (patient-level fidelity)

Goal: compare SQL Server charting rows and Postgres imports for a single patient.

## Why two patients (current data)

In this R4 instance:
- `dbo.BPEFurcation` and `dbo.PerioProbe` do not expose `PatientCode`.
- BPE entries exist for patient codes (e.g. 1000035), while PerioProbe rows can only be linked
  via `Transactions.RefId -> PerioProbe.TransId`, which currently surfaces patient 1000000.
- No single patient code appears in both sets with the current linkage.

Until the patient linkage for `PerioProbe`/`BPEFurcation` is confirmed and encoded, use two
patients for spot-checks:
- Patient 1000000: PerioProbe evidence.
- Patient 1000035: BPE entry + BPEFurcation evidence.

## Preconditions

Import the patients and charting rows (bounded):

```bash
docker compose exec -T backend python -m app.scripts.r4_import --source sqlserver --entity patients --apply --confirm APPLY --patients-from 1000000 --patients-to 1000000 --stats-out /tmp/stage131/patients_1000000.json
docker compose exec -T backend python -m app.scripts.r4_import --source sqlserver --entity patients --apply --confirm APPLY --patients-from 1000035 --patients-to 1000035 --stats-out /tmp/stage131/patients_1000035.json

docker compose exec -T backend python -m app.scripts.r4_import --source sqlserver --entity charting --apply --confirm APPLY --patients-from 1000000 --patients-to 1000000 --stats-out /tmp/stage131/charting_1000000.json
docker compose exec -T backend python -m app.scripts.r4_import --source sqlserver --entity charting --apply --confirm APPLY --patients-from 1000035 --patients-to 1000035 --stats-out /tmp/stage131/charting_1000035.json
```

Note: The `--patients-from/--patients-to` filter does not scope `BPEFurcation` or `PerioProbe`
in this dataset because those tables do not expose `PatientCode`. Their linkage is derived
from `BPE.BPEID` and `Transactions.RefId`, respectively.

## Spot-check tool (SQL Server + Postgres)

Generate a JSON side-by-side comparison:

```bash
docker compose exec -T backend python -m app.scripts.r4_charting_spotcheck --patient-code 1000000 --limit 20 > /tmp/stage131/spotcheck_1000000.json
docker compose exec -T backend python -m app.scripts.r4_charting_spotcheck --patient-code 1000035 --limit 20 > /tmp/stage131/spotcheck_1000035.json
```

The output includes:
- SQL Server rows for patient-scoped entities (notes, temporary notes, BPE entries).
- SQL Server BPEFurcation rows via `BPEID` join.
- SQL Server PerioProbe rows via `Transactions.RefId` join.
- Postgres rows for the imported tables, using the same keys.

## Manual SQL (optional)

SQL Server (patient 1000035, BPE):

```sql
SELECT TOP (20) b.BPEID, b.PatientCode, b.Date, b.Sextant1, b.Sextant2, b.Sextant3, b.Sextant4, b.Sextant5, b.Sextant6
FROM dbo.BPE b WITH (NOLOCK)
WHERE b.PatientCode = 1000035
ORDER BY b.Date;

SELECT TOP (20) bf.pKey, bf.BPEID, bf.Furcation1, bf.Furcation2, bf.Furcation3, bf.Furcation4, bf.Furcation5, bf.Furcation6
FROM dbo.BPEFurcation bf WITH (NOLOCK)
JOIN dbo.BPE b WITH (NOLOCK) ON b.BPEID = bf.BPEID
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
