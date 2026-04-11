# CHARTING_GOLDEN_SELECTED_CASES_V1

## 1. Purpose

This document records the first selected golden cases for charting parity work and provides a reusable per-case evidence template for future corpus expansion.

It is the first operational corpus artefact derived from the Phase 2 planning work. It does not introduce runtime logic or a charting/odontogram module.

## 2. Standard Per-Case Template

Future selected cases should record at least:

- patient id
- tooth
- case status
- confidence
- categories covered
- why this case matters
- relevant raw row summary
- chronology / ordering summary
- current best expected visible family/families
- current best expected effective row(s)
- screenshot / observed R4 outcome reference
- known uncertainty / ambiguity
- follow-up need, if any

## 3. Selection Criteria for V1

The first selected set was chosen because these cases are already investigated, carry high information value, cover core categories, and provide both cleaner controls and more ambiguous edge/mixed cases.

Selection intent for V1:

- reuse the strongest already-reviewed evidence rather than starting a new discovery pass
- cover the most important family, reset, scaffold, and tooth-state behaviours first
- keep both clean controls and one controlled ambiguous reset case in view
- preserve the current investigation conclusions without overclaiming certainty

## 4. V1 Selected Cases

### `1006366`

- patient id: `1006366`
- tooth: `16`
- case status: `selected`
- confidence: `high`
- categories covered:
  - root filling / root canal
  - special surface `224`
  - multi-family coexistence
  - completed-treatment-derived restorative family reference
- why this case matters:
  - cleanest reviewed case showing coronal restorative behaviour and a root/endodontic family coexisting on the same tooth
- relevant raw row summary:
  - same tooth carries a coronal filling-family row and a `Root Filling` row on surface `224`
- chronology / ordering summary:
  - later baseline rows establish the visible coronal and root/endodontic state without a reset boundary
- current best expected visible family/families:
  - filling
  - root canal / root filling
- current best expected effective row(s):
  - coronal filling-family row remains effective for the coronal component
  - root-filling/root-canal row remains effective for the root component
- screenshot / observed R4 outcome reference:
  - reviewed baseline screenshot for patient `1006366`
- known uncertainty / ambiguity:
  - exact proprietary surface semantics for `224` remain undocumented
- follow-up need, if any:
  - add more special-surface controls besides `224`

### `1011746`

- patient id: `1011746`
- tooth: `14`
- case status: `selected`
- confidence: `high`
- categories covered:
  - simple fillings
  - same-family overlap
  - same-family precedence / overlay interpretation
- why this case matters:
  - strongest current same-family filling case with clean row chronology and clear visible restorative-family behaviour
- relevant raw row summary:
  - same tooth carries `Status 1 Fillings` and later `Status 4 Fillings` in the same broad restorative family
- chronology / ordering summary:
  - later same-family row is the strongest current candidate for the visible semantic state
- current best expected visible family/families:
  - filling
- current best expected effective row(s):
  - the later surviving filling-family semantic row is the current best expected effective row
- screenshot / observed R4 outcome reference:
  - reviewed baseline screenshot for patient `1011746`
- known uncertainty / ambiguity:
  - exact proprietary client arbitration between same-family `Status 1` and `Status 4` remains inferred rather than directly documented
- follow-up need, if any:
  - add more low-ambiguity same-family restorative controls

### `1012070`

- patient id: `1012070`
- tooth: `16`
- case status: `selected`
- confidence: `medium`
- categories covered:
  - `Reset Tooth` sequence
  - same-family overlap
  - mixed-family coexistence
  - legacy ambiguity
- why this case matters:
  - best current reset-heavy case for survival logic, even though the final visible outcome remains less clean than the simpler controls
- relevant raw row summary:
  - pre-reset semantic rows exist on the tooth, followed by `Reset Tooth`, then later `Tooth Present` and later semantic rows
- chronology / ordering summary:
  - post-reset rows are the strongest current candidates for effective state; pre-reset rows should not control the current baseline interpretation
- current best expected visible family/families:
  - post-reset filling-family behaviour on the tooth
  - possible coexistence with additional legacy family context
- current best expected effective row(s):
  - latest surviving post-reset semantic row(s) are the best current candidates
- screenshot / observed R4 outcome reference:
  - reviewed baseline screenshot for patient `1012070`
- known uncertainty / ambiguity:
  - final mixed visual composition remains more ambiguous than the cleaner control cases
- follow-up need, if any:
  - find a simpler reset-before/after case with less family clutter

### `1012191`

