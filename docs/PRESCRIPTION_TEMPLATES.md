# Prescription and recall template handover

The agreed scope is three reusable document layouts: **Private Prescription -
typed**, **Recall - 6 months**, and **Recall - 12 months**. Historical records
stay in R4/archive. No historical import or R4 connection is part of this change.

## Practice favourites

**Templates → Prescriptions** manages the shared library. Superadmins can add,
edit, deactivate and reactivate entries. Selecting one in a patient's Documents
view copies its values into an editable prescription without changing the library.
Nine owner-requested favourites are supplied:

| Medicine | Directions | Quantity |
| --- | --- | --- |
| Amoxicillin 250 mg capsules | One capsule three times a day | 21 capsules |
| Amoxicillin 500 mg capsules | One capsule three times a day | 21 capsules |
| Amoxicillin 250 mg/5 mL oral suspension (sugar free) | 5 mL three times a day | Enter total supply in mL |
| Amoxicillin 500 mg/5 mL oral suspension | 5 mL three times a day | Enter total supply in mL |
| Metronidazole 200 mg tablets | One tablet three times a day | 21 tablets |
| Metronidazole 400 mg tablets | One tablet three times a day | 21 tablets |
| Erythromycin 250 mg tablets | One tablet four times a day | 28 tablets |
| Clindamycin 150 mg capsules | One capsule every six hours | Enter for each prescription |
| Clindamycin 300 mg capsules | One capsule every six hours | Enter for each prescription |

