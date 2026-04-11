# CHARTING_RULE_RECOVERY_V1

## 1. Purpose

This document records the first explicit recovered working rules for R4 charting parity based on the selected corpus and the current read-only tooth-state proof seam.

It is a rule-extraction artefact only. It does not introduce runtime logic, tests, import behaviour, or a charting/odontogram module.

## 2. Evidence Basis

This rule set is based on:

- the `dbo.Transactions.Status` continuity investigation
- selected cases V1
- selected cases V2
- gap-fill candidates V1 where relevant
- existing merged read-only tooth-state seam proofs
- the charting parity specification and roadmap

No new broad discovery pass was required for this document. This is a structured recovery of working rules from already-curated evidence.

## 3. Rule Confidence Model

- `proven`
  - directly supported by merged read-only seam proofs and consistent with the selected corpus
- `strongly inferred`
  - best-supported by the selected corpus and prior read-only investigation, but not backed by vendor documentation or proprietary client logic
- `provisional`
  - plausible working rule, useful for planning, but still too weak or incomplete to hard-code safely

## 4. Recovered Rule Groups

### A. Status-Role Rules

- `[strongly inferred]` `Status 0` behaves as a completed/history treatment transaction row.
  - Working meaning: historic/completed treatment context rather than the primary current baseline semantic bucket.
- `[strongly inferred]` `Status 1` behaves as the primary current baseline semantic row bucket.
  - Working meaning: the main current semantic source for restorative and many tooth-state families.
- `[strongly inferred]` `Status 3` behaves as a tooth-presence scaffold / initializer row.
  - Working meaning: background tooth context rather than the primary restorative semantic winner.
- `[strongly inferred]` `Status 4` behaves as a specialised semantic / reset-adjacent baseline row.
  - Working meaning: visible and semantic, but not a unique icon bucket.
- `[strongly inferred]` raw status values remain behavioural working labels only.
  - They are not recovered proprietary internal names.

### B. Family Grouping Rules

- `[proven]` crown-family rows map into a `crown` family at the current seam.
- `[proven]` `Root Filling` rows map into a `root canal / root filling` family at the current seam.
- `[proven]` `Post` and related post/core rows map into a `post` family at the current seam.
- `[strongly inferred]` `Fillings` and closely related carious/filling semantics belong to the same broad filling-family competition space.
- `[strongly inferred]` `Missing Tooth` is a direct tooth-state family, separate from restorative families.
- `[strongly inferred]` `Retained Root` is a direct tooth-state family, separate from restorative families.
- `[strongly inferred]` `Tooth Present` belongs to a scaffold/tooth-presence family rather than a primary restorative family.
- `[strongly inferred]` `Reset Tooth` belongs to a control/reset family rather than a visible icon family of its own.
- `[strongly inferred]` visible family identity is driven mainly by:
  - `SubType`
  - `Surface`
  - `Material`
  - `Condition`

### C. Reset and Survival Rules

- `[proven]` in the current read-only tooth-state seam, a reset boundary suppresses older same-tooth rows and allows later rows to survive.
- `[strongly inferred]` the latest reset boundary is the relevant baseline reset boundary for current display interpretation.
- `[strongly inferred]` pre-reset baseline rows should not control the current effective baseline state after a later reset.
- `[strongly inferred]` post-reset semantic rows are the strongest current candidates for the surviving/effective display state.
- `[provisional]` it is not yet safe to assume that reset semantics are identical for every rare legacy family or special surface combination.

### D. Same-Family Precedence Rules

- `[proven]` in the current read-only tooth-state seam, the latest surviving row within one family wins.
- `[strongly inferred]` same-family competition should be evaluated after reset handling, not before it.
- `[strongly inferred]` same-family overlap is a family-level precedence problem, not a whole-tooth winner-takes-all problem.
- `[strongly inferred]` raw status bucket alone does not determine the same-family winner.
- `[provisional]` the exact proprietary R4 arbitration rule between overlapping same-family `Status 1` and `Status 4` rows is not yet fully settled beyond the current working “latest surviving row in family” model.

### E. Cross-Family Coexistence Rules

