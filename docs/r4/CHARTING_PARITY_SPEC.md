# CHARTING_PARITY_SPEC

## 1. Purpose and Scope

This specification defines the target behavioural parity Dental PMS should achieve for R4 odontogram/charting.

It defines:

- the target behavioural parity we are trying to achieve with R4 odontogram/charting in Dental PMS
- the current known rules
- the unresolved areas
- the boundaries between source truth, derived display, and future rendering

This specification does not yet provide:

- proprietary internal R4 labels recovered from source code or documented schema metadata
- a full implementation
- a guarantee that every rare historic edge case is already solved

## 2. Evidence Basis

This specification is based on:

- read-only patient screenshot-to-row matching
- live SQL row inspection
- sequencing and reset analysis
- current repo render/extract seam inspection
- accessible metadata and SQL object inspection
- behavioural profiling across live `dbo.Transactions` status values
- existing charting parity hardening and proof work at the read-only tooth-state API seam
- the continuity note in `docs/r4/ODONTOGRAM_TRANSACTIONS_STATUS_CONTINUITY.md`

Evidence status must be treated explicitly:

- `proven`: directly supported by repeatable seam proofs and/or unambiguous evidence
- `strongly inferred`: best-supported by behavioural evidence, but not backed by a recovered proprietary label or explicit vendor documentation
- `unknown`: not yet resolved with enough confidence for implementation to treat as settled

## 3. Non-Conflation Rule

These must not be conflated:

- BPE score `4`
- tooth number `4`
- raw `dbo.Transactions.Status = 4`

## 4. Core Terminology

- `raw chart row`: a row imported or observed from R4 chart-related source data before Dental PMS display resolution is applied
- `completed/history row`: a row representing completed or historical treatment activity rather than current baseline charting state
- `baseline/current row`: a row contributing to current baseline odontogram meaning
- `scaffold row`: a row that establishes tooth presence/background context rather than the main visible restorative semantic state
- `semantic row`: a row that carries chart meaning that can affect the visible odontogram state
- `reset boundary`: a row/event that marks the start of a new authoring epoch for a tooth, so earlier baseline rows should not continue to control current display state
- `family`: the working rendering group a row belongs to, such as filling, crown, post, root canal, missing tooth, or retained root
- `surviving row`: a row still eligible to influence visible display after reset and precedence rules are applied
- `effective row`: the surviving row currently treated as the winner inside a family for visible display purposes
- `derived display state`: the rendered odontogram projection produced from raw/source rows after classification, reset handling, and precedence resolution
- `source truth`: the preserved imported/raw chart records from which display is derived
- `golden case`: a curated high-value patient/tooth case used as a repeatable parity reference
- `parity proof`: a repeatable verification artifact, typically a test or curated case, that confirms a rule or rendering outcome

## 5. Current Known Baseline Model

Current best-supported model:

- `dbo.Transactions.Status` behaves like an internal chart-row role/state field
- current best inferred behavioural labels are:
  - `0` = completed/history treatment transaction row
  - `1` = primary current baseline semantic row
  - `3` = tooth-presence scaffold / initializer row
  - `4` = specialised semantic / reset-adjacent baseline row

These are behavioural labels only. They are not recovered proprietary internal names.

Evidence confidence:

- `Status 0 = completed/history treatment transaction row`: strongly supported
- `Status 1 = primary current baseline semantic row`: strongly supported
- `Status 3 = tooth-presence scaffold / initializer row`: strongly supported
- `Status 4 = specialised semantic / reset-adjacent baseline row`: strongly supported

## 6. Chart Family Model

Current working rendering model is family-based.

Visible odontogram family appears to be driven mainly by:

- `SubType`
- `Surface`
- `Material`
- `Condition`

Working family rules:

- same-family rows compete within a family
- different families may coexist on the same tooth
- status bucket alone does not define a unique icon vocabulary

Current working family examples include:

- filling
- crown
- root canal / root filling
- post
- missing tooth
- retained root
- tooth present
- reset
- other tooth-state families where a stable family grouping is later proven

Current evidence level:

- same-family competition: strongly supported
- cross-family coexistence: strongly supported
- status bucket does not define unique icon vocabulary: strongly supported

## 7. Reset and Survival Rules

Current best interpretation:

