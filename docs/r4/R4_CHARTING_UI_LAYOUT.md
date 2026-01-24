# R4 Charting UI Layout Parity (Stage 143)

Date: 2026-01-24
Feature flag: NEXT_PUBLIC_FEATURE_CHARTING_VIEWER=1

## Summary
Stage 143 focuses on layout/UX parity only (read-only). The data pipeline and API remain unchanged.

## Evidence
- Playwright parity report: `tmp/stage143/ui_parity.json`.

## Operational notes
- Read-only banner and last-imported metadata are displayed in the charting viewer.
- Charting viewer availability is controlled by the runtime flag `FEATURE_CHARTING_VIEWER`.
- Stage 151 adds CSV export; Stage 152 moves charting filters to the server.

## Filters (Stage 152)
- Perio probes: date range, tooth, site, bleeding-only, plaque-only.
- BPE: date range + "latest exam only" toggle (furcations follow the same filters).
- Patient notes: text search, category filter, date range.
- Filters are server-backed; totals and pagination reflect the filtered dataset.
- Stage 153 adds per-user filter presets (3 slots per section) stored in localStorage.

## CSV export (Stage 151)
- Export is Postgres-only and read-only.
- The CSV column order matches the spot-check format (`postgres_<entity>.csv` + `index.csv`).
- Export supports per-entity selection from the charting viewer.

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
