# Prescription and recall template handover

On 13 October 2026 the owner selected three reusable templates for future use:
Private Prescription, Recall - 6 months and Recall - 12 months. The prescription
must be typed in the PMS before printing. Historical documents remain in R4 or
the archive; this feature does not import them.

## Workflow

1. Open the patient's Documents view and select **Private Prescription - typed**.
2. Enter medicine name/strength/form, directions, quantity, prescriber name and
   prescriber GDC number. All five fields are required; there are no drug defaults.
3. Preview the merged patient details and entered prescription, then save.
4. Download the saved document as PDF for printing and signing. The signature
   and practice-stamp spaces are blank.

Editing the draft clears its preview. Saving, selecting another template or
navigating to another patient clears the prescription entry. The saved body is
a text snapshot: later edits to the shared template do not alter it. Entered
text is not recursively interpreted as a merge field. Existing document
capabilities, audit events and request-ID replay behaviour remain in place.

Choose **Recall - 6 months** or **Recall - 12 months** in the same template list
for a routine reminder. These templates do not select a clinical interval,
calculate due dates or change the separate recall-dashboard letter generator.

## Installation and limits

The existing backend startup seeder adds the three named templates if absent,
preserving existing templates and edits. No database migration is needed.
The typed form requires all five `prescription.*` fields in the prescription
template body. Legacy templates without these fields continue to work as before.

The PDF uses the existing practice header and plain-text document layout;
it does not reproduce the R4 Word table. Body lines wrap to the printable width,
including long unbroken words. Longer prescriptions can span multiple pages.
The PDF header's patient/practice details and Generated date are resolved when
exported; only the saved document body is frozen. The feature does not validate
medicine choice, dose or registration, and does not apply an electronic signature.

This branch has not been deployed. After merge and the separate deployment
instruction, check practice settings and print one synthetic example for owner
review before using the templates with patients.

## Validation

All data used here is synthetic. The isolated worktree is
`/home/amir/dental-pms-prescription-entry`, Compose project
`dental_prescription_entry`, with separate database/attachment volumes and
loopback ports 8187/3187. No R4 connection or production data was used.

Run these only from the configured isolated worktree:

```sh
cd /home/amir/dental-pms-prescription-entry
bash ops/health.sh
SKIP_DOCKER_BUILD=1 bash ops/verify.sh
docker compose exec -T backend pytest -q
```

- Health: passed.
- Verify: passed, including production frontend build, typecheck and health.
  `SKIP_DOCKER_BUILD=1` reused dependency images with the current worktree source
  mounted; it did not skip the frontend production build or other verify checks.
- Full backend suite on a fresh synthetic database: **704 passed, 2 skipped**.
- Focused prescription/document reliability suite: **15 passed**.
- Four document browser checks: **4 passed** using:

```sh
set -a
. ./.env
set +a
cd frontend
npx playwright test tests/patient-prescription-entry.spec.ts \
  tests/patient-document-preview.spec.ts tests/patient-document-save.spec.ts \
  --workers=1 --output=../.run/browser-check-2
```

The networkless print check rendered all three defaults with synthetic details:
one page each, no unknown placeholders, and all entered prescription values and
the final manufacturer field present in extracted PDF text. Long unbroken text
also has unit coverage for printable width. Receipts are in the isolated
worktree's ignored `.run/` directory: `backend-final.log`, `verify-2.log`,
`prescription-browser-tests-2.log` and `template-print-check.log`.

The first full-suite run against a reused database failed an existing lifecycle
test that assumes its patient is on the first page, plus a charting fixture
assertion expecting `500` despite generating a different code. Fresh baseline
`d81bb96` and feature runs both reproduced the charting assertion alone
(697 and 703 passes respectively). The assertion now compares with its generated
fixture code, in a separate test-only commit. The final fresh run passes with
charting enabled; no application charting behaviour was changed.

An initial browser run failed because the isolated frontend's development server
inherited `NODE_ENV=production`. Correcting the ignored test Compose override
resolved this; the passing browser/build receipts are from the corrected setup.
