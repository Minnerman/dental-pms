# R4 Appointment Status Policy

Status: design policy only. This document does not authorise R4 writes, PMS
database writes, appointment import, or promotion into the core diary.

Baseline: `master@55e46a08450e95da8b4029d9aa3c3616dbfddbd2`

Implementation status: PR #571 added the pure backend helper
`backend/app/services/r4_import/appointment_status_policy.py` and focused unit
tests in `backend/tests/r4_import/test_appointment_status_policy.py`. The helper
is not wired into importer behaviour, and no appointment import, core diary
promotion, PMS DB write, or R4 access occurred in that slice.

Promotion dry-run status: PR #574 added backend-only/report-only no-core-write
promotion dry-run tooling in
`backend/app/services/r4_import/appointment_promotion_dryrun.py` and
`backend/app/scripts/r4_appointment_promotion_dryrun.py`. It does not add core
appointment apply/promotion code.

Promotion plan status: PR #576 added the pure backend promotion plan helper in
`backend/app/services/r4_import/appointment_promotion_plan.py` and focused unit
tests in `backend/tests/r4_import/test_appointment_promotion_plan.py`. The
helper classifies staging rows into eligible promotion candidates, excluded
rows, manual-review rows, null-patient read-only rows, unmapped-patient rows,
and clinician-unresolved rows. It is not wired into importer/apply behaviour,
does not implement timezone conversion or conflict detection, and performs no
DB writes.

Timezone/local-time status: PR #578 added the pure backend helper
`backend/app/services/r4_import/appointment_datetime_policy.py` and focused unit
tests in `backend/tests/r4_import/test_appointment_datetime_policy.py`. It
proves the future convention that naive R4 appointment datetimes are
Europe/London clinic-local wall times, valid local times convert to UTC-aware
datetimes for PMS core storage, and invalid, missing, ambiguous fall-back, or
non-existent spring-forward local times fail closed. The helper is not wired
into importer or promotion behaviour.

Evidence source:
`/home/amir/dental-pms-appointments-inventory-run/.run/appointment_cutover_inventory_20260429_225200/appointment_cutover_inventory.json`

Scratch transcript evidence:
`/home/amir/dental-pms-appointments-scratch-import/.run/appointment_import_idempotency_linkage_dentalpms_appts_scratch_20260430_033056/`

Promotion dry-run evidence:
`/home/amir/dental-pms-appointment-promotion-dryrun/.run/appointment_promotion_dryrun_dentalpms_appt_promo_dryrun_20260430_0835/`

The inventory command queried `dbo.vwAppointmentDetails WITH (NOLOCK)` under
`R4_SQLSERVER_READONLY=true`. It was SELECT-only, made no R4 writes, made no PMS
database writes, and changed no tracked repo files.

The scratch transcript queried R4 under `R4_SQLSERVER_READONLY=true` and wrote
only to scratch DB `dental_pms_appointments_scratch`. It imported raw R4
appointments into `r4_appointments` only; core `appointments` stayed at `0`.

The promotion dry-run used scratch DB
`dental_pms_appointment_promotion_scratch`. R4 access was SELECT-only, no R4
writes occurred, PMS writes were scratch-only, no core appointment writes
occurred, and core `appointments` stayed unchanged with `before=0` and
`after=0`.

## Inventory Evidence

- Total appointments: `101051`
- Date range: `2001-10-27T11:15:00` to `2027-02-01T09:00:00`
- Cutover date used by the report: `2026-04-29`
- Future appointments on or after cutover date: `57`
- Past appointments before cutover date: `100994`
- Null/blank patient-code rows: `1752`
- Clinician/provider codes: `20`
- Clinic codes: one value, `1=101051`
- Cutover boundary counts: `3` on cutover day, `15` seven days before,
  and `15` seven days after

Status, cancellation, and flag distributions:

| R4 status | Count | R4 `apptflag` | Policy class |
| --- | ---: | ---: | --- |
| `Complete` | 83836 | 1 | Terminal completed |
| `Cancelled` | 4193 | 2 | Terminal cancelled |
| `Deleted` | 3932 | 5 | Excluded from core diary promotion by default |
| `Did Not Attend` | 3833 | 3 | Terminal no-show |
| `Pending` | 2786 | 6 | Active booked candidate |
| `Left Surgery` | 1158 | 11 | Terminal completed candidate |
| `Postponed` | 751 | 10 | Inactive cancelled/postponed candidate |
| `Late Cancellation` | 296 | 9 | Terminal cancelled |
| `In Surgery` | 139 | 8 | In-progress candidate only for current/live rows |
| `Waiting` | 120 | 7 | Active booked/waiting candidate |
| `On Standby` | 7 | 4 | Active standby candidate; no core equivalent yet |

