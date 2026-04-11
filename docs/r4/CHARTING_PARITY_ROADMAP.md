# CHARTING_PARITY_ROADMAP

## Purpose

This roadmap exists to:

- understand R4 charting behaviour comprehensively
- mirror that behaviour closely in Dental PMS
- import historic odontogram data safely
- display imported old odontograms correctly and predictably

## Current Known Baseline

The current evidence-backed baseline is:

- `dbo.Transactions.Status` is best treated as an internal chart-row role/state field, not a user-facing clinical enum
- current best inferred labels are:
  - `0` = completed/history treatment transaction row
  - `1` = primary current baseline semantic row
  - `3` = tooth-presence scaffold / initializer row
  - `4` = specialised semantic / reset-adjacent baseline row
- visible odontogram family appears to be driven mainly by:
  - `SubType`
  - `Surface`
  - `Material`
  - `Condition`
- `Reset Tooth` acts as a reset / re-authoring boundary
- current best rendering model is:
  - latest surviving post-reset row per family likely drives the visible semantic state

These are evidence-backed inferences from read-only investigation and parity work. They are not proprietary internal labels recovered from R4 source code or documented schema metadata.

## Non-Conflation Warning

Do not conflate:

- BPE score `4`
- tooth number `4`
- raw `dbo.Transactions.Status = 4`

## Programme Objective

Build an evidence-backed charting engine and API that reproduces R4 odontogram behaviour closely enough that imported historic charts render correctly in Dental PMS.

## Step-by-Step Roadmap Phases

### Phase 1 — Formal Charting Parity Specification

- Purpose:
  - define terminology, family concepts, reset/survival rules, and the boundary between proven behaviour, inferred behaviour, and open questions
- Deliverables:
  - formal parity specification document set
  - glossary for tooth-state, restorative-family, overlay, reset, survival, and precedence concepts
  - proof status table: `proven`, `inferred`, `unknown`
- Success criteria:
  - no major charting term remains ambiguous inside the project
  - the team can explain current parity behaviour without referring back to ad hoc chat history

### Phase 2 — Golden Patient Corpus

- Purpose:
  - create a curated set of high-value patient/tooth cases that anchor future parity work
- Deliverables:
  - golden corpus inventory with patient/tooth selection criteria
  - per-case bundle: screenshots, raw rows, expected visible result, confidence, and unresolved notes
  - coverage map for key families, overlays, reset cases, and special surfaces
- Success criteria:
  - every important inferred rule is backed by one or more curated cases
  - corpus selection is stable enough to support repeatable parity checks

### Phase 3 — Explicit Rule Recovery

- Purpose:
  - convert observed behaviour into explicit, reviewable rules
- Deliverables:
  - written rule set for:
    - family grouping
    - same-family precedence
    - cross-family coexistence
    - reset handling
    - display mapping
  - confidence level per rule
  - contradiction log where evidence conflicts
- Success criteria:
  - major rendering outcomes can be explained by named rules instead of anecdote
  - unresolved behaviour is isolated into a manageable gap list

### Phase 4 — Internal Charting Engine Boundary

- Purpose:
  - define the future internal boundary only after the evidence base is strong enough
- Deliverables:
  - design note for the future engine responsibilities:
    - raw input normalisation
    - family classification
    - reset/survival resolution
    - rendering-state projection
    - API payload contract
- Success criteria:
  - the boundary is explicit and evidence-driven
  - architecture follows the rules/specification, not the other way around

### Phase 5 — Source Truth vs Derived Display

- Purpose:
  - preserve imported/raw truth separately from derived display state
- Deliverables:
  - data-layer strategy note covering:
    - imported raw chart rows
    - derived display projection
    - re-projection behaviour when rules improve
    - auditability of visible output back to source rows
- Success criteria:
  - historic source truth is never lost or overwritten by display simplification
  - display logic can evolve without corrupting imported provenance

### Phase 6 — Testing Strategy

- Purpose:
  - define the proof structure needed to stop parity drift over time
- Deliverables:
  - testing matrix covering:
    - unit tests for rules
    - golden-case API tests
    - screenshot/shape parity tests
  - explicit seam ownership for each proof type
- Success criteria:
  - every important rule has a clear proof surface
  - regressions can be detected at rule level and at rendered-output level

### Phase 7 — Explainability / Debugging

- Purpose:
  - make rendered outcomes inspectable by developers and admins
- Deliverables:
  - explainability requirements for tooling that shows:
    - which rows survived
    - which rows were reset/superseded
    - which family each row belongs to
    - why a tooth rendered the way it did
- Success criteria:
  - a non-author of the feature can trace a rendered tooth back to the winning/surviving rows

### Phase 8 — Historic Import Rollout

- Purpose:
  - move from proof to safe rollout without flooding the system with unverified historic charts
- Deliverables:
  - staged rollout plan:
    - validation cohort
    - shadow cohort
    - broader rollout
  - rollback/containment rules for parity failures
- Success criteria:
  - rollout scale only increases after parity confidence is demonstrated
  - no bulk historic import proceeds ahead of rule confidence

### Phase 9 — Acceptance Criteria

- Purpose:
  - define what “exact enough” means before broad implementation or rollout
- Deliverables:
  - acceptance checklist covering:
    - data fidelity
    - rule fidelity
    - visual fidelity
    - operational fidelity
- Success criteria:
  - parity can be judged against a documented standard instead of subjective confidence alone

### Phase 10 — Known Gap Register

- Purpose:
  - keep remaining unknowns explicit and manageable
- Deliverables:
  - known-gaps register with:
    - gap description
    - impact
    - likely frequency
    - fallback behaviour
    - blocker/not-blocker status
- Success criteria:
  - no major charting unknown is left implicit
  - architecture and rollout decisions can reference a live gap inventory

## Recommended Next Execution Order

1. Formalise the charting parity specification.
2. Build the first golden patient corpus.
3. Expand proof coverage at the existing read-only seam.
4. Convert recovered behaviour into an explicit rule set.
5. Only then define the dedicated charting engine boundary.

## Explicit Architecture Decision

- A dedicated charting/odontogram module is likely justified later.
- It is not justified yet.
- The current next step is specification, corpus building, and rule recovery rather than an architecture-first refactor.

## Risks / Anti-Patterns To Avoid

- Do not import all historic odontograms before a parity engine exists.
- Do not rely only on screenshots without preserving raw source rows.
- Do not hard-code one-off patient exceptions unless they are documented as temporary.
- Do not mix UI drawing logic with selection/precedence logic.
- Do not build the editor/UI first before read-only historic parity is dependable.

## Relationship To Current Docs

- Continuity note for the completed `dbo.Transactions.Status` investigation:
  - `docs/r4/ODONTOGRAM_TRANSACTIONS_STATUS_CONTINUITY.md`
