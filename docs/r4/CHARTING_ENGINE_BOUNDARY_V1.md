# CHARTING_ENGINE_BOUNDARY_V1

## 1. Purpose

This document defines the first implementation-ready internal boundary for the future Dental PMS charting engine, based on the current R4 parity model, selected corpus, recovered rules, hardened rules, and the existing read-only tooth-state seam.

It is a design document only. No runtime code, tests, import rewrites, frontend changes, or charting/odontogram module are created by this pass.

## 2. Why This Boundary Is Now Justified

This step is now appropriate because:

- the continuity note, parity specification, selected corpus, rule recovery, and rule hardening foundation now exist
- the current model is strong enough that implementation should no longer be guesswork
- the next code slice should be a small, deliberate boundary behind the existing read-only seam rather than more ad hoc selection logic

A dedicated internal boundary is now warranted. Implementation is still deferred.

## 3. Proposed Responsibilities of the Engine

The future engine should be responsible for:

- raw row normalisation
  - accept imported/raw chart rows and canonical read-only chart rows in a consistent internal shape
- family classification
  - map rows into working families such as filling, crown, root canal, post, missing tooth, retained root, tooth present, and reset
- reset/survival resolution
  - identify the latest relevant reset boundary and determine which baseline/current rows survive it
- same-family precedence
  - resolve competition within one family without collapsing the whole tooth
- cross-family coexistence
  - preserve multiple surviving families on one tooth when supported by evidence
- derived display projection
  - project effective rows into a stable read-only tooth display state
- explainability/debug projection
  - expose why rows survived, lost precedence, or were suppressed
- stable read-only payload generation
  - produce a dependable API-ready payload for the current tooth-state path

## 4. Out-of-Scope Responsibilities

The engine is not for:

- UI drawing/rendering widgets
- editor workflow or chart-editing UX
- direct SQL import orchestration
- broad import pipeline refactors
- speculative patient-specific exception handling outside the documented rule model
- unrelated charting cleanup or frontend redesign

## 5. Input Contract

The intended engine input should be a read-only internal row set with enough provenance and ordering to apply the parity rules safely.

Minimum design-level input fields:

- patient identifier / legacy patient code
- tooth number
- source provenance
  - source domain
  - source table/view
  - source row id or stable unique key
- ordering fields
  - `recorded_at`
  - raw transaction ordering field where available, such as `RefId`
- semantic fields
  - `SubType` or equivalent label/description
  - `Surface`
  - `Material`
  - `Condition`
  - raw `Status`
- code context where available
  - treatment code id
  - human-readable label/description
- completion/currentness flags where applicable

The first implementation slice should accept the current canonical row shape already used by the existing read-only seam and avoid introducing a second incompatible input model.

## 6. Internal Stages

The engine should process rows in explicit stages:

1. ingest and normalise rows
   - coerce source rows into one internal representation
2. classify rows into families
   - assign each row to a working family or control/scaffold family
3. identify the latest reset boundary
   - per tooth, locate the latest relevant reset marker
4. determine surviving rows
   - suppress pre-reset baseline/current semantic rows where the hardened model supports that
5. resolve same-family precedence
   - within each surviving family, choose the effective row or effective family state
6. preserve cross-family coexistence
   - keep distinct surviving families together on the same tooth
7. project tooth display state
   - produce the read-only display-oriented tooth output
8. expose explainability/debug metadata
   - retain enough structured reasoning to answer why a tooth rendered the way it did

## 7. Output Contract

The intended engine output should be a read-only, API-ready tooth projection rather than a raw row dump.

Minimum design-level output fields:

- tooth identifier
- visible families on that tooth
- per-family display hints
  - mapped surfaces
  - material/condition hints where relevant
- effective rows
  - the rows currently driving the projected display state
- suppressed/discarded rows
  - plus reasons such as:
    - pre-reset superseded
    - lost same-family precedence
    - scaffold/control-only
    - incomplete or not display-driving
- reset boundary info
  - whether a reset boundary was detected and which row established it
