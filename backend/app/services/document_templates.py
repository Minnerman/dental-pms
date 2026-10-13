from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document_template import DocumentTemplate, DocumentTemplateKind
from app.models.user import User


RECALL_TEMPLATE_ROUTINE = "Recall Letter – Routine Examination"
RECALL_TEMPLATE_OVERDUE = "Recall Letter – Overdue Reminder"
PRESCRIPTION_TEMPLATE = "Private Prescription - typed"
RECALL_TEMPLATE_SIX_MONTHS = "Recall - 6 months"
RECALL_TEMPLATE_TWELVE_MONTHS = "Recall - 12 months"

PRESCRIPTION_CONTENT = (
    "Date: {{today}}\n\n"
    "Patient: {{patient.full_name}}\n"
    "Date of birth: {{patient.dob}}\n"
    "Age: {{patient.age}}\n"
    "Address: {{patient.address}}\n\n"
    "Dentist: {{prescription.prescriber_name}}\n"
    "GDC number: {{prescription.prescriber_gdc}}\n\n"
    "Medicine name, strength and form:\n{{prescription.medicine}}\n\n"
    "Directions for use:\n{{prescription.directions}}\n\n"
    "Quantity: {{prescription.quantity}}\n\n"
    "Prescriber's signature: ________________________________\n\n"
    "Practice stamp:\n\n\n"
    "If dispensed in practice:\n"
    "Batch number: _________________________________________\n"
    "Manufacturer: _________________________________________\n"
)


def recall_content(interval: str) -> str:
    return (
        "{{today}}\n\n{{patient.full_name}}\n{{patient.address}}\n\n"
        "Dear {{patient.first_name}},\n\n"
        f"Our records show that your {interval} dental recall is now due.\n"
        "Please contact the practice to arrange an appointment.\n\n"
        "If you have already booked, please disregard this reminder.\n\n"
        "When you attend, please let us know about any changes to your health\n"
        "or medication since your last visit.\n\n"
        "{{practice.phone}}\nWebsite: {{practice.website}}\n\n"
        "Yours sincerely,\n{{practice.name}}\n"
    )


def _template_exists(db: Session, *, name: str, kind: DocumentTemplateKind) -> bool:
    return db.scalar(
        select(DocumentTemplate.id).where(
            DocumentTemplate.name == name,
            DocumentTemplate.kind == kind,
        )
    ) is not None


def ensure_default_templates(db: Session, *, actor: User) -> int:
    defaults = [
        {
            "name": PRESCRIPTION_TEMPLATE,
            "kind": DocumentTemplateKind.prescription,
            "content": PRESCRIPTION_CONTENT,
        },
        {
            "name": RECALL_TEMPLATE_SIX_MONTHS,
            "kind": DocumentTemplateKind.letter,
            "content": recall_content("six-month"),
        },
        {
            "name": RECALL_TEMPLATE_TWELVE_MONTHS,
            "kind": DocumentTemplateKind.letter,
            "content": recall_content("twelve-month"),
        },
        {
            "name": RECALL_TEMPLATE_ROUTINE,
            "kind": DocumentTemplateKind.letter,
            "content": (
                "{{today}}\n"
                "{{patient.first_name}} {{patient.last_name}}\n"
                "{{patient.address}}\n\n"
                "Dear {{patient.first_name}},\n\n"
                "Our records show you are due for a routine dental examination on "
                "{{recall.due_date}}.\n"
                "Please contact the practice to arrange an appointment.\n\n"
                "If you have already booked, please ignore this reminder.\n\n"
                "You can reach us on {{practice.phone}} or visit {{practice.website}}.\n\n"
                "Kind regards,\n"
                "{{practice.name}}\n"
            ),
        },
        {
            "name": RECALL_TEMPLATE_OVERDUE,
            "kind": DocumentTemplateKind.letter,
            "content": (
                "{{today}}\n"
                "{{patient.first_name}} {{patient.last_name}}\n"
                "{{patient.address}}\n\n"
                "Dear {{patient.first_name}},\n\n"
                "Our records show your dental recall is overdue. "
                "Your last due date was {{recall.due_date}}.\n"
                "Please contact the practice to arrange an appointment at your earliest convenience.\n\n"
                "If you have already booked, please ignore this reminder.\n\n"
                "You can reach us on {{practice.phone}} or visit {{practice.website}}.\n\n"
                "Kind regards,\n"
                "{{practice.name}}\n"
            ),
        },
    ]

    stock = db.scalar(select(DocumentTemplate).where(DocumentTemplate.name == PRESCRIPTION_TEMPLATE))
    if stock and stock.content == PRESCRIPTION_CONTENT.replace("Age: {{patient.age}}\n", ""):
        stock.content = PRESCRIPTION_CONTENT
        db.commit()
    created = 0
    for template in defaults:
        if _template_exists(db, name=template["name"], kind=template["kind"]):
            continue
        db.add(
            DocumentTemplate(
                name=template["name"],
                kind=template["kind"],
                content=template["content"],
                is_active=True,
                created_by_user_id=actor.id,
                updated_by_user_id=actor.id,
            )
        )
        created += 1

    if created:
        db.commit()
    return created
