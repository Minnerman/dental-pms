# Stage 59 Flake Analysis

## Source evidence
- `.run/stage58/uat_playwright.txt`
- `.run/stage58/uat_rerun_metadata_edit.txt`

## Flaky test
- Spec: `frontend/tests/appointments-booking.spec.ts`
- Test: `appointment last updated metadata changes after edit`

## Failure snippet (from Stage 58 full run)
```text
Error: expect(locator).toBeVisible() failed

Locator:  getByTestId('appointment-event-756')
Expected: visible
Received: hidden
Timeout:  15000ms

  553 |   const event = page.getByTestId(`appointment-event-${appointment.id}`);
> 554 |   await expect(event).toBeVisible({ timeout: 15_000 });
```

## Diagnosis
- The failure is **not** a metadata-value mismatch (`updated_at`/`updated_by`); the test failed before edit/save assertions.
- The flaky point was the appointment-selection path to show detail metadata (`appointment-updated-meta`).
- Calendar-event selection timing could leave the test without a selected appointment, so metadata never rendered.

## Deterministic fix implemented
- Reworked the test to use stable day-sheet interaction:
  - open day-sheet view on the target date,
  - locate the patient row by unique generated surname,
  - double-click row to open detail/edit panel, then return to view mode.
- Kept assertion strength: still verifies `appointment-updated-meta[data-iso]` changes after Save.
