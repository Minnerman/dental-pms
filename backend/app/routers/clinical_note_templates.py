from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import require_capability
from app.models.clinical_note import ClinicalNoteTemplate, ClinicalNoteTemplateRevision
from app.models.user import User
from app.schemas.clinical_note import ClinicalNoteTemplateCreate, ClinicalNoteTemplateOut, ClinicalNoteTemplateUpdate
from app.services.audit import log_event
from app.services.native_notes import record_receipt, replay_target

router = APIRouter(prefix="/clinical-note-templates", tags=["clinical-note-templates"])
VIEW = require_capability("notes.view")
WRITE = require_capability("notes.write")
FIELDS = ("title", "category", "body", "fields", "codes", "is_active")


def _snapshot(row):
    return {key: getattr(row, key) for key in FIELDS}


def _get(db, template_id, *, lock=False):
    stmt = select(ClinicalNoteTemplate).where(ClinicalNoteTemplate.id == template_id)
    if lock:
        stmt = stmt.with_for_update(of=ClinicalNoteTemplate)
    row = db.scalar(stmt)
    if row is None:
        raise HTTPException(404, "Note template not found")
    return row


def _revision(db, row, user):
    db.add(ClinicalNoteTemplateRevision(template_id=row.id, revision=row.revision, snapshot=_snapshot(row), recorded_by_user_id=user.id))


@router.get("", response_model=list[ClinicalNoteTemplateOut])
def list_templates(
    db: Session = Depends(get_db), _user: User = Depends(VIEW),
    include_inactive: bool = Query(False), limit: int = Query(200, ge=1, le=200), offset: int = Query(0, ge=0),
):
    stmt = select(ClinicalNoteTemplate)
    if not include_inactive:
        stmt = stmt.where(ClinicalNoteTemplate.is_active.is_(True))
    return list(db.scalars(stmt.order_by(ClinicalNoteTemplate.title, ClinicalNoteTemplate.id).limit(limit).offset(offset)))


@router.post("", response_model=ClinicalNoteTemplateOut, status_code=201)
def create_template(
    payload: ClinicalNoteTemplateCreate, db: Session = Depends(get_db),
    user: User = Depends(WRITE), _viewer: User = Depends(VIEW),
    request_id: str | None = Header(default=None, max_length=120),
):
    values = payload.model_dump(mode="json")
    action = "clinical_note_template.created"
    duplicate_id = replay_target(db, user.id, request_id, action, values)
    if duplicate_id is not None:
        return _get(db, duplicate_id)
    row = ClinicalNoteTemplate(**values, created_by_user_id=user.id, updated_by_user_id=user.id)
    db.add(row)
    db.flush()
    _revision(db, row, user)
    record_receipt(db, user.id, request_id, action, values, row.id)
    log_event(db, actor=user, action=action, entity_type="clinical_note_template", entity_id=str(row.id), request_id=request_id,
              after_data={"template_id": row.id, "revision": row.revision, "category": row.category, "is_active": row.is_active})
    db.commit()
    db.refresh(row)
    return row


@router.patch("/{template_id}", response_model=ClinicalNoteTemplateOut)
def update_template(
    template_id: int, payload: ClinicalNoteTemplateUpdate, db: Session = Depends(get_db),
    user: User = Depends(WRITE), _viewer: User = Depends(VIEW),
    request_id: str | None = Header(default=None, max_length=120),
):
    row = _get(db, template_id, lock=True)
    request_values = {"template_id": template_id, **payload.model_dump(mode="json", exclude_unset=True)}
    action = "clinical_note_template.updated"
    if replay_target(db, user.id, request_id, action, request_values) is not None:
        return row
    if row.revision != payload.expected_revision:
        raise HTTPException(409, "Template changed; reload before editing")
    values = {**_snapshot(row), **payload.model_dump(mode="json", exclude_unset=True, exclude={"expected_revision"})}
    try:
        values = ClinicalNoteTemplateCreate.model_validate(values).model_dump(mode="json")
    except ValidationError:
        raise HTTPException(422, "Template fields, codes or placeholders are invalid") from None
    changed = [field for field in FIELDS if getattr(row, field) != values[field]]
    if changed:
        before = {"template_id": row.id, "revision": row.revision}
        for field in changed:
            setattr(row, field, values[field])
        row.revision += 1
        row.updated_by_user_id = user.id
        _revision(db, row, user)
        log_event(db, actor=user, action=action, entity_type="clinical_note_template", entity_id=str(row.id), request_id=request_id,
                  before_data=before, after_data={"template_id": row.id, "revision": row.revision, "changed_fields": sorted(changed)})
    record_receipt(db, user.id, request_id, action, request_values, row.id)
    db.commit()
    db.refresh(row)
    return row
