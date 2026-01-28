# Stage 173f — Manual mapping session runbook (2026-01-29)

Goal:
- Resolve 8 remaining R4 legacy patient codes using R4 UI + NG lookup.
- Record findings in `docs/r4/R4_MANUAL_MAPPING_WORKLOG_2026-01-28.md`.

Unresolved legacy codes (8):
- 1016090
- 1015376
- 1011407
- 1012098
- 1010864
- 1013684
- 1015469
- 1012223

Step 1: R4 UI lookup (per code)
1) Search by Patient Code / Patient Number (exact number).
2) If not found, try Chart No field.
3) Copy fields:
   - Surname
   - Forename(s)
   - DOB (DD/MM/YYYY)
   - Full postcode
   - Address line 1 (optional)
   - Phone/mobile (optional)
   - Chart No / Patient No / NHS No (if shown)

Step 2: NG lookup (after each patient)
Run:
  bash ops/run_backend_script.sh scripts/ng_person_lookup.py \
    --surname "SURNAME" \
    --dob 1970-01-01 \
    --postcode "BN11 1EG" \
    --phone "07..." \
    --limit 10

If you need to share output externally, re-run with redaction:
  bash ops/run_backend_script.sh scripts/ng_person_lookup.py \
    --surname "SURNAME" \
    --dob 1970-01-01 \
    --postcode "BN11 1EG" \
    --phone "07..." \
    --limit 10 \
    --redact

Accept a mapping only if 2+ identifiers match:
- surname + DOB (best)
- surname + full postcode
- surname + phone last-6

If unclear, mark REVIEW and move on.

Step 3: End-of-session batch check
  bash ops/run_backend_script.sh scripts/ng_person_lookup.py \
    --from-worklog docs/r4/R4_MANUAL_MAPPING_WORKLOG_2026-01-28.md

Redacted batch (safe to share):
  bash ops/run_backend_script.sh scripts/ng_person_lookup.py \
    --from-worklog docs/r4/R4_MANUAL_MAPPING_WORKLOG_2026-01-28.md \
    --redact

Helper: print unresolved codes from worklog
  python3 scripts/print_unresolved_codes.py
