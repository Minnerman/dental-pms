# R4 Charting UI Layout Parity (Stage 143)

Date: 2026-01-24
Feature flag: NEXT_PUBLIC_FEATURE_CHARTING_VIEWER=1

## Summary
Stage 143 focuses on layout/UX parity only (read-only). The data pipeline and API remain unchanged.

## Evidence
- Playwright parity report: `tmp/stage143/ui_parity.json`.

## Perio probes
- Grouped by exam date (latest exam highlighted).
- Within a date: ordered by tooth number, then probing site order (MB, B, DB, ML, L, DL).
- Site labels shown as R4-style abbreviations with numeric code retained (e.g., "MB (1)").

## BPE entries
- Grouped by exam date (latest exam highlighted).
- Sextant values displayed as a 2x3 grid (UR, UA, UL / LL, LA, LR).
- Notes and user code shown as compact badges.

## BPE furcations
- Grouped by exam date (latest exam highlighted).
- Displayed in a table with tooth, furcation grade, and sextant.

## Patient notes
- Chronological list (newest first), default shows latest 10.
- Category shown as a badge; note text preserves line breaks.
- "Show all" toggle for full history.

## Tooth surfaces
- Read-only lookup table remains available for parity sanity checks.

## Open gaps
- Full odontogram visuals and surface overlays are still out of scope.
- Fine-grained surface rendering and R4 iconography to be addressed in a future stage.
