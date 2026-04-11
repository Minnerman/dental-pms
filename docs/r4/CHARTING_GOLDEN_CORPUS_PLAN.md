# CHARTING_GOLDEN_CORPUS_PLAN

## 1. Purpose

The golden corpus exists to:

- provide the evidence base for charting parity
- preserve high-value reference cases
- support future rule recovery, API proofs, and rendering validation
- reduce the risk of importing historic odontograms incorrectly

## 2. Definition of a Golden Case

A golden case is a curated patient/tooth reference used to verify one or more charting rules with preserved provenance.

At minimum, each golden case should include:

- patient id
- tooth number
- relevant raw source rows
- chronology / ordering evidence
- screenshot or confirmed observed R4 visual outcome
- expected visible family/families
- expected effective row(s)
- confidence level
- notes on uncertainty
- reason this case matters

## 3. Corpus Design Principles

- Prefer coverage over volume in the first iteration.
- Choose high-information cases that explain more than one rule where possible.
- Include both simple controls and edge cases.
- Preserve provenance from source rows through to observed outcome.
- Avoid duplicate low-value examples unless they strengthen a weak rule.
- Keep explicit confidence labels on every case.
- Separate already-analysed evidence from merely candidate cases.
- Track missing coverage deliberately rather than pretending the current set is complete.

## 4. Required Coverage Categories

The first corpus must cover at minimum:

- simple fillings
- crowns
- root fillings / root canal
- posts
- missing tooth
- retained root
- `Tooth Present` scaffold cases
- `Reset Tooth` sequences
- same-family overlap
- multi-family coexistence
- special surfaces such as `224`
- completed-treatment-derived restorative families
- legacy oddities / ambiguous historic cases where available

## 5. Corpus Status Levels

- `candidate`: potentially useful, but not yet prioritised for the first working set
- `selected`: chosen for the first working corpus because it closes or strengthens a specific coverage need
- `analysed`: case has been materially reviewed against rows/screenshots, but expected outcome still needs tighter confirmation
- `confirmed`: row evidence and observed outcome align cleanly enough to use as a stable reference
- `disputed`: previously useful, but now conflicts with newer evidence or has unresolved interpretation
- `parked`: known case retained for reference, but not currently part of the active working set

Typical movement:

- `candidate -> selected` when it fills a deliberate coverage gap
- `selected -> analysed` when row/screenshot review has been done
- `analysed -> confirmed` when the rule/outcome alignment is strong enough to rely on
- any case -> `disputed` if later evidence conflicts
- any case -> `parked` if it becomes low-priority or redundant

## 6. Confidence Model

- `high`: row data and rendered outcome align cleanly with no major unresolved ambiguity
- `medium`: strong inference, but one important unknown remains
- `low`: useful case, but interpretation is still ambiguous or incomplete

## 7. Required Evidence Fields

Future case entries should capture at least these fields:

- corpus status
- confidence
- patient id
- tooth number(s)
- screenshot reference(s)
- source table/view family
- relevant row ids / refs
- relevant row sequence / ordering basis
- relevant `Status`, `SubType`, `Surface`, `Material`, `Condition`
- expected visible family/families
- expected effective row(s)
- reset boundary present: `yes/no/unknown`
- special surface present: `yes/no/which`
- why the case matters
- uncertainty notes
- follow-up needed

## 8. Initial Curated Candidate Inventory

### Current Known Cases

| Patient | Tooth/teeth of interest | Categories covered | Why valuable | Status | Confidence |
|---|---|---|---|---|---|
| `1006366` | `16` | root filling, special surface `224`, multi-family coexistence, completed-treatment-derived restorative family | Cleanest reviewed case showing a coronal restorative family and a root/endodontic family coexisting on one tooth; strong for special-surface behaviour | `selected` | `high` |
| `1011746` | `14` | simple fillings, same-family overlap, caries overlay behaviour | Strong same-family filling case where row chronology and visible family line up cleanly enough to test precedence/overlay interpretation | `selected` | `high` |
| `1012070` | `16` | `Reset Tooth`, same-family overlap, mixed-family coexistence, legacy ambiguity | Best currently known reset-heavy mixed case; valuable for reset/survival logic even though it remains more ambiguous than the cleaner controls | `selected` | `medium` |
| `1012191` | `5`, `14`, `23`, `36` | missing tooth, retained root, direct `Status 4` tooth-state rows | Best current tooth-state-heavy case where visible meaning is carried without same-tooth restorative base rows; useful for missing/root state families | `selected` | `high` |
| `1017001` | `4`, `7`, `8`, `11-16`, lower restorative teeth | crowns, root fillings, posts, special surface `224`, simple fillings, `Tooth Present`, completed-treatment-derived restorative families, multi-family coexistence | Highest-coverage reviewed patient so far; supplies control cases, crown/root/post combinations, and multiple restorative family examples | `selected` | `high` |

### Additional Candidate Slots Needed

- needs a clean `post + crown + root-canal` coexistence case with low ambiguity on one tooth
- needs a simple reset-before/after pair with minimal extra clutter
- needs more special-surface examples besides `224`
- needs at least one low-ambiguity completed-treatment-only crown control
- needs more low-ambiguity `Tooth Present` scaffold controls without mixed semantic clutter
- needs at least one clean retained-root control distinct from missing-tooth cases
- needs at least one low-ambiguity same-family crown-overlap case
- needs at least one low-ambiguity same-family root-filling overlap case if present in live data

## 9. Gap Analysis

Current known cases still do not cover well enough:

- a clean, low-ambiguity `post + crown + root-canal` coexistence reference that is confirmed rather than inferred
- broader special-surface coverage beyond `224`
- a simple reset sequence that shows before/reset/after without major mixed-family noise
- completed-treatment-only crown controls separated cleanly from baseline/current complexity
- enough low-ambiguity `Tooth Present` scaffold controls to make scaffold handling feel closed rather than just strongly inferred
- a broader sample of legacy oddities so rare behaviour can be distinguished from rule defects

## 10. Recommended Next Execution Order

1. Promote the strongest current cases from `candidate` to `selected` working references where not already done.
2. Find missing cases for uncovered categories, especially clean reset, special-surface, and coexistence controls.
3. Define a standard per-case evidence template using the required evidence fields above.
4. Start turning selected cases into API/parity proofs at the existing read-only seam.
5. Only later define and implement the dedicated charting engine boundary.

## 11. Relationship to Current Spec/Roadmap

- Formal parity specification:
  - `docs/r4/CHARTING_PARITY_SPEC.md`
- Programme roadmap:
  - `docs/r4/CHARTING_PARITY_ROADMAP.md`
- `dbo.Transactions.Status` continuity note:
  - `docs/r4/ODONTOGRAM_TRANSACTIONS_STATUS_CONTINUITY.md`

## 12. Notes on Current Corpus State

- This document is an initial Phase 2 planning and inventory definition only.
- The listed cases are the first curated working inventory, not a final or exhaustive corpus.
- No runtime/module change is justified by this document alone.
