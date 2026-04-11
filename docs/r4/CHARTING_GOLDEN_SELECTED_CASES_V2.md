# CHARTING_GOLDEN_SELECTED_CASES_V2

## 1. Purpose

This document records the next promoted selected golden cases after the first narrow gap-fill pass.

It extends the selected corpus using already-justified evidence from `CHARTING_GOLDEN_GAP_FILL_CANDIDATES_V1.md`. It remains documentation and evidence curation only. No runtime logic, import behaviour, tests, or charting/odontogram module are created by this document.

## 2. Relationship to V1

- `CHARTING_GOLDEN_SELECTED_CASES_V1.md` remains the initial selected reference set.
- This V2 document adds promoted cases from the first gap-fill candidate pass.
- Together, V1 and V2 expand parity coverage before implementation and before a dedicated charting engine boundary is designed.

## 3. Promotion Criteria

The promoted cases were chosen because they:

- have high information value relative to the current gaps
- materially improve corpus coverage rather than duplicating low-value examples
- are lower ambiguity than the other remaining candidates from the first gap-fill pass
- support future rule extraction and read-only parity proof work more directly than the weaker candidates

## 4. V2 Promoted Selected Cases

### `1017000`

- patient id: `1017000`
- tooth/teeth: `11`, `12`
- case status: `selected`
- confidence: `high`
- categories covered:
  - `post + crown + root-canal` coexistence
  - special surface `32`
  - screenshot-backed restorative multi-family control
- why it was promoted:
  - strongest new screenshot-backed candidate for a cleaner restorative multi-family coexistence case
- concise raw-row / chronology summary:
  - tooth `11`: `Tooth Present` -> `Crown` -> `Root Filling Surface 32` -> `Post`
  - tooth `12`: `Tooth Present` -> `Crown` -> `Root Filling Surface 32`
- current expected visible family/families:
  - tooth `11`: `crown`, `root canal / root filling`, `post`
  - tooth `12`: `crown`, `root canal / root filling`
- current expected effective row(s):
  - latest same-family restorative rows, with coexistence across families rather than whole-tooth collapse
- remaining uncertainty, if any:
  - the same patient also contains tooth `73` as a possible legacy oddity, but that oddity is not part of the promoted selected case

### `1013333`

- patient id: `1013333`
- tooth/teeth: `4`, `25`
- case status: `selected`
- confidence: `medium`
- categories covered:
  - simpler reset before/after pattern
  - special surfaces `32` and `96`
  - screenshot-backed mixed control
- why it was promoted:
  - best screenshot-backed reset candidate added by the first gap-fill pass
- concise raw-row / chronology summary:
  - tooth `4`: `Tooth Present` -> `Missing Tooth` -> `Reset Tooth` -> `Tooth Present` -> later `Fillings`
  - tooth `25`: `Tooth Present` -> `Fillings` -> later `Status 0 Root Filling Surface 96` -> later `Status 0 Crown`
- current expected visible family/families:
  - tooth `4`: post-reset filling-family behaviour
  - tooth `25`: filling plus completed root/crown-derived family context
- current expected effective row(s):
  - tooth `4`: post-reset semantic row is the best current candidate
  - tooth `25`: completed-treatment-derived root/crown rows are useful control candidates but still need tighter visual confirmation
- remaining uncertainty, if any:
  - this remains more mixed than the cleanest control cases, so not every tooth in the patient should be treated as equally strong evidence

### `1009153`

- patient id: `1009153`
- tooth/teeth: `6`
- case status: `selected`
- confidence: `medium`
- categories covered:
  - completed-treatment-only triple-family control
  - special surface `32`
  - SQL-only clean control
- why it was promoted:
  - cleanest completed-treatment-only triple-family control found in the first gap-fill pass
- concise raw-row / chronology summary:
  - tooth `6`: `Status 0 Root Filling Surface 32` -> `Status 0 Post` -> `Status 0 Crown`
- current expected visible family/families:
  - `root canal / root filling`
  - `post`
  - `crown`
- current expected effective row(s):
  - completed-treatment-derived rows are the only family candidates on the tooth
- remaining uncertainty, if any:
  - screenshot confirmation is still missing, so this remains selected on SQL evidence rather than screenshot-backed parity

### `1011978`

- patient id: `1011978`
- tooth/teeth: `25`
- case status: `selected`
- confidence: `medium`
- categories covered:
  - completed-treatment-only control
  - special surface `96`
  - SQL-only root/crown control
- why it was promoted:
  - strongest special-surface `96` completed-treatment control found in the first gap-fill pass
- concise raw-row / chronology summary:
  - tooth `25`: `Tooth Present` -> later `Status 0 Root Filling Surface 96` -> later `Status 0 Crown`
- current expected visible family/families:
  - `root canal / root filling`
  - `crown`
- current expected effective row(s):
  - latest completed-treatment-derived root/crown rows are the best current candidates for any derived display projection on this tooth
- remaining uncertainty, if any:
  - screenshot confirmation is still missing

## 5. Coverage Gains from V2

V2 promotions improve the selected corpus materially for:

- cleaner `post + crown + root-canal` coexistence
- reset before/after coverage outside the original mixed reset case
- special surfaces beyond `224`, especially `32` and `96`
- completed-treatment-only controls for crown / root / post families

V2 is strongest where V1 was still thin:

- screenshot-backed restorative coexistence: strengthened by `1017000`
- screenshot-backed reset expansion: strengthened by `1013333`
- SQL-only completed-treatment controls: strengthened by `1009153` and `1011978`

## 6. Combined Corpus Status After V2

- V1 selected cases remain the initial stable selected reference set.
- V2 adds four promoted cases that materially expand coverage in the biggest previously open gap areas.
- The remaining candidate pool still includes weaker or narrower cases, especially:
  - `1013045`
  - `1016998`
- After V2, the selected corpus is broad enough to support tighter rule extraction and more deliberate parity-proof expansion without starting implementation yet.

## 7. Remaining Major Gaps After V2

Highest-priority gaps still open:

- screenshot-backed completed-treatment-only crown/root/post controls
- more low-ambiguity reset before/after pairs
- broader special-surface coverage beyond `32`, `96`, and `224`
- stronger retained-root-specific controls outside mixed missing-tooth cases
- confirmation of how legacy non-standard tooth numbers render, if they render at all

## 8. Immediate Next Execution Order

1. Use V1 + V2 as the expanded stable selected corpus.
2. Turn the strongest selected cases into tighter rule extraction and read-only parity proofs.
3. Only then begin designing the dedicated charting engine boundary.

## 9. Relationship to Current Docs

- selected corpus V1:
  - `docs/r4/CHARTING_GOLDEN_SELECTED_CASES_V1.md`
- first gap-fill candidate pass:
  - `docs/r4/CHARTING_GOLDEN_GAP_FILL_CANDIDATES_V1.md`
- corpus planning:
  - `docs/r4/CHARTING_GOLDEN_CORPUS_PLAN.md`
- formal parity specification:
  - `docs/r4/CHARTING_PARITY_SPEC.md`
- programme roadmap:
  - `docs/r4/CHARTING_PARITY_ROADMAP.md`
- `dbo.Transactions.Status` continuity note:
  - `docs/r4/ODONTOGRAM_TRANSACTIONS_STATUS_CONTINUITY.md`

## 10. Notes on V2 Scope

- This document promotes only the cases already justified in the first gap-fill candidate pass.
- It does not add new discovery.
- It does not justify immediate runtime or module changes.
