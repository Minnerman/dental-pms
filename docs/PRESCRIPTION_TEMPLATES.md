# Prescription and recall template handover

On 13 October 2026 the owner selected three reusable templates for future use:
Private Prescription, Recall - 6 months and Recall - 12 months. The prescription
must be typed in the PMS before printing. Historical documents remain in R4 or
the archive; this feature does not import them. The owner subsequently requested
a Prescriptions tab and a dropdown for the four or five prescriptions commonly
used at the practice.

## Set up usual prescriptions

In **Templates → Prescriptions**, create a named template containing medicine
name/strength/form, directions and quantity. Save it, then use **New template**
to add another. Existing entries can be selected from the dropdown and edited.
Uncheck **Available in the prescription dropdown** to deactivate an entry;
it can be reactivated later. There is no limit of five templates.

The library starts empty: the practice enters its own usual prescriptions.
Entries are shared through the PMS database across practice computers. As with
the existing document-template editor, only superadmins can create or edit
them; reading requires the document download capability.

## Workflow

1. Open the patient's Documents view and select **Private Prescription - typed**.
2. Choose a **Saved prescription** to fill the medicine, directions and quantity,
   or enter those details manually. Adjust them for this patient and enter the
   prescriber name and GDC number. All five fields are required.
3. Preview the merged patient details and entered prescription, then save.
4. Download the saved document as PDF for printing and signing. The signature
   and practice-stamp spaces are blank.

Editing the draft clears its preview. Saving, selecting another template or
navigating to another patient clears the prescription entry. The saved body is
a text snapshot: later edits to the shared template do not alter it. Entered
text is not recursively interpreted as a merge field. Existing document
capabilities, audit events and request-ID replay behaviour remain in place.
Selecting a saved prescription copies its values into the patient draft;
patient-specific edits never update the shared library. Later editing or
deactivating that library entry does not change already saved documents.
The **Manage prescription templates** link opens the library separately; the
patient dropdown refreshes when returning to that window.

Choose **Recall - 6 months** or **Recall - 12 months** in the same template list
for a routine reminder. These templates do not select a clinical interval,
calculate due dates or change the separate recall-dashboard letter generator.

## Installation and limits

The existing backend startup seeder adds the three named templates if absent,
preserving existing templates and edits. Run the additive PMS migration
`0049_prescription_templates` before starting the updated application. It creates
the shared prescription library and does not alter patient documents or R4.
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
- Full backend suite on a fresh synthetic database: **707 passed, 2 skipped**.
- Focused prescription/template/document reliability suite: **18 passed** using
  `docker compose exec -T backend pytest -q tests/attachments/test_prescription_templates.py tests/attachments/test_prescription_entry.py tests/attachments/test_document_reliability.py`.
- Seven document/template browser checks: **7 passed** using:

```sh
set -a
. ./.env
set +a
cd frontend
PLAYWRIGHT_HTML_OUTPUT_DIR=../.run/library-browser-report-2 \
npx playwright test tests/prescription-templates.spec.ts \
  tests/patient-prescription-entry.spec.ts tests/templates-save.spec.ts \
  tests/patient-document-preview.spec.ts tests/patient-document-save.spec.ts \
  --workers=1 --output=../.run/library-browser-2
```

The networkless print check rendered all three defaults with synthetic details:
one page each, no unknown placeholders, and all entered prescription values and
the final manufacturer field present in extracted PDF text. Long unbroken text
also has unit coverage for printable width. Receipts are in the isolated
worktree's ignored `.run/` directory: `prescription-library-full.log`,
`prescription-library-verify.log`, `prescription-library-api.log`,
`prescription-library-browser-2.log` and `template-print-check.log`.
The library tests cover persistence, editing, activation, permissions, audit
metadata, patient-specific overrides and saved-document preservation.

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
During the library extension an initial browser request overlapped restarting
the isolated backend to load its new routes; six checks passed and that request
failed. The rerun after startup passed all seven checks.
