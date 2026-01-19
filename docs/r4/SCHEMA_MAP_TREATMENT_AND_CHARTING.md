# R4 schema map: treatment planning + charting foundations (read-only)

Scope: identify likely keys and joins for treatment plans, charting foundations, perio/BPE, and notes. Inferences are based on table/column names from `sys2000` schema reconnaissance.

## Treatment planning core

### dbo.Patients
- Candidate primary key: `PatientCode`.
- Likely joins: `PatientCode` -> most clinical/treatment tables.
- Notes: patient demographics and flags; used as root entity.

### dbo.Treatments
- Candidate primary key: `TreatmentCode`.
- Likely joins: `Appts.TreatmentCode`, `TreatmentPlanItems.CodeID` (likely maps to treatment code set), `SurfaceTreatment.CodeID`, `MaterialTreatment.CodeID`.
- Notes: master treatment codes, descriptions, defaults.

### dbo.TreatmentPlans
- Candidate primary key: composite (`PatientCode`, `TPNumber`, `Index`) or (`PatientCode`, `TPNumber`) if `Index` is a version/order field.
- Likely joins: `TreatmentPlanItems` and `TreatmentPlanReviews` via `PatientCode` + `TPNumber`.
- Notes: plan header with status, acceptance, dates.

### dbo.TreatmentPlanItems
- Candidate primary key: `TPItemKey` (if globally unique) OR composite (`PatientCode`, `TPNumber`, `TPItem`).
- Likely joins:
  - `TreatmentPlanItemsICD10Codes` via `PatientCode` + `TPNumber` + `TPItem`.
  - `Patients` via `PatientCode`.
  - `TreatmentPlans` via `PatientCode` + `TPNumber`.
  - `Treatments` via `CodeID` (likely treatment code mapping).
  - `SurfaceTreatment` via `Surface` (if `Surface` maps to `SurfaceTreatment.SurfaceNo`).
  - `ApptNeeds` (not yet inspected) via `AppointmentNeedID`.
- Notes: itemized plan procedures; includes tooth/surface and costing.

### dbo.TreatmentPlanReviews
- Candidate primary key: composite (`PatientCode`, `TPNumber`).
- Likely joins: `TreatmentPlans` via `PatientCode` + `TPNumber`.
- Notes: review status and notes for a plan.

### dbo.TreatmentPlanItemsICD10Codes
- Candidate primary key: composite (`PatientCode`, `TPNumber`, `TPItem`, `ICD10CodeID`).
- Likely joins: `TreatmentPlanItems` via `PatientCode` + `TPNumber` + `TPItem`.
- Notes: diagnostic coding per plan item.

### dbo.SurfaceTreatment
- Candidate primary key: composite (`SurfaceNo`, `CodeID`).
- Likely joins: `TreatmentPlanItems.Surface` -> `SurfaceNo`, `TreatmentPlanItems.CodeID` -> `CodeID`.
- Notes: allowed/meaningful surfaces per treatment code.

### dbo.MaterialTreatment
- Candidate primary key: composite (`CodeID`, `MaterialCode`).
- Likely joins: `TreatmentPlanItems.CodeID` -> `CodeID` and `TreatmentPlanItems.Material` -> `MaterialCode`.
- Notes: material options per treatment code.

### Appointment ↔ treatment linkage
- `dbo.TApptTreatmentInfo`: candidate key `ApptId`; join to `Appts.ApptId`.
- `dbo.TApptNeedTreatmentInfo`: candidate key `ApptNeedId`; join to appointment-need table (not yet inspected).
- `dbo.TApptCheckOutTreatmentInfo`: candidate key `ApptId`; join to `Appts.ApptId`.
- `dbo.TWaitingApptTreatmentInfo`: candidate key `WaitingApptId`; join to `WaitingAppts.WaitingApptId`.

## Dental charting foundations (odontogram)

### dbo.ToothSurfaces
- Candidate primary key: composite (`ToothId`, `SurfaceNo`).
- Likely joins: `SurfaceTreatment.SurfaceNo` and plan item `Surface` (if same encoding).
- Notes: surface labels per tooth.

### dbo.ToothSystems
- Candidate primary key: `ToothSystemId`.
- Likely joins: a tooth table or settings table (not yet inspected).
- Notes: coding systems for tooth numbering (FDI, Palmer, etc.).

