# UAT Checklist (Stage 57)

Use this checklist for a focused go-live acceptance pass with representative users.

## Receptionist flow (15-20 mins)

1) Login + logout
- Action: Sign in with receptionist/admin credentials, then log out.
- Expected result: Login succeeds, protected pages load, logout returns to login page.

2) Password reset flow (if enabled)
- Action: Start forgot/reset flow for a valid user.
- Expected result: Reset request is accepted and reset completion allows login with the new password.

3) Patient search + open record
- Action: Search by full and partial patient name; open the selected patient.
- Expected result: Matching results appear quickly; opened patient header/details match selected patient.

4) Create appointment
- Action: Create an appointment with patient, date/time, clinician, and location.
- Expected result: Appointment appears in list/calendar at the selected slot with correct clinician/location.

5) Move appointment in calendar (drag/drop)
- Action: Drag appointment to a different time/day.
- Expected result: Appointment updates to new slot and persists after refresh.

6) Day sheet cut/copy/paste (if enabled)
- Action: Use day sheet cut/copy/paste actions for an appointment.
- Expected result: Appointment is moved/copied correctly and resulting schedule is accurate.

7) Add patient note + verify audit display
- Action: Add a note on a patient record and open note audit view/details.
- Expected result: Note saves successfully; created/updated audit information is visible.

8) Recall worklist + filters
- Action: Open Recalls page and apply filter changes.
- Expected result: Worklist loads and filters update rows/KPIs as expected.

## Clinician flow (15-20 mins)

1) Open patient clinical page
- Action: Open a patient and navigate to Clinical.
- Expected result: Clinical page loads without errors with chart and timeline content.

2) Clinical view mode persistence (Stage 55)
- Action: Toggle clinical view mode, refresh, and reopen same/different patient.
- Expected result: Selected mode persists across refresh/navigation.

3) Treatment plan add/edit
- Action: Add a treatment item, edit it, and save.
- Expected result: Changes persist and display correctly in treatment plan/history views.

4) BPE record and verify (Stage 139)
- Action: Add or view BPE entries for a patient with data.
- Expected result: BPE record is visible and mapped correctly on chart/timeline.

5) BPE furcation verify (Stage 140)
- Action: Add or view BPE furcation entries.
- Expected result: Furcation data appears correctly where expected.

6) Perio probe view for relevant patients (Stage 138)
- Action: Open Perio probe context for patient(s) known to have probe data.
- Expected result: Probe data view exists and renders data without errors.

7) Generate patient letter PDF from template
- Action: Create a patient document from template and download PDF.
- Expected result: Generated PDF downloads successfully with expected merged content.

## Sign-off
- Record date, tester name/role, pass/fail per section, and blockers.
- Any failed step blocks go-live until triaged and accepted.
