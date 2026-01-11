from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document_template import DocumentTemplate, DocumentTemplateKind
from app.models.user import User


RECALL_TEMPLATE_ROUTINE = "Recall Letter – Routine Examination"
RECALL_TEMPLATE_OVERDUE = "Recall Letter – Overdue Reminder"


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
