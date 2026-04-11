# CHARTING_GOLDEN_GAP_FILL_CANDIDATES_V1

## 1. Purpose

This document captures the first narrow corpus-expansion pass aimed at filling the biggest known gaps after `CHARTING_GOLDEN_SELECTED_CASES_V1.md`.

It is a read-only evidence-curation artefact only. It does not introduce runtime logic, tests, import behaviour, or a charting/odontogram module.

## 2. Gap Targets Used

This pass targeted the highest-value remaining corpus gaps:

- a cleaner `post + crown + root-canal` coexistence case
- a simpler reset before/after pair
- special-surface cases beyond `224`
- lower-ambiguity completed-treatment-only controls for crown / root / post families
- one genuinely useful legacy oddity

## 3. Search and Selection Method

Search basis:

- live read-only SQL inspection against `dbo.Transactions` joined to `dbo.SubTypes`
- `RefId` / transaction chronology review for ordering
- existing baseline screenshots where already available
- the current charting parity model already recorded in the continuity note, roadmap, and parity spec

Selection approach:

- prioritise cases that close more than one open coverage gap
- prefer screenshot-backed candidates first when the screenshot already exists locally
- prefer SQL-only candidates only when their row structure is unusually clean
- avoid broad dumps; keep only the cases that materially improve the corpus

Why these cases were chosen over others:

- they add the clearest current evidence for the missing gaps
- they improve category coverage without widening into a fresh broad discovery pass
- they are easier to promote into future selected corpus entries or API/parity proofs than noisier alternatives

## 4. New Candidate Cases

### `1017000`

- patient id: `1017000`
- tooth/teeth: `11`, `12`, `73`
- candidate status: `candidate`
- confidence: `high`
- categories covered:
  - clean `post + crown + root-canal` coexistence
  - special surface `32`
  - screenshot-backed control
  - possible legacy oddity via tooth `73`
- why this case matters:
  - strongest new screenshot-backed candidate for a cleaner multi-family restorative coexistence case
- brief raw-row / chronology summary:
  - tooth `11`: `Tooth Present` -> `Crown` -> `Root Filling` `Surface 32` -> `Post`
  - tooth `12`: `Tooth Present` -> `Crown` -> `Root Filling` `Surface 32`
  - tooth `73`: `Status 1 Tooth Present` on a non-standard tooth number
- current expected visible family/families:
  - tooth `11`: `crown`, `root canal / root filling`, `post`
  - tooth `12`: `crown`, `root canal / root filling`
- current expected effective row(s):
  - latest same-family rows on teeth `11` and `12`, with coexistence across families rather than whole-tooth collapse
- key uncertainty, if any:
  - tooth `73` may be a useful oddity signal, but its rendered behaviour is not yet isolated
- screenshot / observed R4 outcome reference:
  - `/home/amir/odontogram-screenshots/1017000/1017000-baseline-full.png`

### `1013333`

- patient id: `1013333`
- tooth/teeth: `4`, `25`
- candidate status: `candidate`
- confidence: `medium`
- categories covered:
  - simpler reset before/after pattern
  - special surfaces `32` and `96`
  - screenshot-backed mixed control
- why this case matters:
  - strongest currently available screenshot-backed reset candidate outside the already-selected mixed reset case
- brief raw-row / chronology summary:
  - tooth `4`: `Tooth Present` -> `Missing Tooth` -> `Reset Tooth` -> `Tooth Present` -> later `Fillings`
  - tooth `25`: `Tooth Present` -> `Fillings` -> later `Status 0 Root Filling Surface 96` -> later `Status 0 Crown`
- current expected visible family/families:
  - tooth `4`: post-reset filling-family behaviour
  - tooth `25`: filling plus completed root/crown-derived family context
- current expected effective row(s):
  - tooth `4`: post-reset semantic row is the best current candidate
  - tooth `25`: completed-treatment-derived root/crown rows are useful control candidates, but final display contribution still needs tighter confirmation
- key uncertainty, if any:
  - the patient is still mixed enough that not every tooth is low-ambiguity
- screenshot / observed R4 outcome reference:
  - `/home/amir/odontogram-screenshots/1013333/1013333-baseline.png`

### `1009153`

- patient id: `1009153`
- tooth/teeth: `6`
- candidate status: `candidate`
- confidence: `medium`
- categories covered:
  - completed-treatment-only triple-family control
  - special surface `32`
  - SQL-only clean control
- why this case matters:
  - cleanest SQL-only control found for `Root Filling Surface 32` + `Post` + `Crown` on one tooth with no current semantic rows on that tooth
- brief raw-row / chronology summary:
  - tooth `6`: `Status 0 Root Filling Surface 32` -> `Status 0 Post` -> `Status 0 Crown`
- current expected visible family/families:
  - `root canal / root filling`
  - `post`
  - `crown`
- current expected effective row(s):
  - completed-treatment-derived rows are the only family candidates on the tooth, so this is a strong future control for completed-treatment projection
- key uncertainty, if any:
  - no screenshot has been captured yet, so visible confirmation remains pending

### `1011978`

