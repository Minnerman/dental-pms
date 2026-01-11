from __future__ import annotations

import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import get_current_user, require_roles
from app.models.document_template import DocumentTemplate, DocumentTemplateKind
from app.models.user import User
from app.schemas.document_template import (
    DocumentTemplateCreate,
    DocumentTemplateOut,
    DocumentTemplateUpdate,
)
from app.services.audit import log_event

router = APIRouter(prefix="/document-templates", tags=["document-templates"])


def sanitize_filename(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_")
    return cleaned or "template"


def get_template_or_404(
    db: Session, template_id: int, *, include_deleted: bool = False
) -> DocumentTemplate:
    template = db.get(DocumentTemplate, template_id)
    if not template or (template.deleted_at is not None and not include_deleted):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document template not found",
        )
    return template


def template_audit_payload(template: DocumentTemplate) -> dict:
    return {
        "name": template.name,
        "kind": template.kind.value if template.kind else None,
        "is_active": template.is_active,
    }


@router.get("", response_model=list[DocumentTemplateOut])
def list_document_templates(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    kind: DocumentTemplateKind | None = Query(default=None),
    include_inactive: bool = Query(default=False),
):
    stmt = select(DocumentTemplate).where(DocumentTemplate.deleted_at.is_(None))
    if kind is not None:
        stmt = stmt.where(DocumentTemplate.kind == kind)
    if not include_inactive:
        stmt = stmt.where(DocumentTemplate.is_active.is_(True))
    stmt = stmt.order_by(DocumentTemplate.name)
    return list(db.scalars(stmt))


@router.post("", response_model=DocumentTemplateOut, status_code=status.HTTP_201_CREATED)
def create_document_template(
    payload: DocumentTemplateCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("superadmin")),
    request_id: str | None = Header(default=None),
):
    template = DocumentTemplate(
        name=payload.name,
        kind=payload.kind,
        content=payload.content,
        is_active=payload.is_active,
        created_by_user_id=user.id,
        updated_by_user_id=user.id,
    )
    db.add(template)
    db.flush()
    log_event(
        db,
        actor=user,
        action="document_template.created",
        entity_type="document_template",
        entity_id=str(template.id),
        after_data=template_audit_payload(template),
        request_id=request_id,
        ip_address=request.client.host if request else None,
    )
    db.commit()
    db.refresh(template)
    return template


@router.get("/{template_id}", response_model=DocumentTemplateOut)
def get_document_template(
    template_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return get_template_or_404(db, template_id)


@router.patch("/{template_id}", response_model=DocumentTemplateOut)
def update_document_template(
    template_id: int,
    payload: DocumentTemplateUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("superadmin")),
    request_id: str | None = Header(default=None),
):
    template = get_template_or_404(db, template_id)
    before_data = template_audit_payload(template)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(template, field, value)
    template.updated_by_user_id = user.id
    db.add(template)
    log_event(
        db,
        actor=user,
        action="document_template.updated",
        entity_type="document_template",
        entity_id=str(template.id),
        before_data=before_data,
        after_data=template_audit_payload(template),
        request_id=request_id,
        ip_address=request.client.host if request else None,
    )
    db.commit()
    db.refresh(template)
    return template


@router.delete("/{template_id}", response_model=DocumentTemplateOut)
def delete_document_template(
    template_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("superadmin")),
    request_id: str | None = Header(default=None),
):
    template = get_template_or_404(db, template_id, include_deleted=True)
    if template.deleted_at is not None:
        return template
    before_data = template_audit_payload(template)
    template.deleted_at = datetime.now(timezone.utc)
    template.deleted_by_user_id = user.id
    template.updated_by_user_id = user.id
    db.add(template)
    log_event(
        db,
        actor=user,
        action="document_template.deleted",
        entity_type="document_template",
        entity_id=str(template.id),
        before_data=before_data,
        after_data=template_audit_payload(template),
        request_id=request_id,
        ip_address=request.client.host if request else None,
    )
    db.commit()
    db.refresh(template)
    return template


@router.get("/{template_id}/download")
def download_document_template(
    template_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    request_id: str | None = Header(default=None),
):
    template = get_template_or_404(db, template_id)
    safe_name = sanitize_filename(template.name)
    filename = f"{safe_name}-{template.kind.value}.txt"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    log_event(
        db,
        actor=user,
        action="document_template.downloaded",
        entity_type="document_template",
        entity_id=str(template.id),
        after_data={"filename": filename},
        request_id=request_id,
        ip_address=request.client.host if request else None,
    )
    db.commit()
    return Response(content=template.content, media_type="text/plain", headers=headers)