Clindamycin quantities were not supplied, so neither is inferred. A library
quantity can be blank; a patient prescription cannot be saved without quantity.
The liquid dose was explicitly confirmed as 5 mL three times a day for both
strengths. Concentration and dose volume are distinct: 5 mL of these formulations
contains 250 mg or 500 mg respectively. Total supply has no default and remains
required for each patient. The form prompts for the total volume in mL. The
250 mg/5 mL favourite specifies sugar free; the 500 mg/5 mL favourite does not
assume this product attribute. Strength/form references:
[250 mg/5 mL manufacturer information](https://www.medicines.org.uk/emc/product/10891/smpc) and
[500 mg/5 mL manufacturer information](https://www.medicines.org.uk/emc/product/12494/smpc).
Startup uses stable stock keys, preserving renamed, edited or deactivated entries.

These are practice favourites, not recommended antibiotic courses. The owner’s
quantities are retained. Current [SDCEP amoxicillin guidance](https://sdcepdentalprescribing.nhs.scot/guidance/bacterial-infections/dental-abscess/first-line-antibiotics/amoxicillin/)
describes shorter courses for dental abscess than the seven days implied by 21
capsules at three per day; the clinician must choose the regimen for the patient.

## Print and clinical notes

1. Open the patient's **Documents**, choose the prescription or recall layout,
   and complete its fields. Prescriptions require medicine, directions, quantity,
   prescriber name and GDC number. Review the patient details and preview.
2. **Save document** stores its text and complete PDF, including its header and
   date. Later template, patient or practice-profile changes cannot alter that PDF.
3. Select **Print & record**. Review the saved PDF and choose **Print PDF**.
   If the browser cannot display an embedded PDF, open or download the saved
   copy using the links on this screen and print it with a PDF reader.
4. After printing succeeds, select **Printed — add clinical note**. This creates
   one clinical note linked to that exact copy. If printing is cancelled, leave
   without confirming. A browser cannot verify physical printer output.
5. The entry is clickable in patient Notes, the clinical notes pane, and central
   Notes. Reopening it creates no new note. Prescription copies are before the
   handwritten signature; print and sign in ink.

Print confirmation is idempotent, including concurrent duplicate requests.
Deleting the source generated document does not delete issued copies. These
clinical entries cannot be edited or archived; add a separate correction note.
A separate later print preparation can record another print. Plain PDF/text
**Download** and attachment actions do not claim printing occurred.

The two recall layouts are used from Documents. They do not choose the patient's
recall interval, calculate due dates, or replace the separate recall-dashboard
batch/download workflow.

## Prescription writing

The format follows the fields in [SDCEP's prescription-writing guide](https://www.sdcepdentalprescribing.nhs.scot/guidance/introduction/prescription-writing/guide-to-prescription-writing/):
patient title (where recorded), full name and all saved address lines including
postcode, DOB and age, date, practice address, medicine name/form/
strength, explicit directions, quantity, and a space for the ink signature.
Dentist name and GDC number are also included. The approved generic spelling
**amoxicillin** is used; T.D.S./Q.D.S. are expanded into English. Medicine forms
were checked against SDCEP and manufacturer information, including
[erythromycin](https://www.medicines.org.uk/emc/product/502/smpc) and
[clindamycin](https://www.medicines.org.uk/emc/product/11663/smpc).

The app checks required text, patient DOB/address and required layout fields
before preparing a prescription for printing. It does not validate clinical
suitability, allergy/interactions, dosing or registration. Existing custom
layouts are preserved; only the exact untouched stock prescription layout is
updated to include age. Longer documents wrap and repeat patient identity on
continuation pages. This is a private prescription, not an NHS FP10 form or an
electronic signature.

## Recall email: prepared, switched off

The owner requested printing only for now. `RECALL_EMAIL_ENABLED=false` is the
default; the UI displays **Email recall (off)** and the backend rejects sends.
The planned sender is `clinicforimplant@gmail.com`. No credentials were configured
and no actual email was sent during development.

For a later explicitly requested activation, configure the SMTP variables in
`.env.example` through the server's secure configuration. Both username and
password are required. The transport requires STARTTLS (normally port 587) or
implicit TLS (`SMTP_SSL=true`, normally port 465); there is no plaintext fallback.
Do not put credentials in source control or chat. Test with a synthetic recipient
before switching on for practice use.

When enabled, only saved 6/12-month recall documents can prepare an email. Staff
review the sender, patient recipient and exact PDF before sending. Prescription
email is rejected on the server as well as absent from the UI. A changed email
address requires a new preparation. A clinical note is created only after the
mail server accepts the message; that is not confirmation of inbox delivery.

The app durably marks sending before contacting SMTP. A timeout, process crash,
or database failure after SMTP acceptance must not trigger an automatic resend.
Such records stay `sending`/`uncertain`, with no success note. Check the mail
provider before deliberately preparing another copy. There is no automatic
reconciliation or delivery/bounce tracking in this slice.

## Installation and preservation

Apply Alembic through `0050_document_copies` before starting this version:
`0049_prescription_templates` creates the library; `0050_document_copies` adds
stock keys, PDF snapshots, issued copies and note links. PDFs are stored in the
PMS PostgreSQL database and are included in its backups. R4 is untouched.

Older generated documents without a complete frozen PDF remain downloadable,
but require a new template-generated document for this print/email workflow.
They are not backfilled by guessing historical headers or prescription details.
Normal capability checks apply: viewing copies requires `documents.download`
and `notes.view`; recording also requires `notes.write`. Archived patients are
unavailable. PDF retrieval is audited and returned with `Cache-Control: no-store`.

This branch is not deployed. Review/merge and a separate deployment instruction
are still required. Check practice settings and a synthetic paper print on the
practice printer before using the feature with patients.

## Verification receipts

The isolated worktree is `/home/amir/dental-pms-prescription-entry`, Compose project
`dental_prescription_entry`, with separate synthetic database/storage and loopback
ports 8187/3187. Commands and final results are recorded in `docs/STATUS.md`.

Latest extension: 722 backend tests passed, 2 skipped; health and verify passed;
3 focused browser checks passed with `tests/document-print-record.spec.ts`. The
prior broader browser command below passed all 9 checks before the liquid addition.
The two new liquid API cases and prescription suite passed 20 checks; the external
API copy run passed 14 checks before the whitespace-address case was added to the
final full run. Receipts use the ignored `.run/liquid-prescription-*.log` paths.

```sh
cd /home/amir/dental-pms-prescription-entry
bash ops/health.sh
SKIP_DOCKER_BUILD=1 bash ops/verify.sh
docker compose exec -T backend pytest -q

set -a
. ./.env
set +a
cd frontend
PLAYWRIGHT_HTML_OUTPUT_DIR=../.run/document-copy-browser-final-report \
npx playwright test tests/document-print-record.spec.ts \
  tests/patient-prescription-entry.spec.ts tests/prescription-templates.spec.ts \
  tests/templates-save.spec.ts tests/patient-document-preview.spec.ts \
  tests/patient-document-save.spec.ts --workers=1 \
  --output=../.run/document-copy-browser-final
```

`SKIP_DOCKER_BUILD=1` reuses dependency images with current source mounted; verify
still runs the production frontend build/typecheck, migrations and service checks.
Browser tests exercise cancellation, print confirmation, clinical-note links,
PDF byte identity and required Clindamycin quantities. API coverage includes
concurrent replay, source deletion, permissions, archive guards, immutable copies,
disabled emailing, simulated successful/uncertain sending, and TLS attachment
construction. A synthetic one-page liquid prescription PDF was visually inspected, including
all patient address lines, title, full name and prescriber details. Existing saved
PDFs remain unchanged when this display-name improvement is installed. No new
migration is required beyond `0050_document_copies`; startup adds the two liquids.

Email simulations use an in-process test client so their mocked transport also
works when CI points ordinary API tests at a separately running backend. The
external-API check passed; no SMTP configuration was enabled on that server.