- patient id: `1012191`
- tooth: `5`, `14`, `23`, `36`
- case status: `selected`
- confidence: `high`
- categories covered:
  - missing tooth
  - retained root
  - direct tooth-state families
  - visible semantic behaviour without same-tooth restorative base rows
- why this case matters:
  - strongest tooth-state-heavy case where missing/root state meaning is carried directly rather than through a same-tooth restorative base family
- relevant raw row summary:
  - relevant teeth carry `Missing Tooth` and `Retained Root`-style rows, with `Tooth Present` scaffold context where applicable
- chronology / ordering summary:
  - tooth-state rows remain the best current candidates for effective visible tooth-state meaning
- current best expected visible family/families:
  - missing tooth
  - retained root
- current best expected effective row(s):
  - direct tooth-state semantic rows for the affected teeth
- screenshot / observed R4 outcome reference:
  - reviewed baseline screenshot for patient `1012191`
- known uncertainty / ambiguity:
  - exact legacy variation between missing-tooth and retained-root rendering remains worth broadening with more controls
- follow-up need, if any:
  - add a cleaner retained-root control distinct from mixed missing-tooth examples

### `1017001`

- patient id: `1017001`
- tooth: `4`, `7`, `8`, `11-16`, lower restorative control teeth
- case status: `selected`
- confidence: `high`
- categories covered:
  - crowns
  - root fillings / root canal
  - posts
  - special surface `224`
  - simple fillings
  - `Tooth Present` scaffold controls
  - completed-treatment-derived restorative family references
- why this case matters:
  - highest-coverage reviewed patient so far; supplies the best current control pool for simple restorative families and several multi-family restorative combinations
- relevant raw row summary:
  - multiple teeth provide crown, root-filling, post, filling, and scaffold examples, including a special-surface `224` root-filling control
- chronology / ordering summary:
  - provides control/reference rows rather than one single decisive chronology story; valuable as a control patient across multiple family categories
- current best expected visible family/families:
  - crown
  - root canal / root filling
  - post
  - filling
  - tooth present scaffold context where applicable
- current best expected effective row(s):
  - effective row depends on the specific tooth/family under review; current evidence supports using this patient as a control/reference pool rather than a single-rule proof case
- screenshot / observed R4 outcome reference:
  - reviewed baseline/control screenshots and prior seam-hardening references for patient `1017001`
- known uncertainty / ambiguity:
  - not every tooth in this patient is equally low-ambiguity, so case use should stay tooth-specific
- follow-up need, if any:
  - promote the cleanest subcases into separate per-tooth confirmed references

## 5. Coverage Map

These first selected cases already cover well:

- same-family precedence:
  - `1011746`
- multi-family coexistence:
  - `1006366`
  - `1012070`
  - parts of `1017001`
- reset boundary behaviour:
  - `1012070`
- missing tooth / retained root:
  - `1012191`
- special surface `224`:
  - `1006366`
  - `1017001`
- root filling / root canal:
  - `1006366`
  - `1017001`
- scaffold / `Tooth Present` behaviour:
  - `1012070`
  - `1012191`
  - `1017001`
- completed-treatment-derived restorative family references:
  - `1006366`
  - `1017001`

## 6. Remaining Gaps After V1

Biggest remaining gaps:

- cleaner `post + crown + root-canal` coexistence on one tooth with lower ambiguity
- simpler reset before/after pairs without major mixed-family noise
- more special-surface cases beyond `224`
- lower-ambiguity completed-treatment-only crown controls
- broader retained-root coverage separate from mixed missing-tooth cases
- rare legacy oddities that can test the limits of the current family-first/post-reset model

## 7. Immediate Next Execution Order

1. Use V1 selected cases as the first stable reference set.
2. Fill the biggest remaining coverage gaps.
3. Turn selected cases into stronger API/parity proofs at the existing read-only seam.
4. Only later start implementation of the dedicated charting engine boundary.

## 8. Relationship to Current Docs

- corpus planning:
  - `docs/r4/CHARTING_GOLDEN_CORPUS_PLAN.md`
- formal parity specification:
  - `docs/r4/CHARTING_PARITY_SPEC.md`
- programme roadmap:
  - `docs/r4/CHARTING_PARITY_ROADMAP.md`
- `dbo.Transactions.Status` continuity note:
  - `docs/r4/ODONTOGRAM_TRANSACTIONS_STATUS_CONTINUITY.md`

## 9. Notes on V1 Scope

- This document records the first selected corpus reference set only.
- It is still documentation/evidence curation work, not runtime implementation.
- No charting/odontogram module or engine boundary is created by this document.
