# Appointments UI Acceptance (R4-Like Diary/Calendar)

## Purpose
Define a strict, testable acceptance contract for making Dental PMS appointments UI as close to R4 diary behavior as possible.

## Current Surface
- Primary route: `/appointments`
- Component: `frontend/app/(app)/appointments/page.tsx`
- Modes:
  - `Day sheet` (dense list)
  - `Calendar` (day/week/month/agenda via `react-big-calendar`)

## Scope
- Stage 157: evidence, acceptance criteria, snapshot tooling, screenshot harness.
- Stage 158+: UI shell and behavior implementation to close parity gaps.

## Views
- Day:
  - Dense single-day diary with rapid scanning.
  - Stable row order by start time.
  - Fast keyboard and pointer interactions.
- Week:
  - Columnar week layout with clear day/column boundaries.
  - Predictable appointment block stacking for collisions.
- Month (secondary):
  - Keep for navigation context; not primary parity target for Stage 158.

## Layout
- Time scale:
  - 10-minute granularity for day/week.
  - Consistent visible working window and scroll anchor.
- Columns:
  - Must support clinician and chair/room-oriented slicing.
  - Header row must expose active grouping dimension and labels.
- Header rows:
  - Date header + sub-header metadata (filters/grouping state).
- Scroll behavior:
  - Smooth vertical scroll without jitter during re-render.
  - Predictable scroll restore after filter/date/view changes.

## Visual Language
- Color coding:
  - Strong status semantics (booked/arrived/in-progress/completed/cancelled/no-show).
  - Colors remain legible in dense mode.
- Icons/status indicators:
  - Alert flags, notes indicators, domiciliary markers, cancellation semantics.
- Text density:
  - Compact typography and spacing tuned for high-throughput diary usage.
  - Prioritize at-a-glance patient/time/status comprehension.

## Interactions
- Single click:
  - Select appointment without opening full edit.
- Double click:
  - Open appointment details/edit quickly.
- Drag/drop:
  - Move appointment in day/week grid with conflict + schedule guardrails.
- Resize:
  - Adjust duration with schedule/conflict checks.
- Copy/duplicate:
  - Cut/copy/paste behavior with deterministic conflict handling and clear notices.

## Context Menus
- Right-click menu baseline:
  - Open/edit
  - Mark arrived/in-progress/completed
  - Cancel/no-show (with reason)
  - Cut/copy
  - Paste (when clipboard present)
- Unsupported R4 actions should be explicitly listed as out-of-scope until implemented.

## Keyboard Shortcuts
- Navigation:
  - Previous/next day or range
  - Jump to date
- Creation/search:
  - New appointment
  - Patient search focus
- Clipboard:
  - Copy/cut/paste selected appointment
- Escape:
  - Close active modal/context states

## Filtering and Search
- Required filters:
  - Clinician
  - Chair/room
  - Location type (`clinic`/`visit`)
  - Appointment status
  - Appointment type
- Search:
  - Patient quick-find with low-latency response.
- URL-state:
  - Date/view/filter state should be shareable and refresh-stable where practical.

## Printing and Export
- In scope now:
  - Existing run-sheet export for visit workflows.
- Future parity target:
  - R4-like diary print layouts and richer export controls.

## Performance
- Expected behavior:
  - Smooth scroll and drag in busy days.
  - Fast redraw on filter/view toggle.
  - Deterministic loading and error states (no flicker loops).

## Acceptance Tests (Playwright Required)
- Route and mode baseline:
  - `/appointments` loads with authenticated user.
  - Day-sheet and calendar mode toggles are stable.
- View/date stability:
  - Day screenshots for selected representative dates.
  - Week screenshot for selected anchor week.
- Interaction baseline:
  - Single click selects appointment.
  - Double click opens details.
  - Drag/drop and resize enforce schedule/conflict constraints.
- Context and shortcuts:
  - Right-click menu core actions work.
  - Keyboard shortcuts for new/search/copy/cut/paste/escape work.
- Filters:
  - Filter toggles update visible dataset deterministically.
  - URL date/view persistence remains stable after refresh.

## Evidence Artifacts
- Snapshot JSON: `.run/stage157/diary_snapshot_<date>_<view>.json`
- UI screenshots: `.run/stage157/appointments_<view>_<date_or_week>.png`

