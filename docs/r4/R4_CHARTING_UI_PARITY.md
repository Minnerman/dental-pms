# R4 Charting UI Parity Review (Stage 139)

Date: 2026-01-24
Feature flag: NEXT_PUBLIC_FEATURE_CHARTING_VIEWER=1

## Cohort
- 1000000 (perio probes + duplicates case)
- 1011978 (BPE-heavy)
- 1012056 (notes-heavy)

## Artefacts
- tmp/stage139/patient_1000000/
- tmp/stage139/patient_1011978/
- tmp/stage139/patient_1012056/

## Results

### Patient 1000000
- Artefact: tmp/stage139/patient_1000000/
- CSV index lines:
  - perio_probes,transactions.ref_id_join,ok,,20,166,117,49,,,0,0,0,0,,
  - bpe,bpe.patient_code_or_bpe_id,ok,,0,,,,,,0,,,,,
  - bpe_furcations,bpefurcation.bpe_id_join,ok,,0,,,,,,0,,,,,
  - patient_notes,patient_notes.patient_code,ok,,0,,,,,,0,,,,,
  - tooth_surfaces,global_lookup,ok,,20,,,,,,3,,,,,
- UI parity: not verified (manual review required).
- Notes: Postgres counts are 0 for charting entities in index.csv; UI parity cannot be confirmed without PG data.

### Patient 1011978
- Artefact: tmp/stage139/patient_1011978/
- CSV index lines:
  - perio_probes,transactions.ref_id_join,ok,,0,0,0,0,,,0,0,0,0,,
  - bpe,bpe.patient_code_or_bpe_id,ok,,16,,,,2018-01-11T12:37:55+00:00,2025-09-18T11:40:12+00:00,0,,,,,
  - bpe_furcations,bpefurcation.bpe_id_join,ok,,16,,,,,,0,,,,,
  - patient_notes,patient_notes.patient_code,ok,,0,,,,,,0,,,,,
  - tooth_surfaces,global_lookup,ok,,20,,,,,,3,,,,,
- UI parity: not verified (manual review required).
- Notes: Postgres counts are 0 for charting entities in index.csv; UI parity cannot be confirmed without PG data.

### Patient 1012056
- Artefact: tmp/stage139/patient_1012056/
- CSV index lines:
  - perio_probes,transactions.ref_id_join,ok,,0,0,0,0,,,0,0,0,0,,
  - bpe,bpe.patient_code_or_bpe_id,ok,,4,,,,2017-12-13T09:19:41+00:00,2023-11-06T10:16:39+00:00,0,,,,,
  - bpe_furcations,bpefurcation.bpe_id_join,ok,,4,,,,,,0,,,,,
  - patient_notes,patient_notes.patient_code,ok,,20,,,,2013-08-15T09:41:21+00:00,2013-08-15T09:45:29+00:00,0,,,,,
  - tooth_surfaces,global_lookup,ok,,20,,,,,,3,,,,,
- UI parity: not verified (manual review required).
- Notes: Postgres counts are 0 for charting entities in index.csv; UI parity cannot be confirmed without PG data.

## Follow-ups
- Run charting import for this cohort before UI parity review.
- Re-run spotcheck CSVs after import and complete manual UI comparison.

---

# R4 Charting UI Parity Review (Stage 140)

Date: 2026-01-24
Feature flag: NEXT_PUBLIC_FEATURE_CHARTING_VIEWER=1

## Cohort
- 1000000 (perio probes + duplicates case)
- 1011978 (BPE-heavy)
- 1012056 (notes-heavy)

## Artefacts
- tmp/stage140/patient_1000000/ (spotcheck with --limit 5000)
- tmp/stage140/patient_1011978/ (spotcheck with --limit 5000)
- tmp/stage140/patient_1012056/ (spotcheck with --limit 5000)
- tmp/stage140/ui_parity.json (Playwright parity report)

## Results

### Automated UI parity (Playwright)
- 1000000: Perio probes PASS (API=117, UI=117)
- 1011978: BPE entries PASS (API=16, UI=16)
- 1012056: Patient notes PASS (API=37, UI=37)

### CSV index summaries
- 1000000: perio_probes SQL=166, SQL unique=117, PG=117
- 1011978: bpe SQL=16, PG=16
- 1012056: patient_notes SQL=37, PG=37

## Notes
- Stage 139 blocker resolved: charting import seeded this cohort and spotcheck limits raised.
