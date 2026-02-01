# Stage 129 — R4 charting canonical plan

Source of truth: `docs/r4/R4_CHARTING_DISCOVERY.md`

## 1) Charting domains/entities to support
- Tooth systems (tooth numbering system definitions).
- Tooth surfaces (surface labels per tooth).
- Planned/completed chart items (treatment plan headers + items + review status).
- Chart healing/actions (action history and potential links to treatment/appointments).
- Perio/BPE (BPE entries, furcations, probing depths, plaque/bleeding).
- Charting notes (patient notes, fixed notes, note categories, treatment notes, temporary notes, old notes).

## 2) Canonical entities (tables) and fields

### Canonical record store (new)
**Table:** `r4_charting_canonical_records`
- **Purpose:** Raw, fully faithful chart events/observations and reference rows. Preserve source data without premature normalization.
- **Primary key:** `id` (UUID).
- **Idempotency key:** `unique_key` (text, unique). Derived from `(domain, r4_source, r4_source_id, patient_code_or_id)`.
- **R4 provenance:**
  - `r4_source` (text; source table/view name).
  - `r4_source_id` (text; source row key or composite key string).
  - `legacy_patient_code` (int; when present in source).
  - `extracted_at` (timestamp when read from R4).
- **Patient linkage:**
  - `patient_id` (FK to PMS patient) when mapping exists.
  - `legacy_patient_code` retained even when mapping is missing.
- **Stable query columns (only when needed for UI/filtering):**
  - `domain` (text; e.g., `tooth_system`, `tooth_surface`, `treatment_plan_item`, `bpe`, `perio_probe`, `patient_note`, etc.).
  - `recorded_at` / `entered_at` (timestamps if present in source).
  - `tooth` (smallint; R4 tooth id).
  - `surface` (smallint; R4 surface code).
  - `code_id` (int; treatment code id if present).
  - `status` (text; planned/completed/accepted/etc when present).
- **Payload:**
  - `payload` (JSONB) contains the full source record or extra fields that do not map cleanly.
- **Uncertainty notes:**
  - Completed work source is still ambiguous (may be `TreatmentPlanItems` status or separate transactions table).
  - Tooth numbering system and surface encoding require confirmation in production data.

### Reference entities (existing models)
These already exist and remain authoritative for structured access:
- `r4_tooth_systems`
- `r4_tooth_surfaces`
- `r4_chart_healing_actions`
- `r4_bpe_entries`
- `r4_bpe_furcations`
- `r4_perio_probes`
- `r4_perio_plaque`
- `r4_patient_notes`
- `r4_fixed_notes`
- `r4_note_categories`
- `r4_treatment_notes`
- `r4_temporary_notes`
- `r4_old_patient_notes`

The canonical table is a “raw layer” that can coexist with these structured tables. It is the safest place to preserve source fidelity while the final mapping rules are still evolving.

## 3) Idempotency / upsert keys
- `r4_charting_canonical_records.unique_key` is required and must be stable across runs.
- Proposed format (string):
  - `{domain}|{r4_source}|{r4_source_id}|{patient_code_or_id}`
  - `patient_code_or_id` is `patient_id` if mapped, else `legacy_patient_code`, else empty.

## 4) Import ordering
1. Patient mapping (existing; needed for `patient_id`).
2. Reference tables: tooth systems, tooth surfaces (if imported to canonical).
3. Treatment plans / plan items / reviews.
4. Chart healing actions.
5. Perio/BPE (BPE, furcations, probes, plaque).
6. Notes (patient notes, fixed notes, note categories, treatment notes, temporary/old notes).

## 5) Parity expectations
- Tooth numbering and surface labeling match R4 (FDI/Palmer/Universal) and draw order.
- Planned vs completed overlays reflect exact status semantics.
- Perio/BPE values and dates are identical to R4.
- Notes (including fixed and treatment notes) retain categories, tooth/surface bindings, and ordering.
- Canonical payload must allow reconstruction of any unknown semantics without re-reading R4.