### dbo.ChartHealingActions
- Candidate primary key: `ID`.
- Likely joins: `Patients.PatientCode`, `TreatmentPlans.TPNumber`, `ApptNeeds` via `AppointmentNeedId`, `Treatments` via `CodeId`.
- Notes: chart healing audit/actions tied to plan or appointment needs.

## Perio / BPE

### dbo.BPE
- Candidate primary key: composite (`PatientCode`, `Date`) or implicit identity (not listed).
- Likely joins: `Patients.PatientCode`.
- Notes: sextant scores per date.

### dbo.BPEFurcation
- Candidate primary key: `pKey` (likely a surrogate) with `BPEID` as foreign key to `BPE` (if `BPEID` is an identity in another table).
- Likely joins: `BPE` via `BPEID` if present there.
- Notes: furcation flags by sextant.

### dbo.PerioProbe
- Candidate primary key: composite (`TransId`, `Tooth`, `ProbingPoint`) or `TransId` as group id.
- Likely joins: `PerioPlaque.TransID` (same transaction), possibly a missing visit table.
- Notes: detailed probing depths and related measures.

### dbo.PerioPlaque
- Candidate primary key: composite (`TransID`, `Tooth`).
- Likely joins: `PerioProbe.TransId` and `Patients` via an unobserved visit table.
- Notes: plaque/bleeding quadrants per tooth.

## Notes

### dbo.PatientNotes
- Candidate primary key: composite (`PatientCode`, `NoteNumber`) or (`PatientCode`, `Date`, `NoteNumber`).
- Likely joins: `Patients.PatientCode`, `FixedNotes.FixedNoteCode`.
- Notes: free-text clinical notes with per-tooth optionality.

### dbo.TreatmentNotes
- Candidate primary key: `NoteID`.
- Likely joins: `Patients.PatientCode`, `TreatmentPlanItems` via `TPNumber` + `TPItem`.
- Notes: notes per plan item.

### dbo.ApptNotes
- Candidate primary key: unclear (no `ApptId` column present); likely joined via a separate mapping table.
- Notes: appointment notes content only.

### dbo.NoteCategories
- Candidate primary key: `CategoryNumber`.
- Likely joins: `FixedNotes.CategoryNumber`.
- Notes: fixed-note categories.

### dbo.FixedNotes
- Candidate primary key: `FixedNoteCode`.
- Likely joins: `PatientNotes.FixedNoteCode`.
- Notes: templated notes with tooth/mouth applicability.

### dbo.TemporaryNotes
- Candidate primary key: `PatientCode` (one current note per patient).
- Likely joins: `Patients.PatientCode`.
- Notes: editable temporary patient note.

### dbo.OldPatientNotes
- Candidate primary key: composite (`PatientCode`, `NoteNumber`, `Date`).
- Likely joins: `Patients.PatientCode`, `FixedNotes.FixedNoteCode`.
- Notes: archived/historical notes.

## Must-join tables for key UI screens

### Treatment plan screen
- `Patients` -> `TreatmentPlans` (PatientCode)
- `TreatmentPlans` -> `TreatmentPlanItems` (PatientCode + TPNumber)
- `TreatmentPlanItems` -> `Treatments` (CodeID -> TreatmentCode)
- `TreatmentPlanItems` -> `SurfaceTreatment` (Surface -> SurfaceNo, CodeID)
- `TreatmentPlanItems` -> `MaterialTreatment` (CodeID, Material -> MaterialCode)
- Optional: `TreatmentPlanItemsICD10Codes` (diagnosis)
- Optional: `TreatmentPlanReviews` (review status)

### Odontogram / charting
- `TreatmentPlanItems` (Tooth, Surface, CodeID) as planned work
- `ToothSurfaces` (ToothId + SurfaceNo) for surface labels
- `ToothSystems` for numbering conventions
- `ChartHealingActions` for chart action history

### Perio / BPE chart
- `BPE` (sextant scores) by `PatientCode` and `Date`
- `BPEFurcation` if `BPEID` can be tied to a BPE entry
- `PerioProbe` and `PerioPlaque` via `TransId`/`TransID` (requires identifying the visit/transaction table)
