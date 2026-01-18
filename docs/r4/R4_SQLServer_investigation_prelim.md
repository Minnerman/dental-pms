# R4 / SQL Server investigation notes (preliminary)
Date: 2026-01-18

Scope: technical mapping/integration notes only (no patient-identifiable data).

## Environment
- SQL Server: Microsoft SQL Server 2008 R2 (SP2) build 10.50.4000
- SSMS server shown: DESKTOP-MGOEUGD

## Databases observed (approx sizes)
- sys2000: ~856 MB
- NG_R4_Sys2000: ~582 MB
- Tutor: ~201 MB (not part of core mapping work)

## Legacy database: sys2000
- dbo.Patients rows: 16,948 (key: PatientCode int)
- dbo.Appts rows: 100,795
  - PatientCode NULL: 1,752
  - PatientCode NOT NULL: 99,043
  - Distinct PatientCode in Appts (non-null): 14,706
  - All 14,706 exist in dbo.Patients

## NG database: NG_R4_Sys2000
- dbo.Patient rows: 5,052
  - key columns noted: RecordID (GUID), ChartNumber (nvarchar(20))
  - observation: ChartNumber often blank in sampled rows
- dbo.Person rows: 5,052
  - key columns noted: RecordID (GUID), PMSRecordID (nvarchar(50))
  - observation: PMSRecordID appears to hold legacy numeric IDs (as text) for a subset

## NG appointment-related schema (partial)
- dbo.Appointment key columns noted:
  - RecordID (GUID)
  - PatientID (GUID)
  - ScheduledDate (datetime)
  - EndTime (datetime)
  - OperatoryID (GUID)
  - PMSRecordID (nvarchar(100), nullable)
  - plus status/flags fields (IsConfirmed/IsCompleted/IsSeated/IsCheckedOut etc.)

## Mapping attempted: legacy PatientCode -> NG GUID
Goal: link sys2000.dbo.Appts.PatientCode (int) to an NG GUID (Person.RecordID or related).

Constraint: SQL Server 2008 R2 has no TRY_CONVERT, so numeric filtering is required before CONVERT.

### Mapping table created (in NG_R4_Sys2000)
dbo.PatientCodeToRecordIDMapping
- PatientCode INT PRIMARY KEY
- RecordID UNIQUEIDENTIFIER NOT NULL

Population logic (successful variant)
- Source: NG_R4_Sys2000.dbo.Person
- PatientCode = CONVERT(INT, per.PMSRecordID)
- Filters:
  - per.PMSRecordID IS NOT NULL
  - LTRIM(RTRIM(per.PMSRecordID)) <> ''
  - per.PMSRecordID contains digits only (pattern check)

Result: 5,052 mapping rows inserted.

### Appointment mapping result (sys2000 -> NG)
Considering Appts where PatientCode IS NOT NULL (99,043):
- mapped to NG Person via per.PMSRecordID: 32,199
- not mapped: 66,844

## Interpretation so far
- NG has far fewer people/patients (5,052) than legacy (16,948) => likely partial migration/subset.
- Best linkage candidate currently is Person.PMSRecordID, but it is incomplete across the legacy dataset.
- Patient.ChartNumber is not currently a reliable legacy key (appears often blank in samples).

## Next checks (recommended)
1) Confirm what NG_R4_Sys2000 represents (partial/test/migrated subset?)
2) Search NG for other crosswalk keys ("Legacy", "Import", "External", "CSI", "PatientCode", etc.)
3) Inspect NG dbo.Appointment.PatientID joins (to Patient.RecordID / Person.RecordID) and whether Appointment.PMSRecordID is populated and what it refers to.
4) Confirm Patient vs Person relationship in NG (do RecordIDs align or is there a link table?)
