# R4 charting discovery (Stage 128)

**R4 SQL Server is strictly read-only.** Codex must only run `SELECT` queries against R4. **No writes of any kind**: no `UPDATE/INSERT/DELETE/MERGE`, no DDL (`CREATE/ALTER/DROP`), no stored procedures, no temp-table side effects, no schema changes, and nothing that could modify or impact the R4 server.

Status: discovery-only. No UI or import changes in this stage. All R4 access is SELECT-only.

Goal: identify the exact R4 tables/views, keys, code systems, and rendering rules needed to match the R4 odontogram and related clinical charting behaviors.

## Candidate tables/views (from schema reconnaissance)

These are likely sources based on `sys2000` schema names and prior mapping notes. Confirm with SELECT-only queries before any import or UI work.

### Patient anchor
- `dbo.Patients`
  - Key: `PatientCode` (patient linkage)

### Charting foundations (odontogram)
- `dbo.ToothSurfaces`
  - Key: (`ToothId`, `SurfaceNo`)
  - Use: surface labels per tooth.
- `dbo.ToothSystems`
  - Key: `ToothSystemId`
  - Use: tooth numbering system definitions (FDI, Palmer, etc.).
- `dbo.ChartHealingActions`
  - Key: `ID`
  - Use: chart action history and possible links to treatment/appointments.

### Planned/completed work (likely drives chart overlays)
- `dbo.TreatmentPlans`
  - Key: (`PatientCode`, `TPNumber`) (+ `Index` if used for versions)
- `dbo.TreatmentPlanItems`
  - Key: `TPItemKey` (if globally unique) or (`PatientCode`, `TPNumber`, `TPItem`)
  - Fields: `Tooth`, `Surface`, `CodeID`, `Status`, `Date*`, `Material` (confirm).
- `dbo.TreatmentPlanReviews`
  - Key: (`PatientCode`, `TPNumber`)
  - Use: accepted/rejected status.
- `dbo.Treatments`
  - Key: `TreatmentCode`
  - Use: code descriptions, defaults.
- `dbo.SurfaceTreatment`
  - Key: (`SurfaceNo`, `CodeID`)
  - Use: allowed surfaces per treatment code.
- `dbo.MaterialTreatment`
  - Key: (`CodeID`, `MaterialCode`)
  - Use: materials per treatment code.

### Perio/BPE (chart overlay layer)
- `dbo.BPE`
  - Key: (`PatientCode`, `Date`) or identity column; `RefId` is present in this schema.
- `dbo.BPEFurcation`
  - Key: `pKey` with `BPEID` (confirm). In this schema, `BPEID` links to `BPE.RefId`.
- `dbo.PerioProbe`
  - Key: (`TransId`, `Tooth`, `ProbingPoint`) (confirm).
- `dbo.PerioPlaque`
  - Key: (`TransID`, `Tooth`) (confirm).

### Notes tied to charting
- `dbo.PatientNotes`
  - Key: (`PatientCode`, `NoteNumber`) or (`PatientCode`, `Date`, `NoteNumber`) (confirm).
  - Fields to confirm: tooth/surface indicators, note category codes.
- `dbo.FixedNotes`
  - Key: `FixedNoteCode`
- `dbo.NoteCategories`
  - Key: `CategoryNumber`
- `dbo.TreatmentNotes`
  - Key: `NoteID`
  - Use: notes per plan item.
- `dbo.TemporaryNotes`
  - Key: `PatientCode`
- `dbo.OldPatientNotes`
  - Key: (`PatientCode`, `NoteNumber`, `Date`)

## Key linkages to confirm

- `TreatmentPlanItems.PatientCode` -> `Patients.PatientCode`
- `TreatmentPlanItems.CodeID` -> `Treatments.TreatmentCode`
- `TreatmentPlanItems.Surface` -> `SurfaceTreatment.SurfaceNo`
- `TreatmentPlanItems.Material` -> `MaterialTreatment.MaterialCode`
- `ChartHealingActions.PatientCode` -> `Patients.PatientCode`
- Perio tables -> patient linkage via `Transactions.RefId` (confirmed for this dataset)
- BPEFurcation -> BPE via `BPEID`; use `BPE.RefId` when `BPE.BPEID` is absent (schema variant).

## Code systems to capture

- Tooth numbering system in active use (FDI/Palmer/Universal), and how stored (`ToothId`/`Tooth` values).
- Surface codes and labels (e.g., M/O/D/B/L/I/P or numeric).
- Treatment code mapping (treatment code -> chart overlay type/color/icon).
- Status enums for planned/completed/cancelled/observed.
- Material codes and display names.
- Special tooth states: missing, extracted, deciduous, implant, crown, RCT, bridge, partial denture, etc.

## Sample SELECT-only queries

Replace placeholders (`<PATIENT_CODE>`) and run with read-only credentials.

