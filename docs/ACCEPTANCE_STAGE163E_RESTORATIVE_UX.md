# Stage 163E Restorative UX Acceptance Checklist

Purpose: protect restorative chart interaction behavior (selection, surface toggles, keyboard navigation, undo/redo, visible state).

## Preconditions
- `master` is up to date and working tree is clean.
- Stage 163C/163D artefacts exist:
  - `.run/stage163c/restorative_proof_patients.json`
  - `.run/stage163d/restorative_proof_patients_stage163d.json`
- App services are healthy (`./ops/health.sh`).

## Fast Checks
1. Frontend typecheck:
```bash
cd frontend
npm run -s typecheck
```

2. Restorative UX interaction spec:
```bash
cd frontend
ADMIN_EMAIL=... ADMIN_PASSWORD=... \
RESTORATIVE_UX_ARTIFACT_DIR=/home/amir/dental-pms/.run/stage163e \
npx playwright test tests/clinical-odontogram-restorative-ux.spec.ts --reporter=line
```

3. Real restorative glyph proof (existing Stage 163D proof cohort):
```bash
cd frontend
ADMIN_EMAIL=... ADMIN_PASSWORD=... \
RESTORATIVE_PROOF_PATIENTS_FILE=/home/amir/dental-pms/.run/stage163d/restorative_proof_patients_stage163d.json \
RESTORATIVE_ODONTOGRAM_ARTIFACT_DIR=/home/amir/dental-pms/.run/stage163e \
npx playwright test tests/clinical-odontogram-restorative-real.spec.ts --reporter=line
```

## Expected UX Behaviors
- Clicking a tooth selects that tooth and clears surface selection.
- Pressing surface shortcuts (`M/O/D/B/L/I`) toggles that surface on the selected tooth.
- Left/right arrows move selection deterministically across odontogram teeth.
- Undo (`Ctrl/Cmd+Z`) and redo (`Ctrl/Cmd+Shift+Z` or `Ctrl/Cmd+Y`) restore chart selection state.
- Selection state remains visible in the toolbar (`tooth` + `surface`).

## Expected Artefacts
- `.run/stage163e/odontogram_restorative_ux_*.png`
- `.run/stage163e/odontogram_restorative_real_*.png`

## Stop Conditions
- Surface toggle or keyboard navigation fails in Playwright UX spec.
- Undo/redo does not restore prior selection state.
- Real restorative proof spec regresses.
- Clinical chart selection state is not visible or drifts from highlighted UI state.
