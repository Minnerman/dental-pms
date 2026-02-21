# Patient UI Acceptance (R4-Like Header + Tabs)

## Purpose
Define a strict, testable acceptance contract for making the patient screen feel as close to R4 as practical for header density, tab model, and navigation ergonomics.

## Current Surface
- Primary route: `/patients/{id}/clinical`
- Component: `frontend/app/(app)/patients/[id]/PatientDetailClient.tsx`
- Shared shell/nav: `frontend/app/(app)/AppShell.tsx`

## Scope
- Stage 160A: evidence pack, representative patient set, screenshot harness, golden-hash guard.
- Stage 160B: locked R4 default tab order/labels and keyboard shortcut behavior.
- Stage 161: patient header parity (dense grouping, alerts, quick actions, sticky behavior decision).

## Header Parity (Stage 161)
- Route `/patients/{id}/clinical` must include `data-testid="patient-header"`.
- Required direct child blocks (strict DOM order):
  1. `patient-header-name`
  2. `patient-header-identifiers`
  3. `patient-header-alerts`
  4. `patient-header-actions`
- `patient-header-name`:
  - patient full name is the dominant line.
  - includes patient ID and provenance context.
- `patient-header-identifiers`:
  - must include DOB and age.
  - includes NHS number when present.
  - includes legacy identifier/code when present.
- `patient-header-alerts`:
  - must surface flags for medical, financial, and notes context.
  - must show recall badge/status at header level.
- `patient-header-actions`:
  - must expose quick actions (`Call`, `Email`) when supported by available patient data.
  - includes quick route links without displacing the locked tab model.
- Sticky decision:
  - header remains sticky (`position: sticky`) to preserve high-throughput scanability on long pages.
- Change control:
  - header block IDs/order and required fields must not change unless this acceptance file, Playwright assertions, and golden hashes are updated in the same PR.

## Tabs and Navigation Model
- Locked default order/labels (must match exactly, case-sensitive):
  1. Personal
  2. Medical
  3. Schemes
  4. Appointments
  5. Financial
  6. Comms
  7. Notes
  8. Treatment
- Custom tabs are extension-only and must be appended after `Treatment` under a `Custom` group.
- This locked order must not change unless this acceptance file and Playwright assertions are updated in the same PR.
- Active state:
  - Strong active tab affordance.
  - Clear distinction between primary tabs and quick links.

## Keyboard Shortcuts
- Stage 160B target:
  - `Ctrl/Cmd + 1..8` maps to the locked tab order above.
  - `Esc` closes any transient panel/menu and returns to stable patient view state.
  - Shortcut behavior should not trigger while typing in input/textarea/select fields.

## Evidence and Regression Guard
- Representative patient set:
  - deterministic selection from API metrics:
    - high appointments volume
    - high charting/overlay density
    - alert/note-rich
    - minimal activity
    - edge case with missing data
- Screenshot pack:
  - one screenshot per representative patient (stage-specific output directory allowed via env).
- Golden hash mode:
  - `PATIENT_UI_GOLDEN_MODE=record|assert`
  - `PATIENT_UI_GOLDEN_HASHES=frontend/tests/fixtures/patient-ui-golden-hashes.json`
  - `PATIENT_UI_SCREENSHOT_DIR` override for artifacts.
- Performance guard:
  - lightweight render budget assertion for patient clinical route.
  - configurable via `PATIENT_UI_RENDER_BUDGET_MS`.

## Acceptance Tests (Playwright Required)
- `frontend/tests/patient-ui-parity-pack.spec.ts` must cover:
  - deterministic representative patient set generation and persistence.
  - `/patients/{id}/clinical` loads for each representative patient.
  - header block test IDs exist and remain in strict DOM order.
  - locked tabs exist and remain in strict label order.
  - screenshot artifact emitted per representative patient.
  - golden hash recording/assertion flow.
  - render timing within budget.

## Open Inputs
- None. Any future contract drift requires synchronous updates to this file plus Playwright assertions and golden hashes.