```sql
-- Identify tooth numbering systems
SELECT TOP (50) * FROM dbo.ToothSystems;

-- Surface labels per tooth
SELECT TOP (200) * FROM dbo.ToothSurfaces ORDER BY ToothId, SurfaceNo;

-- Planned treatment items for a patient
SELECT TOP (200)
  PatientCode, TPNumber, TPItem, TPItemKey, Tooth, Surface, CodeID, Status, Material, DateCreated, DateCompleted
FROM dbo.TreatmentPlanItems
WHERE PatientCode = <PATIENT_CODE>
ORDER BY TPNumber, TPItem;

-- Treatment plan headers
SELECT TOP (50)
  PatientCode, TPNumber, Status, DateCreated, DateAccepted
FROM dbo.TreatmentPlans
WHERE PatientCode = <PATIENT_CODE>
ORDER BY TPNumber DESC;

-- Treatment code metadata
SELECT TOP (50)
  TreatmentCode, TreatmentDesc, ShortDesc
FROM dbo.Treatments;

-- Surface mappings for a treatment code
SELECT TOP (50)
  CodeID, SurfaceNo
FROM dbo.SurfaceTreatment
WHERE CodeID = <TREATMENT_CODE>;

-- Perio/BPE summary for a patient
SELECT TOP (50)
  PatientCode, Date, Sextant1, Sextant2, Sextant3, Sextant4, Sextant5, Sextant6
FROM dbo.BPE
WHERE PatientCode = <PATIENT_CODE>
ORDER BY Date DESC;

-- Perio probing/presence
SELECT TOP (200)
  TransId, Tooth, ProbingPoint, Depth
FROM dbo.PerioProbe
WHERE TransId = <TRANS_ID>;

-- Stage 132: PerioProbe -> Transactions.RefId linkage proof
-- 1) Probes with a transaction
SELECT COUNT(1) AS probes_with_transaction
FROM dbo.PerioProbe pp
WHERE EXISTS (
  SELECT 1 FROM dbo.Transactions t WHERE t.RefId = pp.TransId
);

-- 2) Probes with a patient
SELECT COUNT(1) AS probes_with_patient
FROM dbo.PerioProbe pp
WHERE EXISTS (
  SELECT 1 FROM dbo.Transactions t
  WHERE t.RefId = pp.TransId AND t.PatientCode IS NOT NULL
);

-- 3) Ambiguous RefId -> multiple patients (should be 0)
SELECT COUNT(1) AS ambiguous_ref_ids
FROM (
  SELECT pp.TransId, COUNT(DISTINCT t.PatientCode) AS patient_count
  FROM dbo.PerioProbe pp
  JOIN dbo.Transactions t ON t.RefId = pp.TransId
  WHERE t.PatientCode IS NOT NULL
  GROUP BY pp.TransId
  HAVING COUNT(DISTINCT t.PatientCode) > 1
) q;

-- Stage 132: BPEFurcation -> BPE linkage proof (schema variant uses BPE.RefId)
-- 1) Furcations linked to a BPE entry
SELECT COUNT(1) AS furcations_with_bpe
FROM dbo.BPEFurcation bf
WHERE EXISTS (
  SELECT 1 FROM dbo.BPE b WHERE COALESCE(b.BPEID, b.RefId) = bf.BPEID
);

-- 2) Furcations linked to a patient (via BPE)
SELECT COUNT(1) AS furcations_with_patient
FROM dbo.BPEFurcation bf
WHERE EXISTS (
  SELECT 1 FROM dbo.BPE b
  WHERE COALESCE(b.BPEID, b.RefId) = bf.BPEID
    AND b.PatientCode IS NOT NULL
);

-- 3) BPEID reused across patients (should be 0)
SELECT COUNT(1) AS ambiguous_bpe_ids
FROM (
  SELECT COALESCE(b.BPEID, b.RefId) AS bpe_link_id,
         COUNT(DISTINCT b.PatientCode) AS patient_count
  FROM dbo.BPE b
  WHERE b.PatientCode IS NOT NULL
  GROUP BY COALESCE(b.BPEID, b.RefId)
  HAVING COUNT(DISTINCT b.PatientCode) > 1
) q;
```

## Mapping notes into PMS entities

- Planned work: `TreatmentPlanItems` map to planned chart overlays, keyed by patient + tooth + surface + treatment code.
- Completed work: determine whether completed items come from `TreatmentPlanItems` status or a separate transactions table.
- Tooth history: use `TreatmentNotes` and `PatientNotes` with tooth/surface metadata.
- Perio: map BPE and probing data to chart overlays (dates + sextant/point positions).

## Rendering rules checklist (must match R4 exactly)

- Tooth numbering system and order (upper/lower, left/right, permanent/deciduous).
- Surface labeling and draw order (e.g., occlusal vs mesial overlays).
- Planned vs completed vs historical color/shape rules.
- Material and restoration types (fillings, crowns, inlays, onlays, veneers, RCT, implants, bridges).
- Missing/extracted/unerupted/deciduous indicators.
- Perio marks: BPE sextant scores, probing depths, bleeding/plaque marks.
- Chart note markers and hover/detail behavior.
- How multiple items on the same tooth/surface stack (priority rules).
- Date-based filtering rules (current vs historical view).
- Any R4-specific iconography, legends, or status badges.

## Open questions / next discovery steps

- Confirm the exact R4 chart data tables and fields (verify candidates above).
- Identify the table that records completed procedures if not in `TreatmentPlanItems`.
- Confirm surface code encoding and tooth numbering system in production data.
- Capture at least one real patient chart end-to-end into Postgres to validate mapping.
- Gather screenshots of R4 chart states to codify rendering rules.
