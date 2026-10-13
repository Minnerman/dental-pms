from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import require_capabilities, require_roles
from app.models.prescription_template import PrescriptionTemplate
from app.models.user import User
from app.schemas.prescription_template import (
    PrescriptionTemplateOut,
    PrescriptionTemplateWrite,
)
from app.services.audit import log_event

router = APIRouter(prefix="/prescription-templates", tags=["prescription-templates"])


def audit_data(template: PrescriptionTemplate) -> dict:
    return {"name": template.name, "is_active": template.is_active}


@router.get("", response_model=list[PrescriptionTemplateOut])
def list_templates(
    db: Session = Depends(get_db),
    _user: User = Depends(require_capabilities("documents.download")),
    include_inactive: bool = Query(default=False),
):
    stmt = select(PrescriptionTemplate)
    if not include_inactive:
        stmt = stmt.where(PrescriptionTemplate.is_active.is_(True))
    return list(db.scalars(stmt.order_by(PrescriptionTemplate.name, PrescriptionTemplate.id)))


@router.post("", response_model=PrescriptionTemplateOut, status_code=status.HTTP_201_CREATED)
def create_template(
    payload: PrescriptionTemplateWrite,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("superadmin")),
):
    template = PrescriptionTemplate(
        **payload.model_dump(), created_by_user_id=user.id, updated_by_user_id=user.id
    )
    db.add(template)
    db.flush()
    log_event(
        db, actor=user, action="prescription_template.created",
        entity_type="prescription_template", entity_id=str(template.id),
        after_data=audit_data(template), ip_address=request.client.host if request.client else None,
    )
    db.commit()
    db.refresh(template)
    return template


@router.put("/{template_id}", response_model=PrescriptionTemplateOut)
def update_template(
    template_id: int,
    payload: PrescriptionTemplateWrite,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("superadmin")),
):
    template = db.get(PrescriptionTemplate, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Prescription template not found")
    before = audit_data(template)
    for field, value in payload.model_dump().items():
        setattr(template, field, value)
    template.updated_by_user_id = user.id
    log_event(
        db, actor=user, action="prescription_template.updated",
        entity_type="prescription_template", entity_id=str(template.id),
        before_data=before, after_data=audit_data(template),
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    db.refresh(template)
    return template
