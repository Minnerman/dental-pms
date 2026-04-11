# CHARTING_RULE_HARDENING_V1

## 1. Purpose

This document records the first focused pass to harden the highest-impact provisional or weakly supported charting rules before implementation work begins.

It is still a read-only evidence/rule-hardening artefact only. It does not introduce runtime logic, tests, import behaviour, or a charting/odontogram module.

## 2. Target Rules Chosen

This pass focused on the smallest set of rules most likely to shape a future charting engine boundary:

1. reset/survival behaviour at the latest reset boundary
2. same-family precedence where `Status 1` and `Status 4` both appear
3. multi-family coexistence for `crown + root canal + post`
4. completed-treatment-only crown/root/post interaction with derived display
5. the currently covered special surfaces: `224`, `32`, and `96`

These rules were chosen because they are closest to future implementation decisions and still carried either provisional language or important caution flags in `CHARTING_RULE_RECOVERY_V1.md`.

## 3. Method

This pass remained narrow.

Evidence revisited:

- `CHARTING_RULE_RECOVERY_V1.md`
- selected corpus V1
- selected corpus V2
- gap-fill candidates V1 where directly relevant
- merged read-only tooth-state seam proofs in:
  - `backend/tests/patients/test_r4_charting_api.py`
  - `backend/tests/patients/test_tooth_state_classification.py`
- local screenshot-backed selected cases already referenced in the corpus:
  - `/home/amir/odontogram-screenshots/1017000/1017000-baseline-full.png`
  - `/home/amir/odontogram-screenshots/1013333/1013333-baseline.png`

This pass did not reopen broad discovery. It re-used the selected corpus and merged proof seam to tighten only the rules most likely to affect the eventual engine boundary.

## 4. Hardened Rule Findings

### Rule 1

- rule statement:
  - the latest reset boundary should be treated as the survival cut for baseline/current semantic rows on the tooth
- prior confidence level:
  - `strongly inferred` for the general rule
  - `provisional` for edge behaviour across mixed or rare families
- new evidence reviewed:
  - merged tooth-state seam proof for reset + later surviving row
  - selected case `1012070`
  - selected case `1013333` tooth `4`
- updated confidence level:
  - `strongly inferred`
- current outcome:
  - strong enough to influence future engine design for baseline/current semantic rows
- why:
  - the merged seam proof and two selected reset cases align on the same practical outcome:
    - pre-reset baseline rows stop controlling current effective state
    - post-reset semantic rows become the strongest current candidates
  - this is still not a safe blanket rule for every historic/context row or every rare family combination

### Rule 2

- rule statement:
  - same-family overlap must not be modeled as a hard `Status 4` priority rule; it should be treated as a family-and-chronology problem
- prior confidence level:
  - `provisional` for exact proprietary `Status 1` vs `Status 4` arbitration
- new evidence reviewed:
  - selected case `1011746`
  - selected case `1017001` control teeth
  - continuity note conclusions
  - merged tooth-state seam proof for latest surviving same-family row
- updated confidence level:
  - `strongly inferred` for the negative rule:
    - do not hard-code `Status 4` priority
  - `still provisional` for the exact proprietary arbitration label/algorithm
- current outcome:
  - future implementation can safely avoid a hard status-only precedence rule
- why:
  - the same visible families are already evidenced without `Status 4` owning a unique icon bucket
  - the best-supported working model remains latest surviving family row, not `Status 4` supremacy

### Rule 3

- rule statement:
  - crown, root-canal, and post families should be treated as independently surviving families on one tooth rather than one whole-tooth winner
- prior confidence level:
  - `strongly inferred`
- new evidence reviewed:
  - selected case `1017000`
  - selected case `1009153`
  - merged seam proof that different restorative families can coexist
  - merged classification proof that `Crown`, `Root Filling`, and `Post` map into distinct families
- updated confidence level:
  - `strongly inferred`
- current outcome:
  - strong enough to influence future engine boundary design
- why:
  - the selected corpus now has a screenshot-backed multi-family coexistence case and a cleaner SQL-only triple-family control
  - the merged seam already proves the core architectural idea that different families can coexist on one tooth
  - this remains short of `proven` because the merged seam does not yet contain a direct crown/root/post triple-family API proof

### Rule 4

- rule statement:
  - completed-treatment-only crown/root/post rows must be preserved as family candidates and source truth, but they are not yet safe to hard-code as always-current visible display
- prior confidence level:
  - weakly supported / cautionary in the recovery note
- new evidence reviewed:
  - selected case `1009153`
  - selected case `1011978`
  - candidate control `1013045`
  - continuity note and parity spec separation between source truth and derived display
- updated confidence level:
  - `strongly inferred` for preservation as source-truth family candidates
  - `still provisional` for automatic current-display projection
- current outcome:
  - strong enough to shape data-layer and projection design
- why:
  - the corpus now includes cleaner completed-treatment-only crown/root/post controls
  - those controls are good evidence that completed treatment rows matter and must not be discarded
  - screenshot-backed confirmation remains too thin to treat every such row as automatic visible current display

### Rule 5

- rule statement:
  - the currently covered special surfaces `224`, `32`, and `96` are strong enough to support targeted family-aware handling, but blanket rare-surface rules remain unsafe
- prior confidence level:
  - `strongly inferred` that special-surface controls matter
  - weak coverage beyond the currently known set
- new evidence reviewed:
  - selected cases `1006366`, `1017001`, `1017000`, `1013333`, `1009153`, `1011978`
- updated confidence level:
  - `strongly inferred` for the covered set:
    - `224`
    - `32`
    - `96`
  - `still provisional` for broader rare-surface generalisation
- current outcome:
  - future implementation can safely treat the covered surfaces as explicit evidence-backed cases
- why:
  - the selected corpus now repeats these surfaces across both screenshot-backed and SQL-only controls
  - the broader surface space is still too weakly covered for a blanket rule

## 5. Rules Still Not Safe to Hard-Code

- the exact proprietary arbitration algorithm or label for overlapping same-family `Status 1` and `Status 4` rows
- a blanket rule that every reset affects all historic/context rows identically across every family
- a blanket rule that every completed-treatment-only restorative row should always project into current visible display
- blanket interpretation of rare surfaces beyond the currently covered `224`, `32`, and `96`
- any rule for non-standard tooth numbers until rendering behaviour is confirmed directly

## 6. Impact on Future Engine Design

Rules now strong enough to influence the eventual engine boundary:

- model reset as an early survival-resolution step for baseline/current semantic rows
- model precedence per family, not per whole tooth
- allow different restorative families to coexist on one tooth
- preserve completed/history rows as source truth even when display projection remains unresolved
- support targeted handling for the currently covered special surfaces rather than assuming all rare surfaces behave alike

Rules still too uncertain to drive implementation directly:

- exact proprietary `Status 1` vs `Status 4` arbitration
- blanket completed-treatment-to-display projection
- blanket rare-surface mapping beyond the covered set
- legacy/non-standard tooth-number rendering

## 7. Immediate Next Execution Order

1. Merge the strongest hardened rules back into the working parity model.
2. Do one more small contradiction or gap pass only where it materially changes engine-shaping decisions.
3. Then begin defining the dedicated charting engine boundary.

## 8. Relationship to Current Docs

- first explicit rule recovery:
  - `docs/r4/CHARTING_RULE_RECOVERY_V1.md`
- selected corpus V1:
  - `docs/r4/CHARTING_GOLDEN_SELECTED_CASES_V1.md`
- selected corpus V2:
  - `docs/r4/CHARTING_GOLDEN_SELECTED_CASES_V2.md`
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