This table reflects matching marginal distribution counts from the inventory,
not a proven full cross-tab. The next backend proof still needs to confirm the
complete `status x cancelled x apptflag` combinations before promotion.

## Current PMS Constraints

- The read-only R4 appointment table preserves raw `status`, `cancelled`,
  `appt_flag`, `patient_code`, `clinician_code`, and `clinic_code`.
- Core PMS appointments currently support only:
  `booked`, `arrived`, `in_progress`, `completed`, `cancelled`, and `no_show`.
- Core conflict detection excludes `cancelled` and `no_show`, but not `completed`
  or `in_progress`.
- The R4 calendar already treats R4 appointments as read-only source rows,
  hides non-active statuses by default, and hides unlinked rows unless requested.

## Scratch Import Evidence

The 2026-04-30 isolated scratch transcript completed the raw appointment
staging proof without starting core diary promotion:

- Appointment dry-run exited `0`.
- Scratch patient import created `17010` patients and `17010`
  `r4_patient_mappings`.
- Scratch appointment import created `101051`, updated `0`, skipped `0`, and
  preserved `1752` null-patient rows.
- Idempotency rerun created `0`, updated `0`, and skipped `101051`.
- Linkage report showed `appointments_total=101051`,
  `appointments_imported=101051`, `appointments_not_imported=0`,
  `mapped=99299`, `unmapped=1752`, and `actionable_unmapped=0`.
- Final scratch counts were `patients=17010`, `r4_patient_mappings=17010`,
  `r4_appointments=101051`, and core `appointments=0`.
- R4 access was SELECT-only; no R4 writes occurred; PMS writes were
  scratch-only. The evidence artefacts remain preserved; the scratch import
  stack was cleaned up after the evidence was recorded.

## No-Core-Write Promotion Dry-Run Evidence

The 2026-04-30 scratch promotion dry-run/report completed without creating,
updating, or deleting core diary rows:

- Report considered `101051` imported `r4_appointments` rows.
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
- R4 access was SELECT-only; no R4 writes occurred; PMS writes were
  scratch-only; no core appointment writes occurred.

## Mapping Policy

Do not promote raw R4 appointment rows directly into core `appointments`. Any
promotion must go through an explicit mapping function with tests that preserve
the raw R4 fields for audit and reconciliation.

Mapping precedence:

1. If `patientcode` is null or blank, keep the row in the read-only R4
   appointment workflow only. Do not promote it into core `appointments`.
2. If the normalized status is `Deleted` or `apptflag=5`, exclude the row from
   core diary promotion by default. Preserve it in `r4_appointments` for audit.
3. If `cancelled=true`, or the normalized status is `Cancelled` or
   `Late Cancellation`, or `apptflag` is `2` or `9`, map to core `cancelled`
   only if promotion is explicitly enabled.
4. If the normalized status is `Did Not Attend` or `apptflag=3`, map to core
   `no_show` only if promotion is explicitly enabled.
5. If the normalized status is `Complete` or `apptflag=1`, map to core
   `completed` only if promotion is explicitly enabled.
6. If the normalized status is `Left Surgery` or `apptflag=11`, treat it as a
   completed candidate. It needs a focused confirmation test before core
   promotion because it is not identical to `Complete`.
7. If the normalized status is `Postponed` or `apptflag=10`, treat it as
   inactive. If promoted, use core `cancelled` with raw status/cancel reason
   retained; do not make it an active booking.
8. If the normalized status is `Pending` or `apptflag=6`, it is the default
   active-booking candidate and may map to core `booked` after linkage,
   clinician, timezone, and conflict proofs pass.
9. If the normalized status is `Waiting` or `apptflag=7`, it is an active
   waiting candidate. It may map to core `booked` only with raw status retained
   and explicit operator acceptance.
10. If the normalized status is `On Standby` or `apptflag=4`, keep it read-only
    until a standby policy exists. Core PMS has no standby state.