- patient id: `1011978`
- tooth/teeth: `25`
- candidate status: `candidate`
- confidence: `medium`
- categories covered:
  - completed-treatment-only control
  - special surface `96`
  - SQL-only root/crown control
- why this case matters:
  - cleaner special-surface `96` control than the mixed cases already known
- brief raw-row / chronology summary:
  - tooth `25`: `Tooth Present` -> later `Status 0 Root Filling Surface 96` -> later `Status 0 Crown`
- current expected visible family/families:
  - `root canal / root filling`
  - `crown`
- current expected effective row(s):
  - latest completed-treatment-derived root/crown rows are the best current candidates for any derived display projection on this tooth
- key uncertainty, if any:
  - screenshot confirmation is still missing

### `1013045`

- patient id: `1013045`
- tooth/teeth: `10`, `26`
- candidate status: `candidate`
- confidence: `medium`
- categories covered:
  - low-ambiguity completed-treatment-only single-family controls
  - crown control
  - root-filling `Surface 32` control
- why this case matters:
  - provides simpler single-family SQL-only controls than the more complex mixed cases
- brief raw-row / chronology summary:
  - tooth `10`: `Status 0 Crown` only
  - tooth `26`: `Status 0 Root Filling Surface 32` only
- current expected visible family/families:
  - tooth `10`: `crown`
  - tooth `26`: `root canal / root filling`
- current expected effective row(s):
  - the single completed-treatment row on each tooth is the only candidate family row
- key uncertainty, if any:
  - no screenshot has been captured yet

### `1016998`

- patient id: `1016998`
- tooth/teeth: `47`, `49`, `50`, `51`, `52`, `54`, `67`, `69`, `70`, `71`, `72`, `74`
- candidate status: `candidate`
- confidence: `low`
- categories covered:
  - legacy oddity
  - unusual tooth-numbering pattern
  - scaffold-only oddity
- why this case matters:
  - strongest currently observed tooth-numbering oddity in the live data, with many non-standard/primary-style tooth numbers carrying `Tooth Present` rows
- brief raw-row / chronology summary:
  - the patient contains a dense set of `Status 3 Tooth Present` rows on tooth numbers outside the standard `1-38` range, plus tooth `0` exam rows
- current expected visible family/families:
  - scaffold/tooth-presence only
- current expected effective row(s):
  - `Tooth Present` scaffold rows on non-standard tooth numbers
- key uncertainty, if any:
  - rendered handling of these tooth numbers is not yet confirmed, so this remains an oddity candidate rather than a selected reference

## 5. Coverage Improvement Summary

This pass improves coverage materially for:

- a cleaner `post + crown + root-canal` coexistence candidate:
  - `1017000`
  - `1009153`
- a simpler reset before/after pattern:
  - `1013333`
- special surfaces beyond `224`:
  - `1017000` (`32`)
  - `1013333` (`32`, `96`)
  - `1011978` (`96`)
  - `1013045` (`32`)
  - `1009153` (`32`)
- lower-ambiguity completed-treatment-only controls:
  - `1009153`
  - `1011978`
  - `1013045`
- legacy oddity coverage:
  - `1016998`

Still weak after this pass:

- screenshot-backed completed-treatment-only controls
- screenshot-backed special-surface cases beyond `224` with low ambiguity
- a screenshot-backed legacy oddity with confirmed rendered outcome

## 6. Recommended Promotion Candidates

Strongest candidates to promote next into the selected corpus:

- `1017000`
  - best new screenshot-backed coexistence case
- `1013333`
  - best new screenshot-backed reset/special-surface case
- `1009153`
  - cleanest SQL-only completed-treatment-only triple-family control
- `1011978`
  - strongest SQL-only special-surface `96` completed-treatment control

Keep as candidate-only for now:

- `1013045`
  - useful control, but still screenshot-free and single-family only
- `1016998`
  - useful oddity, but still too unconfirmed for promotion

## 7. Remaining Biggest Gaps

Highest-priority gaps still open:

- screenshot-backed completed-treatment-only crown/root/post controls
- more low-ambiguity reset before/after pairs
- broader special-surface coverage beyond `32`, `96`, and `224`
- stronger retained-root-specific controls outside mixed missing-tooth cases
- confirmation of how legacy non-standard tooth numbers render, if they render at all

## 8. Immediate Next Execution Order

1. Promote the strongest new candidates into a Selected Corpus V2 document.
2. Tighten explicit rule extraction using the expanded corpus.
3. Turn promoted cases into stronger API/parity proofs at the existing read-only seam.
4. Only then begin designing the dedicated charting engine boundary.

## 9. Relationship to Current Docs

- selected corpus V1:
  - `docs/r4/CHARTING_GOLDEN_SELECTED_CASES_V1.md`
- corpus planning:
  - `docs/r4/CHARTING_GOLDEN_CORPUS_PLAN.md`
- formal parity specification:
  - `docs/r4/CHARTING_PARITY_SPEC.md`
- programme roadmap:
  - `docs/r4/CHARTING_PARITY_ROADMAP.md`
- `dbo.Transactions.Status` continuity note:
  - `docs/r4/ODONTOGRAM_TRANSACTIONS_STATUS_CONTINUITY.md`
