# V1 Go-Live Finish Line (Baseline)

This document defines the initial “finish line” for V1 so the system is usable day-to-day in clinic. We can adjust this later, but V1 should be achievable and testable.

## V1 goal
Run a full working day using Dental PMS for:
- appointments scheduling and rescheduling
- patient record access
- clinical notes (basic)
- documents/attachments handling
- billing payments + receipts

## Scope: must-have

### Appointments
- Create / edit / cancel appointments
- Reschedule via drag/resize with clear saving state
- Conflict detection blocks overlapping bookings
- Booking modal UX: patient search focus, required fields validation
- Keyboard shortcuts: N (new), / (search), Esc (close)

### Patients
- Patient detail page is usable and responsive
- Notes entry is reliable (basic notes; no advanced templates required for V1)
- Documents/attachments:
  - upload with in-flight state
  - list updates immediately
  - preview, download, delete
  - show basic metadata (uploaded by/when)

### Billing
- Record payments and show paid/part-paid status correctly
- Disable payment actions while saving or when fully paid
- Reliable receipt download (with in-flight/error states)
- Prevent accidental duplicate payments through UI state/guards

### Audit (basic)
- Created / last updated metadata for key entities
- Minimal audit log entries for key actions (see docs/PERMISSIONS_AND_AUDIT.md)

### Operational / reliability
- Repeatable deploy/run via Docker Compose
- CI green on master (including Playwright smoke)
- Backup approach documented (at minimum: DB backup + uploads storage plan)

## Out of scope (V2+)
- Fine-grained role permissions enforced in UI (the backend capability system can be added in V2; V1 stays full-access)
- Advanced reporting
- Bulk SMS/email automations (beyond what exists)
- Full clinical charting parity with R4

## Definition of done
- A receptionist or clinician can run a real clinic day in PMS for appointments + payments + notes + documents.
- No critical workflows depend on R4 (R4 can remain as read-only historical reference).