- `Reset Tooth` behaves as a reset / re-authoring boundary
- earlier baseline rows before the latest reset boundary should not control the current effective baseline state
- surviving post-reset rows are the strongest candidates for the current display state

Strongly supported:

- `Reset Tooth` frequently precedes later `Tooth Present` and later new semantic rows on the same tooth
- reset handling belongs in selection/survival logic, not in icon-family definition

Still inferred:

- exact proprietary vendor wording for the reset concept
- whether every rare legacy case obeys the same reset semantics without exception

## 8. Current Best Rendering Rule

Best current working rule in plain English:

- render by family first
- after the latest reset boundary
- latest surviving row per family most likely determines visible semantic state
- different families can still render together on the same tooth

Also currently established:

- `Status 4` is visible and semantic
- `Status 4` is not a unique icon bucket
- the same visible family can render without `Status 4` being uniquely responsible

Evidence level:

- family-first rendering: strongly supported
- latest surviving post-reset row per family: strongly inferred and suitable as the current implementation target
- different families can coexist on one tooth: strongly supported

## 9. Separation of Source Truth and Derived Display

Future design rule:

- imported/raw chart rows must be preserved as source truth
- displayed odontogram state must be derived/projection output
- source truth must not be destructively flattened into UI-only state

Why this is required:

- future rule improvements must allow re-projection without losing source provenance
- debugging requires visibility into the rows that produced display state
- migration fidelity depends on preserving what was imported, not just what was drawn

This is a future architectural requirement, not an implementation introduced by this document.

## 10. Parity Proof Model

The intended proof layers are:

- `rule-engine unit tests`
  - purpose: prove isolated classification, reset, survival, and precedence rules
- `golden-case API tests`
  - purpose: prove that the exposed read-only API seam produces the expected effective tooth-state output for curated cases
- `screenshot/shape parity tests`
  - purpose: prove that the visual/output projection remains close to R4 for representative cases

Each rule that becomes implementation-critical should have a clear home in at least one proof layer, and important rules should usually have more than one proof surface.

## 11. Golden Patient Corpus Requirements

A golden case must include:

- patient id
- tooth
- relevant raw rows
- chronology / ordering information
- screenshot or confirmed visual outcome
- expected visible families
- expected effective rows
- confidence level
- notes on uncertainty, if any

The first corpus must cover at minimum:

- simple fillings
- crowns
- root fillings
- posts
- missing tooth
- retained root
- reset sequences
- same-family overlap
- multi-family coexistence
- special surfaces such as `224`
- legacy oddities where available

## 12. Explainability Requirement

The future charting system must support a developer/admin explainability view that can show:

- raw rows
- family assignment
- reset boundary
- discarded rows and why
- surviving rows
- final display state

This is a requirement only. No explainability feature is created by this document.

## 13. Acceptance Criteria

### Data Fidelity

- imported/raw rows are preserved without destructive flattening
- source provenance remains traceable from display state back to raw rows

### Rule Fidelity

- implemented selection/survival behaviour matches the formal parity rules for the covered families and golden cases
- reset handling and same-family precedence are explainable and repeatable

### Visual Fidelity

- rendered output is close enough to R4 that historic chart meaning is preserved for covered cases
- family identity and coexistence are not lost through over-collapse

### Operational Fidelity

- developers and admins can explain why a tooth rendered the way it did
- parity regressions can be caught by repeatable proof layers before broader rollout

## 14. Known Unknowns / Gap Register

- exact proprietary internal labels for statuses `1`, `3`, and `4`
  - status: informational
- inaccessible client/view arbitration details inside proprietary R4 logic
  - status: important but non-blocking
- rare surface encodings and special historic edge cases outside the currently profiled set
  - status: important but non-blocking
- uncertain mixed-family or legacy scenarios not yet represented in a golden corpus
  - status: important but non-blocking
- any rare behaviour that contradicts the current family-first, post-reset survival model
  - status: blocking if found in common/high-impact cases; otherwise important but non-blocking until frequency is understood

## 15. Immediate Next Execution Order

1. Assemble the first golden patient corpus.
2. Expand proof coverage against that corpus.
3. Refine the explicit rule set from the curated cases.
4. Only then define and implement the dedicated charting engine boundary.

## 16. Explicit Architecture Decision

- A dedicated charting/odontogram module or engine boundary is likely justified later.
- It is not created by this docs pass.
- The current next step remains evidence/spec/corpus work, not an architecture-first refactor.
