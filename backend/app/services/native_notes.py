"""Shared revision and request guarantees for native notes only."""
from datetime import datetime, timezone
import hashlib
import json

from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models.clinical_note import ClinicalNoteTemplate, NativeNoteRevision, NoteMutationReceipt
from app.models.audit_log import AuditLog
from app.models.note import Note
from app.models.user import User
from app.services.capabilities import get_user_capabilities

METADATA_FIELDS = ("clinical_date", "category", "template_id", "template_revision", "codes")


def creation_metadata(db: Session, payload, user: User) -> dict:
    values = {field: getattr(payload, field) for field in METADATA_FIELDS}
    if payload.template_id is not None:
        if "notes.view" not in {cap.code for cap in get_user_capabilities(db, user.id)}:
            raise HTTPException(403, "Note template access required")
        template = db.get(ClinicalNoteTemplate, payload.template_id)
        if template is None:
            raise HTTPException(404, "Note template not found")
        if not template.is_active or template.revision != payload.template_revision:
            raise HTTPException(409, "Template changed or is inactive; review the current template before saving")
        if "codes" in payload.model_fields_set and payload.codes != template.codes:
            raise HTTPException(422, "Template code labels must match the selected revision")
        values["codes"] = list(template.codes)
    return values


def request_fingerprint(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode()).hexdigest()


def replay_target(db: Session, user_id: int, request_id: str | None, action: str, payload: dict) -> int | None:
    if not request_id:
        return None
    # Serialize only the same actor/request key, including calls to different
    # native-note endpoints. No global write lock and no clinical text in audit.
    lock_key = int.from_bytes(hashlib.sha256(f"native-notes:{user_id}:{request_id}".encode()).digest()[:8], "big", signed=True)
    db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock_key})
    receipt = db.scalar(select(NoteMutationReceipt).where(NoteMutationReceipt.actor_user_id == user_id, NoteMutationReceipt.request_id == request_id))
    if receipt is None:
        historical = db.scalar(select(AuditLog.id).where(
            AuditLog.actor_user_id == user_id, AuditLog.request_id == request_id,
            AuditLog.action.in_(("note.created", "note.updated", "note.archived", "note.restored", "clinical.tooth_note.created", "clinical.tooth_note.updated",
                                "clinical_note_template.created", "clinical_note_template.updated")),
        ).limit(1))
        if historical is not None:
            # Old audit records did not keep an immutable request fingerprint.
            # Do not guess the original payload or create a duplicate on retry.
            raise HTTPException(409, "An earlier note request used this Request-Id; review the existing record")
        return None
    if receipt.action != action or receipt.fingerprint != request_fingerprint(payload):
        raise HTTPException(409, "Request-Id was already used for a different note operation")
    return receipt.target_id


def record_receipt(db: Session, user_id: int, request_id: str | None, action: str, payload: dict, target_id: int):
    if request_id:
        db.add(NoteMutationReceipt(actor_user_id=user_id, request_id=request_id, action=action, fingerprint=request_fingerprint(payload), target_id=target_id))


def snapshot(note) -> dict:
    values = {field: getattr(note, field) for field in METADATA_FIELDS}
    values["clinical_date"] = values["clinical_date"].isoformat() if values["clinical_date"] else None
    values.update(body=note.body if isinstance(note, Note) else note.note,
                  note_type=note.note_type.value if isinstance(note, Note) else None,
                  archived=note.deleted_at is not None if isinstance(note, Note) else False,
                  deleted_at=note.deleted_at.isoformat() if isinstance(note, Note) and note.deleted_at else None)
    return values


def source_filter(note):
    return NativeNoteRevision.note_id == note.id if isinstance(note, Note) else NativeNoteRevision.tooth_note_id == note.id


def save_snapshot(db: Session, note, actor_id: int | None, *, reason: str | None = None, baseline=False, recorded_at=None):
    row = NativeNoteRevision(
        note_id=note.id if isinstance(note, Note) else None,
        tooth_note_id=None if isinstance(note, Note) else note.id,
        revision=note.revision,
        snapshot=snapshot(note),
        recorded_by_user_id=actor_id,
        reason=reason,
        baseline=baseline,
        recorded_at=recorded_at or datetime.now(timezone.utc),
    )
    db.add(row)
    return row


def ensure_baseline(db: Session, note):
    if db.scalar(select(NativeNoteRevision.id).where(source_filter(note), NativeNoteRevision.revision == note.revision)) is None:
        # For pre-feature content we only know the latest stored value; capture
        # it verbatim and label it, rather than inventing old authors or edits.
        actor_id = note.updated_by_user_id if isinstance(note, Note) else note.created_by_user_id
        save_snapshot(db, note, actor_id, baseline=True,
                      recorded_at=(note.updated_at if isinstance(note, Note) else note.created_at))


def check_revision(note, expected: int | None):
    if expected is not None and note.revision != expected:
        raise HTTPException(409, "Note changed; reload and review before amending")


def history(db: Session, note, *, limit=100, before_revision=None):
    query = select(NativeNoteRevision).where(source_filter(note))
    if before_revision is not None:
        query = query.where(NativeNoteRevision.revision < before_revision)
    rows = list(db.scalars(query.order_by(NativeNoteRevision.revision.desc()).limit(limit + 1)))
    if not rows and before_revision is None:
        actor = note.updated_by if isinstance(note, Note) else note.created_by
        return {"items": [{**snapshot(note), "revision": note.revision,
                           "recorded_at": note.updated_at if isinstance(note, Note) else note.created_at,
                           "recorded_by": {"id": actor.id, "name": actor.full_name} if actor else None,
                           "reason": None, "baseline": True}], "next_before_revision": None}
    return {"items": [{**row.snapshot, "revision": row.revision, "recorded_at": row.recorded_at,
                       "recorded_by": {"id": row.recorded_by.id, "name": row.recorded_by.full_name} if row.recorded_by else None,
                       "reason": row.reason, "baseline": row.baseline} for row in rows[:limit]],
            "next_before_revision": rows[limit - 1].revision if len(rows) > limit else None}
