# R4 Appointments Discovery (Stage 123)

Safety reminder: R4 SQL Server is STRICTLY READ-ONLY (SELECT-only; read-only creds).

Current tooling note: PR #568 added the SELECT-only appointment cutover
inventory command `python -m app.scripts.r4_appointment_cutover_inventory`.
The live inventory ran successfully on 2026-04-29 with complete R4 SQL Server
environment variables and `R4_SQLSERVER_READONLY=true`. It was SELECT-only,
made no R4 writes, made no PMS DB writes, and changed no tracked repo files.
The status/null-patient/clinician policy is now documented in
`docs/r4/R4_APPOINTMENT_STATUS_POLICY.md`.

## Candidate tables/views

Base tables (by name):
- dbo.Appts
- dbo.WaitingAppts
- dbo.ApptNotes
- dbo.ApptFlags
- dbo.ApptGroups
- dbo.ApptPrefs
- dbo.AppointmentSeries
- dbo.AppointmentNeeds
- dbo.ApptsConfirmation
- dbo.ApptSMSReminderReplies
- dbo.DiaryNotes
- dbo.WT_DNA_Appts

Views (by name):
- dbo.vwAppointmentDetails
- dbo.vwAppointments
- dbo.vApptsInSession
- dbo.vwForwardAppointments
- dbo.vwApptFlags

## Chosen source for importer

Primary candidate: `dbo.vwAppointmentDetails`
- Contains stable `apptid` key, patient/clinician codes, appointment datetime, duration (int), status, cancelled flag, notes, and appointment type.
- Mirrors `dbo.Appts` row count and key uniqueness.

Fallback base table: `dbo.Appts`
- Stable `ApptId` key, appointment datetime, duration (datetime), patient code, clinician `UserCode`, treatment code, notes.
- Lacks friendly status string; would need mapping from `ApptFlag` or other sources.

## Key uniqueness

- `dbo.Appts.ApptId`: total 100812, distinct 100812.
- `dbo.vwAppointmentDetails.apptid`: total 100812, distinct 100812.

The 2026-04-29 live inventory supersedes the earlier Stage 123 count for
cutover planning: current total appointment count is `101051`.

## Date range + linkage

- Date range (both Appts and vwAppointmentDetails):
  - min_start: 2001-10-27 11:15
  - max_start: 2026-11-18 09:00
- Patient code nulls: 1752 / 100812 (~1.7%).

2026-04-29 live inventory update:
- Source: `dbo.vwAppointmentDetails WITH (NOLOCK)`
- Total appointment count: `101051`
- Date range: `2001-10-27T11:15:00` to `2027-02-01T09:00:00`
- Future count on/after `2026-04-29`: `57`
- Past count before `2026-04-29`: `100994`
- Cutover day count: `3`
- Seven days before cutover: `15`
- Seven days after cutover: `15`
- Null/blank patient-code count: `1752`
- Clinician/provider codes: `20`
- Clinic code distribution: `1=101051`
- Evidence path: `/home/amir/dental-pms-appointments-inventory-run/.run/appointment_cutover_inventory_20260429_225200/`

Status evidence from the live inventory:

| R4 status | Count | R4 `apptflag` | Count |
| --- | ---: | ---: | ---: |
| `Complete` | 83836 | 1 | 83836 |
| `Cancelled` | 4193 | 2 | 4193 |
| `Deleted` | 3932 | 5 | 3932 |
| `Did Not Attend` | 3833 | 3 | 3833 |
| `Pending` | 2786 | 6 | 2786 |
| `Left Surgery` | 1158 | 11 | 1158 |
| `Postponed` | 751 | 10 | 751 |
| `Late Cancellation` | 296 | 9 | 296 |
| `In Surgery` | 139 | 8 | 139 |
| `Waiting` | 120 | 7 | 120 |
| `On Standby` | 7 | 4 | 7 |

Cancelled distribution: `0=91872`, `1=9179`. Future samples include
`Cancelled`, `Pending`, and `Deleted` rows. Null-patient samples are historic
`Pending` miscellaneous rows.

## Column mapping (vwAppointmentDetails)

- unique key: `apptid`
- patient_code: `patientcode`
- starts_at: `appointmentDateTimevalue`
- duration_minutes: `duration`
- clinician_code: `providerCode`
- clinician_name: `providerFullname` (optional display only)
- status: `status`
- cancelled: `cancelled`
- clinic_code/location: `cliniccode`
- treatment_code: `treatmentcode`
- appointment_type: `appointmentType`
- notes: `notes`
- flag: `apptflag`

Notes:
- Times appear to be local time values (no timezone offsets). Import should treat them as local clinic time and store with timezone awareness (likely UTC conversion later, or store as naive with clinic timezone handling).
- `duration` is already minutes in the view; base table `Appts.Duration` is a datetime time span.

## Proposed minimal Postgres schema (draft)

- legacy_source (r4)
- legacy_appt_id (int, unique with legacy_source)
- legacy_patient_code (int, nullable)
- starts_at (timestamp tz)
- duration_minutes (int, nullable)
- clinician_code (int, nullable)
- status (text, nullable)
- cancelled (bool, nullable)
- clinic_code (int, nullable)
- treatment_code (int, nullable)
- appointment_type (text, nullable)
- notes (text, nullable)
- appt_flag (int, nullable)

## Proposed import bounds

- Use `--appts-from/--appts-to` to scope on `appointmentDateTimevalue` (or `ApptDateTime` if using base table).
- Start with the same patient code window as transactions for pilot validation.

## Open questions / oddities

- Prove the full `status x cancelled x apptflag` cross-tab before promotion.
- Validate `Left Surgery`, `Waiting`, and `On Standby` semantics with operator review or focused evidence.
- Decide whether R4 clinician codes map to PMS login users, imported `r4_users`, or a separate resource mapping.
- Keep `Deleted` rows read-only/excluded by default unless a later audit projection requires otherwise.