- provenance/debug data
  - enough source metadata to explain the projection
- stable read-only payload shape
  - suitable for the existing tooth-state API seam without requiring immediate frontend redesign

## 8. Relationship to Existing Code

The future engine should sit beneath or directly behind the current read-only tooth-state seam in:

- `backend/app/routers/r4_charting.py`

Design intent:

- keep the current `/patients/{id}/charting/tooth-state` API seam
- move row selection, reset handling, family grouping, precedence, and coexistence decisions into the engine gradually
- leave the current frontend contract stable for the first implementation slice
- avoid a broad refactor of import code or unrelated charting routes

The current seam already does part of this work in a compact way:

- it filters canonical rows for the read-only output
- it skips `Reset Tooth` and `Tooth Present` control/scaffold rows
- it classifies rows into restoration types
- it deduplicates projected restorations per tooth

The engine should replace these ad hoc projection decisions gradually with an explicit, explainable rule pipeline.

## 9. Rules Safe to Encode First

Based on the hardened parity model, the first implementation slice is safe to encode these rules:

- treat `Status 3` / `Tooth Present` as scaffold context rather than primary restorative output
- treat `Reset Tooth` as a reset/control boundary signal
- resolve precedence per family rather than per whole tooth
- allow distinct restorative families to coexist on one tooth
- classify at least these families explicitly:
  - filling
  - crown
  - root canal / root filling
  - post
  - missing tooth
  - retained root
  - tooth present
  - reset
- use the latest surviving row within a family in the current read-only seam where the rule is already proven
- preserve completed/history rows as source truth even when they are not yet safely projected into current visible display
- support targeted evidence-backed handling for currently covered special surfaces:
  - `224`
  - `32`
  - `96`

## 10. Rules Not Yet Safe to Encode

These rules or behaviours should stay deferred in the first implementation slice:

- any hard-coded rule that `Status 4` automatically beats `Status 1`
- any blanket rule that every completed-treatment-only restorative row always projects into current visible display
- any blanket rare-surface rule beyond the currently covered `224`, `32`, and `96`
- any rule for non-standard tooth-number rendering
- any assumption that every reset affects all row classes identically across every family and every historic/context row type
- any implementation that depends on unrecovered proprietary internal labels for raw statuses `1`, `3`, and `4`

## 11. Explainability Requirement

The engine must support a developer/admin “why did this tooth render this way?” view.

Minimum explainability data:

- raw rows considered
- family assignment for each row
- detected reset boundary
- discarded/suppressed rows and reasons
- surviving rows after reset/survival handling
- same-family precedence result
- final projected display state

This is a first-class requirement. Explainability should not be added later as an afterthought.

## 12. First Implementation Slice Recommendation

Recommended first code slice:

- implement the engine only for the current read-only tooth-state path
- no editor
- no frontend refactor
- no full import rewrite
- no change to current module/package structure beyond the minimum needed internal boundary
- encode only the strongest rules first
- keep unsupported or still-weak rules explicitly deferred and explainable

This keeps the next implementation small, reviewable, and directly verifiable against the existing selected corpus and merged read-only seam proofs.

## 13. Relationship to Current Docs

- first rule-hardening pass:
  - `docs/r4/CHARTING_RULE_HARDENING_V1.md`
- first explicit rule recovery:
  - `docs/r4/CHARTING_RULE_RECOVERY_V1.md`
- selected corpus V1:
  - `docs/r4/CHARTING_GOLDEN_SELECTED_CASES_V1.md`
- selected corpus V2:
  - `docs/r4/CHARTING_GOLDEN_SELECTED_CASES_V2.md`
- formal parity specification:
  - `docs/r4/CHARTING_PARITY_SPEC.md`
- programme roadmap:
  - `docs/r4/CHARTING_PARITY_ROADMAP.md`
- `dbo.Transactions.Status` continuity note:
  - `docs/r4/ODONTOGRAM_TRANSACTIONS_STATUS_CONTINUITY.md`
