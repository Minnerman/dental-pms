# R4 manual mapping resolution report (2026-01-28)

How to review:
- `rg -n "legacy_patient_code 1016090" docs/r4/R4_MANUAL_MAPPING_RESOLUTION_2026-01-28.md`
- `less +/legacy_patient_code\ 1016090 docs/r4/R4_MANUAL_MAPPING_RESOLUTION_2026-01-28.md`

Summary:
- total codes: 10
- resolved (single confident match or existing mapping): 2
- ambiguous (multiple candidates): 0
- no match: 8

### legacy_patient_code 1012195

R4 details:
- PatientCode: 1012195
- Name: Amir Mostofi
- DOB: 1966-07-27T00:00:00
- Title: Dr
- Mobile: 07909642016
- Appt date range: 2013-05-21T00:00:00 → 2026-11-18T00:00:00

NG candidates (patients table):
| patient_id | legacy_source | legacy_id | name | dob | postcode | phone | email | category | match_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 321 | - | - | Amir Mostofi | 1966-07-27 | - | - | - | clinic_private | surname_dob |

Proposed mapping:
- Proposed: patient_id 321 (confidence: medium; Matched surname + DOB)

### legacy_patient_code 1007995

R4 details:
- PatientCode: 1007995
- Name: Phillip Wood
- DOB: 1965-06-19T00:00:00
- Title: Mr
- Mobile: 07787425586
- Email: philwood1965@hotmail.co.uk
- Appt date range: 2005-02-07T00:00:00 → 2026-01-22T00:00:00

NG candidates (patients table):
| patient_id | legacy_source | legacy_id | name | dob | postcode | phone | email | category | match_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 322 | - | - | Phillip Wood | 1965-06-19 | - | - | - | clinic_private | surname_dob |

Proposed mapping:
- Proposed: patient_id 322 (confidence: medium; Matched surname + DOB)

### legacy_patient_code 1016090

R4 details:
- PatientCode: 1016090
- Name: Elaine Atkinson
- DOB: 1968-04-18T00:00:00
- Title: Mrs
- Mobile: 07713441015
- Appt date range: 2022-10-28T00:00:00 → 2025-11-14T00:00:00

NG candidates (patients table):
_No candidates found._

Proposed mapping:
- UNRESOLVED (No candidate matches)

### legacy_patient_code 1015376

R4 details:
- PatientCode: 1015376
- Name: Rachel Matthews
- DOB: 1993-08-04T00:00:00
- Title: Mrs
- Mobile: 07909854089
- Email: rachelcdmatthews@gmail.com
- Appt date range: 2021-04-08T00:00:00 → 2025-04-07T00:00:00

NG candidates (patients table):
_No candidates found._

Proposed mapping:
- UNRESOLVED (No candidate matches)

### legacy_patient_code 1011407

R4 details:
- PatientCode: 1011407
- Name: William White
- DOB: 1952-12-05T00:00:00
- Title: Mr
- Mobile: 07824352193
- Appt date range: 2011-01-05T00:00:00 → 2026-01-21T00:00:00

NG candidates (patients table):
_No candidates found._

Proposed mapping:
- UNRESOLVED (No candidate matches)

### legacy_patient_code 1012098

R4 details:
- PatientCode: 1012098
- Name: Nicola Scott
- DOB: 1980-07-18T00:00:00
- Title: Mrs
- Mobile: 07939623094
- Appt date range: 2013-04-26T00:00:00 → 2026-07-16T00:00:00

NG candidates (patients table):
_No candidates found._

Proposed mapping:
- UNRESOLVED (No candidate matches)

### legacy_patient_code 1010864

R4 details:
- PatientCode: 1010864
- Name: Scott Debnam
- DOB: 1972-12-30T00:00:00
- Title: Mr
- Mobile: 07830144297
- Email: scottprmscrm@yahoo.com
- Appt date range: 2009-01-14T00:00:00 → 2026-02-09T00:00:00

NG candidates (patients table):
_No candidates found._

Proposed mapping:
- UNRESOLVED (No candidate matches)

### legacy_patient_code 1013684

R4 details:
- PatientCode: 1013684
- Name: Sally Smith
- DOB: 1961-02-21T00:00:00
- Title: Mrs
- Mobile: 07840276140
- Appt date range: 2016-12-30T00:00:00 → 2026-03-09T00:00:00

NG candidates (patients table):
_No candidates found._

Proposed mapping:
- UNRESOLVED (No candidate matches)

### legacy_patient_code 1015469

R4 details:
- PatientCode: 1015469
- Name: Christine Montgomery
- DOB: 1946-09-09T00:00:00
- Title: Mrs
- Mobile: 07948064977
- Email: chrismontgomery21@hotmail.com
- Appt date range: 2021-06-16T00:00:00 → 2025-09-23T00:00:00

NG candidates (patients table):
_No candidates found._

Proposed mapping:
- UNRESOLVED (No candidate matches)

### legacy_patient_code 1012223

R4 details:
- PatientCode: 1012223
- Name: Glynis Vidler
- DOB: 1958-12-07T00:00:00
- Title: Ms
- Mobile: 07791024356
- Email: glynack@hotmail.co.uk
- Appt date range: 2013-06-11T00:00:00 → 2025-12-23T00:00:00

NG candidates (patients table):
_No candidates found._

Proposed mapping:
- UNRESOLVED (No candidate matches)
