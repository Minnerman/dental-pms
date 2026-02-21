# Patient UI Acceptance (R4-Like Header + Tabs)

## Purpose
Define a strict, testable acceptance contract for making the patient screen feel as close to R4 as practical for header density, tab model, and navigation ergonomics.

## Current Surface
- Primary route: `/patients/{id}/clinical`
- Component: `frontend/app/(app)/patients/[id]/PatientDetailClient.tsx`
- Shared shell/nav: `frontend/app/(app)/AppShell.tsx`

## Scope
- Stage 160A: evidence pack, representative patient set, screenshot harness, golden-hash guard.
- Stage 160B: patient header + tab parity implementation and keyboard shortcut behavior.

## Patient Header Layout
- Name prominence:
  - Patient full name is the dominant line.
  - Identifier line includes patient ID and provenance metadata.
- Demographics and identifiers:
  - DOB and age are presented in one scan line.
  - Contact primitives (phone/email) are visible without opening sub-panels.
- Alerts:
  - Allergy/medical/safeguarding/financial/access alerts are visible in header zone.
  - Recall status badge is visible at header level.
- Information density:
  - Header groups are compact and scan-friendly, optimized for high-throughput usage.
  - Grouping should mirror R4 style: identity -> risk/alerts -> contact/recall -> quick actions.

## Tabs and Navigation Model
- Primary tab strip should follow R4-oriented clinical workflow ordering.
- Baseline target order for Stage 160B (pending Amir exact order confirmation):
  1. Summary
  2. Clinical
  3. Charting (when feature enabled)
  4. Appointments/Transactions
  5. Treatment Plans/Estimates
  6. Notes
  7. Financial (Invoices/Ledger)
  8. Recalls
  9. Documents/Attachments
  10. Timeline/Audit
- Active state:
  - Strong active tab affordance.
  - Clear distinction between primary tabs and quick links.

## Keyboard Shortcuts
- Stage 160B target:
  - `Ctrl/Cmd + 1..9` maps to primary patient tabs.
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
  - one screenshot per representative patient under `.run/stage160a/`.
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
  - header and tab controls are visible before capture.
  - screenshot artifact emitted per representative patient.
  - golden hash recording/assertion flow.
  - render timing within budget.

## Open Inputs
- Exact R4 tab labels/order should be confirmed by Amir and then locked as strict assertions in Stage 160B.
