from datetime import date
from app.models.document_template import DocumentTemplateKind
from app.services.document_render import PLACEHOLDER_PATTERN
from app.services.document_templates import RECALL_TEMPLATE_SIX_MONTHS, RECALL_TEMPLATE_TWELVE_MONTHS
from app.services.pdf_documents import generate_patient_document_pdf
from app.services.practice_profile import load_profile


def freeze_document(db, document, patient, template, unknown_fields):
    document.document_kind = (
        "prescription" if template.kind == DocumentTemplateKind.prescription else
        "recall" if template.name in (RECALL_TEMPLATE_SIX_MONTHS, RECALL_TEMPLATE_TWELVE_MONTHS) else "letter"
    )
    blockers = []
    if unknown_fields:
        blockers.append("Resolve the unknown merge fields and create a new document")
    if document.document_kind == "prescription":
        if not (patient.address_line1 or "").strip() or not (patient.postcode or "").strip():
            blockers.append("Complete the patient's address and postcode, then create a new prescription")
        if not patient.date_of_birth or patient.date_of_birth > date.today():
            blockers.append("Complete a valid patient date of birth, then create a new prescription")
        fields = {m.group(1).strip() for m in PLACEHOLDER_PATTERN.finditer(template.content)}
        required = {"patient.full_name", "patient.address", "patient.dob", "patient.age", "today"}
        required |= {"prescription." + k for k in ("medicine", "directions", "quantity", "prescriber_name", "prescriber_gdc")}
        if not required <= fields or "signature" not in template.content.lower():
            blockers.append("Use a prescription layout with patient name, address, DOB, age, date and signature space")
    document.issue_blockers = blockers
    document.frozen_pdf = generate_patient_document_pdf(
        patient, document.title, document.rendered_content, load_profile(db)
    )