- `[proven]` different restorative families can coexist on one tooth at the current read-only seam.
- `[proven]` filling-family rows and root-canal-family rows can coexist on one tooth at the current read-only seam.
- `[strongly inferred]` crown and root-canal families can coexist on one tooth.
- `[strongly inferred]` post and root-canal families can coexist on one tooth.
- `[strongly inferred]` crown, root-canal, and post can coexist as separate surviving families on one tooth.
- `[strongly inferred]` direct tooth-state families should not be collapsed into restorative families merely because they share the same tooth.

### F. Rendering / Projection Rules

- `[strongly inferred]` visible family is driven mainly by `SubType`, `Surface`, `Material`, and `Condition`.
- `[strongly inferred]` raw status bucket does not define a unique icon vocabulary.
- `[strongly inferred]` `Status 4` is visible and semantic, but not a standalone icon system.
- `[proven]` the current read-only tooth-state API projects typed family output from canonical rows rather than exposing raw flat status buckets as the display contract.
- `[strongly inferred]` the correct parity target is a derived display state built from surviving/effective rows, not a flat rendering of raw status values.

## 5. Rule-to-Case Support Map

| Rule | Confidence | Main support cases |
|---|---|---|
| `Status 0` behaves like completed/history treatment context | `strongly inferred` | `1009153`, `1011978`, `1013045`, `1013333`, continuity note |
| `Status 3` behaves like tooth-presence scaffold | `strongly inferred` | `1012070`, `1012191`, `1017001`, `1013333`, continuity note |
| `Status 4` is visible/semantic but not a unique icon bucket | `strongly inferred` | `1006366`, `1011746`, `1012070`, `1012191`, `1017001`, continuity note |
| latest surviving same-family row wins | `proven` | merged tooth-state seam proof, `1011746`, `1012070`, `1013333` |
| reset boundary invalidates older baseline state | `proven` at current seam / `strongly inferred` for parity | merged tooth-state seam proof, `1012070`, `1013333` |
| filling and root-canal families can coexist | `proven` | merged tooth-state seam proof, `1006366`, `1017001` |
| crown and root-canal families can coexist | `strongly inferred` | `1017000`, `1017001`, `1011978` |
| post and root-canal families can coexist | `strongly inferred` | `1017000`, `1017001`, `1009153` |
| crown + root-canal + post triple coexistence is viable | `strongly inferred` | `1017000`, `1009153` |
| missing tooth / retained root are direct tooth-state families | `strongly inferred` | `1012191`, `1017000`, `1017001` |
| special-surface controls matter and are not limited to `224` | `strongly inferred` | `1006366`, `1017000`, `1013333`, `1009153`, `1011978`, `1017001` |
| derived display should be built from effective rows rather than raw flat statuses | `strongly inferred` | continuity note, parity spec, selected corpus, current tooth-state seam |

## 6. Contradictions and Weak Areas

- Exact proprietary labels for raw statuses `1`, `3`, and `4` remain unknown.
- The exact proprietary arbitration rule between overlapping same-family `Status 1` and `Status 4` rows is still not fully documented.
- Completed-treatment-only controls are useful, but screenshot-backed confirmation is still missing for several of them.
- Special surfaces beyond `224`, `32`, and `96` remain weakly covered.
- Legacy oddities such as non-standard tooth numbers remain too weakly understood to drive implementation rules.

## 7. Rules That Are Not Yet Safe to Hard-Code

- A hard rule that `Status 4` always beats `Status 1`.
- A hard rule that every reset invalidates all historic/context rows in exactly the same way across every family.
- A blanket rule that every `Status 0` restorative row should always project into visible current display state.
- A blanket rule for all rare surface encodings beyond the currently covered set.
- Any rendering rule for non-standard tooth numbers until their display behaviour is confirmed.

## 8. Immediate Next Execution Order

1. Fill the highest-impact remaining corpus gaps.
2. Tighten the provisional rules into `strongly inferred` or `proven` rules where possible.
3. Only then define the dedicated charting engine boundary in implementation terms.

## 9. Relationship to Current Docs

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
