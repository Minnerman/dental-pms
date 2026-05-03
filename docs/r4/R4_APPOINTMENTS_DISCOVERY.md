# R4 Appointments Discovery (Stage 123)

Safety reminder: R4 SQL Server is STRICTLY READ-ONLY (SELECT-only; read-only creds).

Current tooling note: PR #568 added the SELECT-only appointment cutover
inventory command `python -m app.scripts.r4_appointment_cutover_inventory`.
The live inventory ran successfully on 2026-04-29 with complete R4 SQL Server
environment variables and `R4_SQLSERVER_READONLY=true`. It was SELECT-only,
made no R4 writes, made no PMS DB writes, and changed no tracked repo files.
The status/null-patient/clinician policy is now documented in
`docs/r4/R4_APPOINTMENT_STATUS_POLICY.md`. PR #571 added the pure backend helper
and unit tests for that policy without wiring importer behaviour or starting any
appointment import/core diary promotion. PR #574 added backend-only/report-only
no-core-write promotion dry-run tooling and completed the scratch promotion
report without adding core appointment apply/promotion code. PR #576 added the
pure backend appointment promotion plan helper/proof without DB writes or
importer/apply wiring. PR #578 added the pure backend appointment
timezone/local-time proof without importer/promotion wiring, conflict predicate
extraction, DB writes, R4 access, or core appointment apply/promotion code. PR
#580 added the pure backend conflict predicate proof without changing route
behaviour, wiring promotion/import/apply behaviour, touching R4, or writing to
the PMS DB. PR #582 added the backend-only guarded core-promotion apply-plan
prototype without DB writes, CLI/runtime wiring, route/importer changes, R4
access, or real core diary promotion.

2026-04-30 scratch update: isolated scratch `r4_appointments`
import/idempotency/linkage completed under scratch Compose project
`dentalpms_appts_scratch_20260430_033056` and scratch DB
`dental_pms_appointments_scratch`. R4 access was SELECT-only, no R4 writes
occurred, PMS writes were scratch-only, and core `appointments` remained `0`.
Evidence path:
`/home/amir/dental-pms-appointments-scratch-import/.run/appointment_import_idempotency_linkage_dentalpms_appts_scratch_20260430_033056/`.

2026-04-30 promotion dry-run update: no-core-write appointment promotion
dry-run/report completed under scratch Compose project
`dentalpms_appt_promo_dryrun_20260430_0835` and scratch DB
`dental_pms_appointment_promotion_scratch`. R4 access was SELECT-only, no R4
writes occurred, PMS writes were scratch-only, no core appointment writes
occurred, and core `appointments` remained unchanged with `before=0` and
`after=0`. Evidence path:
`/home/amir/dental-pms-appointment-promotion-dryrun/.run/appointment_promotion_dryrun_dentalpms_appt_promo_dryrun_20260430_0835/`.

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

2026-04-30 scratch import/idempotency/linkage update:
- Appointment dry-run exited `0`.
- Scratch patient import created `17010` patients and `17010`
  `r4_patient_mappings`.
- Scratch appointment import into `r4_appointments` created `101051`, updated
  `0`, skipped `0`, and preserved `1752` null-patient rows.
- Idempotency rerun created `0`, updated `0`, and skipped `101051`.
- Linkage report: `appointments_total=101051`, `appointments_imported=101051`,
  `appointments_not_imported=0`, `mapped=99299`, `unmapped=1752`,
  `actionable_unmapped=0`.
- Final scratch counts: `patients=17010`, `r4_patient_mappings=17010`,
  `r4_appointments=101051`, core `appointments=0`.
- Superseded by the 2026-04-30 promotion dry-run/report recorded below.

2026-04-30 no-core-write promotion dry-run update:
- The report considered `101051` imported `r4_appointments` rows.
- Status-policy promote candidates: `94156`.
- Patient-linked promote candidates: `94156`.
- Clinician-resolved promote candidates: `94156`.
- Category counts: completed `83836`, cancelled `5247`, no_show `3833`,
  booked `1240` (`47` future, `1193` past), deleted excluded `3726`,
  manual-review `1417`, null-patient read-only `1752`.
- Risk counts: null patient-code rows `1752`, patient_unmapped `0`,
  clinician_unresolved `0`, distinct clinician codes `20`, clinic code
  `1=101051`.
- Core appointments were unchanged with `before=0` and `after=0`.
- PR #576 then added the pure promotion plan helper/proof so these rows can be
  classified into eligible candidates, excluded rows, manual-review rows,
  null-patient read-only rows, unmapped-patient rows, and clinician-unresolved
  rows without DB writes.
- PR #578 then added the pure timezone/local-time proof: naive R4 appointment
  datetimes are interpreted as Europe/London clinic-local wall times, valid
  local times convert to UTC-aware datetimes for future PMS core storage, and
  invalid, missing, ambiguous fall-back, or non-existent spring-forward times
  fail closed. Importer and promotion behaviour remain unchanged.
- PR #580 then added the pure conflict predicate proof: blocking existing
  statuses are `booked`, `arrived`, `in_progress`, and `completed`;
  `cancelled`, `no_show`, and soft-deleted existing appointments do not block;
  exact same and partial overlaps conflict; back-to-back intervals do not
  conflict; same `clinician_user_id` is required; patient identity is
  irrelevant; aware datetimes compare by instant; and invalid/missing
  datetimes or missing/unknown existing statuses fail closed. Route behaviour
  and promotion/import/apply behaviour remain unchanged.
- PR #582 then added the backend-only guarded apply-plan prototype: it requires
  a scratch/test DB URL, explicit `SCRATCH_APPLY` confirmation, prior
  no-core-write dry-run report validation, zero unmapped promote candidates,
  optional zero unresolved clinicians, datetime/conflict refusal, row-level
  refusal for non-promotable rows, and idempotency skip by legacy ID. It does
  not write to a DB or change routes/importers/runtime.
- The next appointment slice should be scratch-only CLI/runbook wiring and a
  transcript that writes core appointments only inside an isolated scratch DB
  before any real core diary promotion.

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
- Times appear to be local time values (no timezone offsets). PR #578 proves
  the future promotion convention: treat naive R4 appointment datetimes as
  Europe/London clinic-local wall times and convert valid values to UTC-aware
  datetimes for PMS core storage. Ambiguous, non-existent, invalid, or missing
  values fail closed. The importer still uses existing behaviour until a later
  deliberate wiring slice.
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

- Wire and execute guarded core-promotion apply in scratch only before any real
  core diary promotion, including clinician/user mapping policy,
  scratch-first/default-DB refusal, use of the PR #578 timezone/local-time
  convention, use of the PR #580 conflict predicate, and use of the PR #582
  guarded apply-plan prototype.
- Validate `Left Surgery`, `Waiting`, and `On Standby` semantics with operator review or focused evidence.
- Decide whether R4 clinician codes map to PMS login users, imported `r4_users`, or a separate resource mapping.
- Keep `Deleted` rows read-only/excluded by default unless a later audit projection requires otherwise.