11. If the normalized status is `In Surgery` or `apptflag=8`, only same-day or
    live cutover rows can map to core `in_progress`. Historic rows must not be
    left as active `in_progress` without an explicit terminal-state review.
12. Any status/flag combination outside the inventory set must fail closed:
    preserve the row in `r4_appointments`, report it, and do not promote it.

Future rows use the same policy. The inventory includes future `Cancelled`,
`Pending`, and `Deleted` examples; only future `Pending` rows are active-booking
candidates. Future `Cancelled` rows are inactive, and future `Deleted` rows stay
excluded from core diary promotion by default.

## Null/Blank Patient-Code Policy

The inventory found `1752` null/blank patient-code rows. Samples are historic
`Pending` miscellaneous rows.

- Keep these rows in `r4_appointments` for audit and read-only review.
- Hide them from default R4 calendar views unless `show_unlinked` or an admin
  linkage queue explicitly requests them.
- Do not promote them to core `appointments`.
- Allow manual linkage only through the existing R4 appointment patient-link
  workflow, with operator review.
- Before any core diary promotion, prove the count of excluded null-patient rows
  and require the promotion report to show zero null-patient core inserts.

## Clinician And Clinic Policy

The inventory found `20` clinician/provider codes and a single clinic code
`1=101051`.

- Resolve R4 clinician display through imported `r4_users` where available.
- Preserve `clinician_code` on every imported R4 row.
- Do not map R4 clinician codes to PMS login users without a dedicated
  clinician identity mapping policy.
- If a clinician code is missing from `r4_users`, display the raw code and
  include it in the reconciliation report.
- Treat `cliniccode=1` as the source clinic/site code only. Do not infer rooms,
  chairs, or multi-site scheduling semantics from it.
- Any future core promotion should use a neutral clinic location label until
  room/chair mapping is explicitly proven.

## Required Proof Before Core Diary Promotion

Before R4 appointments can be promoted into the core diary, prove:

1. A SELECT-only cross-tab of `status x cancelled x apptflag` for the full source
   set, including the `57` future rows.
2. A pure backend status-mapping function with fixtures for all 11 observed
   status/flag values and fail-closed coverage for unknown combinations
   (complete as of PR #571).
3. An isolated scratch import/idempotency/linkage transcript into
   `r4_appointments`, not core `appointments` (complete as of the 2026-04-30
   scratch transcript).
4. A promotion dry-run report showing how many rows would be excluded, mapped to
   inactive states, mapped to active bookings, and left for manual review
   (complete as of PR #574).
5. A deterministic promotion plan helper that produces row-level actions,
   aggregate counts, and reason samples without DB writes or importer/apply
   wiring (complete as of PR #576).
6. A timezone/local-time proof for Europe/London clinic-local wall times,
   UTC-aware core storage, and fail-closed daylight-saving edge cases
   (complete as of PR #578).
7. Patient linkage thresholds, including explicit handling for the `1752`
   null/blank patient-code rows.
8. Clinician-code coverage against imported R4 users and any proposed PMS user
   mapping.
9. Conflict predicate behaviour for future rows before any live future-diary
   cutover.

## Open Questions

- Whether `Left Surgery` should always be terminal `completed` or needs a more
  specific source-state label.
- Whether `Waiting` and `On Standby` should ever create active core diary
  entries, or remain read-only R4 calendar states.
- Whether `Deleted` should stay purely excluded or appear in an audit-only core
  projection later.
- Whether clinician codes map to current PMS users, historic R4 users only, or a
  separate resource table.
- Whether future rows need recall-linked booking reconstruction before active
  core promotion.

## Recommended Next Slice

The PR #571 backend helper/proof, the 2026-04-30 isolated scratch
`r4_appointments` import/idempotency/linkage transcript, PR #574's no-core-write
appointment promotion dry-run/report, PR #576's pure promotion plan
helper/proof, and PR #578's timezone/local-time proof are complete. The next
safe slice is conflict predicate extraction before any real core diary
promotion.

Keep the next slice proof-only:

- extract the pure overlap/conflict predicate future guarded apply code must
  use;
- cover active/inactive statuses, adjacent boundaries, clinician presence, and
  timezone-aware appointment inputs;
- do not wire importer/apply behaviour;
- leave guarded apply design for later slices;
- keep R4 strictly SELECT-only;
- keep real core diary promotion out of scope until conflict proofs are
  reviewed.
