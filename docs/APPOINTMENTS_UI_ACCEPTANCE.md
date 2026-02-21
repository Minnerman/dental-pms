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
  - Stage 158D baseline:
    - now-line stays visible in day/week time grid.
    - explicit `Jump to now` control scrolls diary to current time anchor.

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
  - Stage 158C baseline:
    - drag to a new time in the same lane.
    - drag to a new lane (chair/clinician resource column) at the target time.
    - direct manipulation (no confirmation modal in normal flow).
- Resize:
  - Adjust duration with schedule/conflict checks.
  - Stage 158C baseline:
    - bottom-edge resize with 10-minute snap increments.
    - optimistic update with rollback on failure.
- Copy/duplicate:
  - Cut/copy/paste behavior with deterministic conflict handling and clear notices.

## Context Menus
- Right-click menu baseline:
  - Open/edit
  - Mark arrived/in-progress/completed
  - Cancel/no-show (with reason)
  - Cut/copy
  - Paste (when clipboard present)
- Stage 158D baseline:
  - Implemented context actions in day/week diary cards:
    - `Open`
    - `Mark arrived`
    - `Mark seated` (`in_progress`)
    - `Mark completed`
    - `Did not attend` (`no_show`)
    - `Cancel…`
    - `Move` (cut mode)
    - `Copy`
    - `Add note` (opens detail/edit panel)
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
- Stage 158B baseline key map:
  - `Esc`: close context menu and clear selected appointment in diary shell.
  - `Enter`: open selected appointment details.
  - `ArrowUp`/`ArrowDown`: move appointment selection by order in current diary shell.
  - `ArrowLeft`/`ArrowRight`: move appointment selection across current diary order/lane scaffold.
  - `PageUp` / `PageDown`: previous day / next day.
  - `T`: jump diary to today.
- Stage 158D baseline key map:
  - `Ctrl/Cmd + Left`: previous day.
  - `Ctrl/Cmd + Right`: next day.
  - `Ctrl/Cmd + F`: focus diary patient-search input (scoped diary quick-find).
  - `N`: open new appointment modal.
  - `Esc`: close menu/panel/modal focus states and clear diary selection.
- Stage 158C scheduling constraints:
  - Disallow overlap within the same active lane (chair/clinician grouping context).
  - Show explicit feedback when blocked and keep original appointment slot.

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
  - Drag/drop moves appointment by time and lane.
  - Resize adjusts appointment duration in 10-minute increments.
  - Overlap attempt in same lane is blocked with visible feedback.
- Stage 159 hardening:
  - Sampled appointment start-time positioning in UI aligns with snapshot start times.
  - Status visual mapping (booked/arrived/completed at minimum) is asserted.
  - Drag/resize results are validated against `GET /appointments/snapshot`.
- Context and shortcuts:
  - Right-click menu core actions work.
  - Keyboard shortcuts for new/search/copy/cut/paste/escape work.
- Screenshot drift control:
  - parity screenshot harness supports golden-hash recording and assertion modes:
    - `APPOINTMENTS_DIARY_GOLDEN_MODE=record`
    - `APPOINTMENTS_DIARY_GOLDEN_MODE=assert`
- Filters:
  - Filter toggles update visible dataset deterministically.
  - URL date/view persistence remains stable after refresh.

## Evidence Artifacts
- Snapshot JSON: `.run/stage157/diary_snapshot_<date>_<view>.json`
- UI screenshots: `.run/stage157/appointments_<view>_<date_or_week>.png`
