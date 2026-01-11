from __future__ import annotations

import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
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
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("superadmin")),
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
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("superadmin")),
):
    template = get_template_or_404(db, template_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(template, field, value)
    template.updated_by_user_id = user.id
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


@router.delete("/{template_id}", response_model=DocumentTemplateOut)
def delete_document_template(
    template_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("superadmin")),
):
    template = get_template_or_404(db, template_id, include_deleted=True)
    if template.deleted_at is not None:
        return template
    template.deleted_at = datetime.now(timezone.utc)
    template.deleted_by_user_id = user.id
    template.updated_by_user_id = user.id
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


@router.get("/{template_id}/download")
def download_document_template(
    template_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    template = get_template_or_404(db, template_id)
    safe_name = sanitize_filename(template.name)
    filename = f"{safe_name}-{template.kind.value}.txt"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=template.content, media_type="text/plain", headers=headers)
