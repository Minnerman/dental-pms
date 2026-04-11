# ODONTOGRAM_TRANSACTIONS_STATUS_CONTINUITY

## Scope

- This note preserves the completed read-only multi-pass investigation into raw `dbo.Transactions.Status` in the R4 odontogram/baseline data.
- Authoritative repo baseline for the investigation: branch `master`, SHA `a7c9ae9f9f1614038272211432257639079ca964`.
- The investigation itself was conducted read-only with no repo file changes; this file is a later continuity save of the result.

## Non-Conflation Warning

Do not conflate:

- BPE score `4`
- tooth number `4`
- raw `dbo.Transactions.Status = 4`

The BPE/perio module is a separate domain. No evidence from this investigation supports treating raw odontogram `Status 4` as a periodontal/BPE meaning.

## Final Best-Supported Model

- `Transactions.Status` is best understood as an internal chart-row role/state field, not a user-facing clinical enum.
- This is inferred from read-only behavioural profiling and cross-source comparison.
- It is not directly documented in accessible schema metadata, SQL object text, repo docs, or local passive artefacts.

## Best Behavioural Labels

- Status `0` = completed/history treatment transaction row
- Status `1` = primary current baseline semantic row
- Status `3` = tooth-presence scaffold / initializer row
- Status `4` = specialised semantic / reset-adjacent baseline row

## Status 4 Conclusion

- Status `4` is visible.
- Status `4` is semantic.
- Status `4` is not a unique icon bucket.
- Status `4` is best treated as a specialised visible baseline semantic row type.

## Current Rendering Model

- Visible odontogram family is driven mainly by `SubType`, `Surface`, `Material`, and `Condition`.
- `Reset Tooth` acts as a reset / re-authoring boundary.
- Rendering likely uses the latest surviving post-reset row per family.
- Different families can still render together on the same tooth.

## Passive Sources Exhausted

The following passive read-only sources were exhausted without yielding an explicit business label for raw `Transactions.Status`:

- accessible DB metadata
- accessible SQL object text
- repo discovery/docs
- local passive artefact/resource search
- final passive label-recovery pass

## Remaining Unresolved Question

- Whether the proprietary R4 client or inaccessible SQL/view definitions contain the hidden internal label/arbitration logic for statuses `1`, `3`, and `4`.

## Decision Note

- This result is saved as continuity/documentation only.
- It does not by itself justify a new charting/odontogram module or a charting refactor.
