# R4 Appointments Discovery (Stage 123)

Safety reminder: R4 SQL Server is STRICTLY READ-ONLY (SELECT-only; read-only creds).

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

## Date range + linkage

- Date range (both Appts and vwAppointmentDetails):
  - min_start: 2001-10-27 11:15
  - max_start: 2026-11-18 09:00
- Patient code nulls: 1752 / 100812 (~1.7%).

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

- Confirm whether `status` is derived from `apptflag` or other fields (view logic).
- Validate meaning of `cancelled` and how it maps to current PMS appointment statuses.
- Decide whether to backfill clinician name from `r4_users` or rely on `providerFullname` from the view.
