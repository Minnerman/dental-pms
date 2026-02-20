# Charting UI acceptance criteria (R4-like odontogram)

This is a top-priority project goal: deliver a highly intelligible, graphical odontogram that matches R4 in layout, tooth geometry, surfaces and symbols.

## 1. Layout and tooth geometry
- Upper and lower arches rendered in an R4-like layout (spacing, ordering, orientation).
- Tooth shapes are recognisable and consistent (incisors/canines/premolars/molars).
- Tooth identifiers and ordering are unambiguous at a glance.

## 2. Surfaces
- Surfaces are represented and interactable in an R4-like way:
  - O/I, M, D, B/L (and any additional surfaces your canonical model supports).
- Surface selection and highlighting are predictable and consistent.
- Restorations can be placed/visualised by surface, not only at tooth-level.

### 2.1 SVG surface model (Stage 154A baseline)
- Odontogram tooth rendering uses explicit SVG surface regions per tooth type.
- Posterior teeth (premolar/molar): `M`, `O`, `D`, `B`, `L`.
- Anterior teeth (incisor/canine): `M`, `I`, `D`, `B`, `L`.
- Each surface region must expose deterministic hooks:
  - `data-surface="<surface>"`
  - `data-testid="tooth-surface-<toothKey>-<surface>"`
- Surface click should set a single selected surface state per active tooth (`data-selected="true"`), and non-selected sibling surfaces remain `false`.

## 3. Symbols and restorative states
The odontogram must render R4-equivalent visual representations for, at minimum:
- Fillings (surface coverage)
- Crowns (full coverage)
- Bridges (abutments + pontic, visually linked)
- Root canal treatment (and status/condition where data supports it)
- Posts
- Implants
- Dentures/partials

### 3.1 Restoration visual vocabulary (Stage 154B v1)
- Contract-first rendering is introduced through `GET /patients/{patient_id}/charting/tooth-state`.
- Initial vocabulary supported by the SVG tooth component:
  - `filling`: surface-only shaded overlays (`M/O/D/B/L/I`)
  - `crown`: full-tooth ring/coverage overlay
  - `bridge`: abutment/pontic connector stub glyph
  - `rct`: root-canal indicator glyph
  - `implant`: implant post glyph
  - `denture`: arch/plate segment glyph
  - `missing` / `extracted`: tooth-level strike markers
- Deterministic test hooks are required for each rendered symbol:
  - `tooth-restoration-<tooth>-<type>`
  - `tooth-restoration-<tooth>-filling-<surface>` for per-surface fillings

## 4. Planned vs completed treatment
- Planned items are visually distinct from completed items.
- Planned/completed items attach to the correct tooth and surface where applicable.

## 5. Drill-down and explainability
- Hover/click provides an intelligible summary: type, date, status, notes.
- Every visual element must be traceable to an underlying canonical record (no “mystery” chart marks).
- Link-explain outputs must align with what the UI renders.

## 6. Evidence-based spotchecks
- Stage 144 pack defines a deterministic set of 20 patients for repeated spotchecks.
- Changes to charting UI should be validated against a subset of these patients and recorded in docs/STATUS.md.
