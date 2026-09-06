"""Read-only, permission-scoped projections of existing PostgreSQL records.

Every source applies search and keyset pagination in SQL before LIMIT. No R4
connection, import, write, template expansion, or historical status inference.
"""
from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import DateTime, String, and_, case, cast, exists, false, func, literal, or_, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from app.core.settings import settings
from app.models.audit_log import AuditLog
from app.models.appointment import Appointment
from app.models.capability import Capability, UserCapability
from app.models.clinical import Procedure, ToothNote, TreatmentPlanItem
from app.models.clinical_note import NativeNoteRevision
from app.models.note import Note
from app.models.patient import Patient
from app.models.patient_document import PatientDocument
from app.models.patient_recall_communication import PatientRecallCommunication
from app.models.r4_charting import R4OldPatientNote, R4PatientNote, R4TemporaryNote, R4TreatmentNote
from app.models.r4_charting_canonical import R4ChartingCanonicalRecord
from app.models.r4_patient_mapping import R4PatientMapping
from app.models.r4_user import R4User
from app.models.user import Role, User
from app.schemas.clinical_journal import (
    ClinicalJournalOut, JournalAuthor, JournalAvailability, JournalItem, JournalProvenance,
)

DIAGNOSIS_ACTIONS = {
    "clinical.tooth_conditions.recorded": "Tooth observations recorded",
    "clinical.root_conditions.recorded": "Root observations recorded",
    "clinical.crown_conditions.recorded": "Crown observations recorded",
    "clinical.surface_conditions.recorded": "Surface observations recorded",
    "clinical.bridge.created": "Bridge recorded",
    "clinical.bridge.reset": "Bridge observations reset",
}
CANONICAL_NOTE_DOMAINS = {
    "patient_note": "Imported patient note",
    "old_patient_note": "Imported historical patient note",
    "treatment_note": "Imported treatment note",
    "temporary_note": "Imported temporary note",
    "appointment_note": "Imported appointment note",
    "completed_questionnaire_note": "Imported questionnaire note",
}


def _utc(value):
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _value(value):
    return getattr(value, "value", value)


def _string(value):
    return None if value is None else str(value)


def _scope(patient_id, category, q, tooth, capabilities):
    data = [patient_id, category, q, tooth, sorted(capabilities), bool(settings.feature_charting_viewer)]
    return hashlib.sha256(json.dumps(data, ensure_ascii=False).encode()).hexdigest()


def _cursor_decode(raw, scope):
    if raw is None:
        return None
    try:
        payload = json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
        if payload["v"] != 1 or payload["scope"] != scope or not isinstance(payload["key"], str):
            raise ValueError
        stamp = payload["at"]
        parsed = _utc(datetime.fromisoformat(stamp)) if stamp is not None else None
        if not payload["key"] or len(payload["key"]) > 600:
            raise ValueError
        return parsed, payload["key"]
    except (ValueError, TypeError, KeyError, UnicodeError):
        raise HTTPException(422, "Invalid journal cursor for this patient or filter") from None


def _cursor_encode(stamp, key, scope):
    payload = {"v": 1, "at": stamp.isoformat() if stamp else None, "key": key, "scope": scope}
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")


def _note_category(column):
    return case((column.in_(["medical", "soft_tissue"]), "medical"),
                (column == "correspondence", "correspondence"), else_="notes")


def _audit_description(action, data):
    """Format exact stored observations, not an interpretation or completion event."""
    lines = []
    changed = data.get("changed_teeth")
    teeth = data.get("teeth") if isinstance(data.get("teeth"), dict) else {}
    names = changed if isinstance(changed, list) else list(teeth)
    fields = {
        "clinical.tooth_conditions.recorded": ("condition", "dentition", "movement", "rotation"),
        "clinical.root_conditions.recorded": ("root_observations",),
        "clinical.crown_conditions.recorded": ("crown_observation",),
        "clinical.surface_conditions.recorded": ("surface_observations",),
        "clinical.bridge.created": ("bridge_role", "crown_observation"),
        "clinical.bridge.reset": ("bridge_role", "crown_observation"),
    }.get(action, ())
    for tooth in names:
        observed = teeth.get(tooth)
        if not isinstance(observed, dict):
            continue
        descriptions = []
        for field in fields:
            if field not in observed:
                continue
            value = observed[field]
            rendered = "not recorded" if value is None else (
                json.dumps(value, ensure_ascii=False, sort_keys=True) if isinstance(value, (dict, list))
                else str(value).replace("_", " "))
            descriptions.append(f"{field.replace('_', ' ')}: {rendered}")
        lines.append(f"{tooth} — {'; '.join(descriptions)}")
    return "\n".join(lines) or "Recorded chart event; observation details were not stored."


def clinical_journal(db: Session, *, patient_id: int, user: User, limit=50, before=None,
                     category="all", q="", tooth=None) -> ClinicalJournalOut:
    capabilities = set(db.scalars(select(Capability.code).join(
        UserCapability, Capability.id == UserCapability.capability_id
    ).where(UserCapability.user_id == user.id)))
    if "patients.view" not in capabilities:
        raise HTTPException(403, "Forbidden")
    patient = db.get(Patient, patient_id)
    if patient is None or patient.deleted_at is not None:
        raise HTTPException(404, "Patient not found")
    clinical = "clinical.view" in capabilities
    imported = "forbidden" if not clinical or user.role == Role.external else (
        "available" if settings.feature_charting_viewer else "disabled")
    availability = JournalAvailability(
        notes="available" if "notes.view" in capabilities else "forbidden",
        clinical="available" if clinical else "forbidden",
        medical="available" if clinical else "forbidden",
        correspondence="available" if {"documents.download", "recalls.view"} & capabilities else "forbidden",
        documents="available" if "documents.download" in capabilities else "forbidden",
        recalls="available" if "recalls.view" in capabilities else "forbidden",
        imported=imported,
    )
    q = q.strip()
    scope = _scope(patient_id, category, q, tooth, capabilities)
    cursor = _cursor_decode(before, scope)
    candidates = []
    imported_authors = {}

    def rows(model, kind, stamp, predicates, body, source_category, *, tooth_expr=None, key=None,
             extra_search=()):
        # A source cannot contribute more than limit+1 candidates to the merged page.
        key = (key if key is not None else literal(kind + ":") + cast(model.id, String)).collate("C")
        stmt = select(model, stamp.label("journal_stamp"), key.label("journal_key")).where(*predicates)
        if category != "all":
            stmt = stmt.where(source_category == category)
        if tooth:
            stmt = stmt.where(tooth_expr == tooth if tooth_expr is not None else false())
        if q:
            # Literal substring matching: user '%' and '_' are not SQL wildcards.
            escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            stmt = stmt.where(or_(*(cast(expr, String).ilike(f"%{escaped}%", escape="\\")
                                    for expr in (body, *extra_search))))
        if cursor:
            cursor_stamp, cursor_key = cursor
            if cursor_stamp is None:
                stmt = stmt.where(stamp.is_(None), key < cursor_key)
            else:
                stmt = stmt.where(or_(stamp < cursor_stamp, stamp.is_(None),
                                      and_(stamp == cursor_stamp, key < cursor_key)))
        return db.execute(stmt.order_by(stamp.desc().nulls_last(), key.desc()).limit(limit + 1)).all()

    def add(row, stamp, key, kind, cat, title, **values):
        item = JournalItem(key=key, source_kind=kind, source_id=str(row.id),
                           category=cat, title=title, **values)
        candidates.append((_utc(stamp), key, item))
        return item

    # Native notes stay in their original tables. Latest content references its explicit revisions.
    for model, kind, capability, body_column, title in (
        (Note, "note", "notes.view", Note.body, "Clinical note"),
        (ToothNote, "tooth_note", "clinical.view", ToothNote.note, "Tooth note"),
    ):
        if capability not in capabilities:
            continue
        cat_expr = _note_category(model.category)
        stamp = func.coalesce(cast(model.clinical_date, DateTime()).op("AT TIME ZONE")("UTC"), model.created_at)
        predicates = [model.patient_id == patient_id]
        if model is Note:
            predicates.append(model.deleted_at.is_(None))
            # Match notes._safe_note_scope without querying or exposing unrelated appointments.
            predicates.append(or_(Note.appointment_id.is_(None), exists(select(Appointment.id).where(
                Appointment.id == Note.appointment_id, Appointment.patient_id == Note.patient_id,
                Appointment.deleted_at.is_(None)))))
        for row, at, key in rows(model, kind, stamp, predicates, body_column, cat_expr,
                                tooth_expr=model.tooth if model is ToothNote else None):
            cat = "medical" if row.category in {"medical", "soft_tissue"} else (
                "correspondence" if row.category == "correspondence" else "notes")
            history = (f"/notes/{row.id}/revisions" if model is Note else
                       f"/patients/{patient_id}/tooth-notes/{row.id}/revisions")
            add(row, at, key, kind, cat, title,
                body=row.body if model is Note else row.note,
                occurred_at=row.created_at, clinical_date=row.clinical_date,
                date_basis="clinical_date" if row.clinical_date else "recorded",
                author=JournalAuthor(user_id=row.created_by_user_id),
                tooth=row.tooth if model is ToothNote else None,
                surface=row.surface if model is ToothNote else None,
                revision=row.revision, can_edit=capability.replace(".view", ".write") in capabilities,
                history_url=history, link=f"/patients/{patient_id}/charting",
                details={"note_type": _value(row.note_type) if model is Note else None,
                         "note_category": row.category, "template_id": row.template_id,
                         "template_revision": row.template_revision, "codes": row.codes})

    if clinical:
        for model, kind, stamp, title in (
            (Procedure, "procedure", Procedure.performed_at, "Procedure"),
            (TreatmentPlanItem, "treatment_plan", TreatmentPlanItem.created_at, "Treatment plan item"),
        ):
            for row, at, key in rows(model, kind, stamp, [model.patient_id == patient_id],
                                    model.description, literal("treatment"), tooth_expr=model.tooth,
                                    extra_search=(model.procedure_code,)):
                add(row, at, key, kind, "treatment", title, body=row.description, occurred_at=at,
                    date_basis="source" if model is Procedure else "recorded",
                    author=JournalAuthor(user_id=row.created_by_user_id), tooth=row.tooth, surface=row.surface,
                    link=f"/patients/{patient_id}/charting",
                    details={"status": _value(row.status), "procedure_code": row.procedure_code,
                             **({"fee_pence": row.fee_pence} if "billing.view" in capabilities else {}),
                             "appointment_id": row.appointment_id})

        after = cast(AuditLog.after_json, JSONB)
        before_data = cast(AuditLog.before_json, JSONB)
        medical_after = after["medical_alerts"].astext
        medical_before = before_data["medical_alerts"].astext
        allergies_after = after["allergies"].astext
        allergies_before = before_data["allergies"].astext
        common = [AuditLog.entity_type == "patient", AuditLog.entity_id == str(patient_id)]
        audit_sources = (
            ("diagnosis", "diagnosis", AuditLog.action.in_(DIAGNOSIS_ACTIONS), cast(after["teeth"], String)),
            ("bpe", "medical", AuditLog.action.in_(["clinical.bpe.recorded", "clinical.bpe.cleared"]),
             cast(after["scores"], String)),
            ("medical_update", "medical", and_(AuditLog.action == "update",
                or_(medical_after.is_distinct_from(medical_before), allergies_after.is_distinct_from(allergies_before))),
                func.concat_ws("\n", medical_after, allergies_after)),
        )
        for kind, cat, allowed, body in audit_sources:
            # Diagnosis is a multi-tooth event: SQL membership, not a guessed single tooth.
            predicates = [*common, allowed]
            if tooth and kind == "diagnosis":
                predicates.append(after["teeth"].has_key(tooth))
            for row, at, key in rows(AuditLog, kind, AuditLog.created_at, predicates, body,
                                    literal(cat), tooth_expr=literal(tooth) if kind == "diagnosis" and tooth else None):
                data = row.after_json if isinstance(row.after_json, dict) else {}
                previous = row.before_json if isinstance(row.before_json, dict) else {}
                if kind == "diagnosis":
                    title = DIAGNOSIS_ACTIONS[row.action]
                    text = _audit_description(row.action, data)
                    details = {"action": row.action, "observations": data.get("teeth", {}),
                               "changed_teeth": data.get("changed_teeth", [])}
                    changed = data.get("changed_teeth", [])
                    target = changed[0] if isinstance(changed, list) and len(changed) == 1 else None
                elif kind == "bpe":
                    title = "BPE recorded" if row.action.endswith("recorded") else "BPE cleared"
                    text = " / ".join(str(score) for score in data.get("scores") or []) or "Scores cleared"
                    details = {"action": row.action, "scores": data.get("scores"),
                               "source_recorded_at": data.get("recorded_at")}
                    target = None
                else:
                    title, target = "Medical information updated", None
                    changes = {field: {"before": previous.get(field), "after": data.get(field)}
                               for field in ("medical_alerts", "allergies")
                               if previous.get(field) != data.get(field)}
                    text = "\n".join(f"{field.replace('_', ' ').capitalize()}: " +
                                     (values["after"] if isinstance(values["after"], str) else "Not recorded")
                                     for field, values in changes.items())
                    details = {"changes": changes}
                add(row, at, key, kind, cat, title, body=text, occurred_at=at, date_basis="recorded",
                    author=JournalAuthor(user_id=row.actor_user_id), tooth=target, details=details,
                    link=f"/patients/{patient_id}/charting")

    if "documents.download" in capabilities:
        for row, at, key in rows(PatientDocument, "document", PatientDocument.created_at,
                [PatientDocument.patient_id == patient_id], PatientDocument.rendered_content,
                literal("correspondence"), extra_search=(PatientDocument.title,)):
            add(row, at, key, "document", "correspondence", row.title, body=row.rendered_content,
                occurred_at=at, date_basis="recorded", author=JournalAuthor(user_id=row.created_by_user_id),
                link=f"/patients/{patient_id}/documents",
                details={"record_kind": "generated_document", "delivery_status": "not_recorded"})
    if "recalls.view" in capabilities:
        model = PatientRecallCommunication
        stamp = func.coalesce(model.contacted_at, model.created_at)
        for row, at, key in rows(model, "recall_communication", stamp, [model.patient_id == patient_id],
                model.notes, literal("correspondence"), extra_search=(model.other_detail, model.outcome)):
            add(row, at, key, "recall_communication", "correspondence", "Recall contact log", body=row.notes,
                occurred_at=at, date_basis="source" if row.contacted_at else "recorded",
                author=JournalAuthor(user_id=row.created_by_user_id), link=f"/patients/{patient_id}",
                details={"recall_id": row.recall_id, "channel": _value(row.channel),
                         "status": _value(row.status), "direction": _value(row.direction),
                         "outcome": row.outcome, "other_detail": row.other_detail,
                         "record_kind": "manual_contact_log", "delivery_status": "not_verified"})

    if imported == "available":
        _imported_sources(db, patient, rows, add, imported_authors)

    # Each individual query is already bounded; merge only these candidates, never whole history.
    candidates.sort(key=lambda row: (row[0] is not None, row[0] or datetime.min.replace(tzinfo=timezone.utc), row[1]), reverse=True)
    page = candidates[:limit]
    items = [row[2] for row in page]
    native_ids = {item.author.user_id for item in items if item.author.user_id is not None}
    authors = {row.id: row for row in db.scalars(select(User).where(User.id.in_(native_ids)))} if native_ids else {}
    source_pairs = {imported_authors[item.key] for item in items if item.key in imported_authors}
    source_users = {}
    if source_pairs:
        for row in db.scalars(select(R4User).where(or_(*(and_(R4User.legacy_source == source,
                cast(R4User.legacy_user_code, String) == code) for source, code in source_pairs)))):
            source_users[(row.legacy_source, str(row.legacy_user_code))] = row.display_name or row.full_name
    for item in items:
        author = authors.get(item.author.user_id)
        if author:
            item.author.name = author.full_name or None
        if item.key in imported_authors:
            item.author.name = source_users.get(imported_authors[item.key])
    # Fetch only the exact current revisions represented on this page, not the
    # patient's revision history. Original authors are distinct from amendment authors.
    native_items = {(item.source_kind, int(item.source_id)): item for item in items
                    if item.source_kind in {"note", "tooth_note"}}
    if native_items:
        predicates = [and_(getattr(NativeNoteRevision, "note_id" if kind == "note" else "tooth_note_id") == source_id,
                           NativeNoteRevision.revision == item.revision)
                      for (kind, source_id), item in native_items.items()]
        for revision in db.scalars(select(NativeNoteRevision).where(or_(*predicates)).limit(len(native_items))):
            identity = ("note", revision.note_id) if revision.note_id else ("tooth_note", revision.tooth_note_id)
            item = native_items[identity]
            item.details["latest_revision"] = {
                "revision": revision.revision, "recorded_at": revision.recorded_at.isoformat(),
                "actor_user_id": revision.recorded_by_user_id,
                "actor_name": revision.recorded_by.full_name if revision.recorded_by else None,
                "baseline": revision.baseline,
            }
    next_cursor = _cursor_encode(page[-1][0], page[-1][1], scope) if len(candidates) > limit else None
    return ClinicalJournalOut(patient_id=patient_id, items=items, next_cursor=next_cursor, availability=availability,
        coverage_notes=[
            "Structured soft-tissue examinations are not available in this journal; explicitly categorised native notes are included.",
            "Imported tooth/surface codes remain raw source values; the tooth filter covers native records only.",
            "Imported note history covers the latest payload already stored in the PMS, not an unverified complete R4 history.",
            "Unmapped or conflicting imported patient identities are not assigned to this patient by the journal.",
        ])


def _imported_sources(db, patient, rows, add, imported_authors):
    """Local imported tables only. Patient mappings are identities, never name matches."""
    mapping = R4PatientMapping
    fallback = int(patient.legacy_id) if patient.legacy_source == "r4" and (patient.legacy_id or "").isdigit() else None

    def mapped(source, code):
        explicit = exists(select(mapping.id).where(mapping.patient_id == patient.id,
                          mapping.legacy_source == source, mapping.legacy_patient_code == code))
        if fallback is None:
            return explicit
        # An explicit mapping to someone else always wins over a legacy fallback.
        conflicting = exists(select(mapping.id).where(mapping.legacy_source == "r4",
                             mapping.legacy_patient_code == fallback, mapping.patient_id != patient.id))
        return or_(explicit, and_(source == "r4", code == fallback, ~conflicting))

    def provenance(source, table, key, patient_code, user_code, recorded, entered, imported, digest=None):
        return JournalProvenance(system=source, source_table=table, source_key=str(key),
            source_patient_code=_string(patient_code), source_author_code=_string(user_code),
            source_recorded_at=recorded, source_entered_at=entered, imported_at=imported, content_hash=digest)

    typed = (
        (R4PatientNote, "r4_patient_note", "dbo.PatientNotes", R4PatientNote.legacy_note_key, R4PatientNote.note_date),
        (R4OldPatientNote, "r4_old_patient_note", "dbo.OldPatientNotes", R4OldPatientNote.legacy_note_key, R4OldPatientNote.note_date),
        (R4TreatmentNote, "r4_treatment_note", "dbo.TreatmentNotes", R4TreatmentNote.legacy_treatment_note_id, R4TreatmentNote.note_date),
        (R4TemporaryNote, "r4_temporary_note", "dbo.TemporaryNotes", R4TemporaryNote.legacy_patient_code, R4TemporaryNote.legacy_updated_at),
    )
    for model, kind, table, source_key, stamp in typed:
        for row, at, key in rows(model, kind, stamp, [mapped(model.legacy_source, model.legacy_patient_code)],
                                model.note, literal("notes")):
            code = _string(row.user_code)
            item = add(row, at, key, kind, "notes", {
                "r4_patient_note": "Imported patient note", "r4_old_patient_note": "Imported historical patient note",
                "r4_treatment_note": "Imported treatment note", "r4_temporary_note": "Imported temporary note",
            }[kind], body=row.note, occurred_at=at, date_basis="source" if at else "unknown",
                author=JournalAuthor(source_user_code=code),
                provenance=provenance(row.legacy_source, table, getattr(row, source_key.key), row.legacy_patient_code,
                    row.user_code, at, None, row.created_at),
                details={"source_tooth": getattr(row, "tooth", None), "source_surface": getattr(row, "surface", None),
                         "category_number": getattr(row, "category_number", None),
                         "fixed_note_code": getattr(row, "fixed_note_code", None),
                         "tp_number": getattr(row, "tp_number", None), "tp_item": getattr(row, "tp_item", None),
                         "source_versions": "latest_stored_payload_only"})
            if code is not None:
                imported_authors[item.key] = (row.legacy_source, code)

    model = R4ChartingCanonicalRecord
    stamp = func.coalesce(model.recorded_at, model.entered_at)
    body = model.payload["note"].astext
    conflicting_mapping = exists(select(mapping.id).where(mapping.legacy_source == "r4",
        mapping.legacy_patient_code == model.legacy_patient_code, mapping.patient_id != patient.id))
    predicates = [model.domain.in_(CANONICAL_NOTE_DOMAINS), ~conflicting_mapping, or_(model.patient_id == patient.id,
        and_(model.patient_id.is_(None), mapped(literal("r4"), model.legacy_patient_code)))]
    # Canonical and typed representations are duplicates only where the source's
    # explicit key agrees AND the stored content/date agree. Never text-only dedup.
    for typed_model, _, table, typed_key, typed_stamp in typed:
        exact = cast(typed_key, String) == model.r4_source_id
        if typed_model is R4OldPatientNote:
            # The canonical key omits the date, whereas the typed key includes it.
            # No unproven cross-representation key conversion here: retain both.
            continue
        duplicate = exists(select(typed_model.id).where(typed_model.legacy_source == "r4",
            typed_model.legacy_patient_code == model.legacy_patient_code, exact,
            typed_model.note.is_not_distinct_from(body), typed_stamp.is_not_distinct_from(model.recorded_at)))
        predicates.append(~and_(model.r4_source == table, duplicate))
    key_expr = literal("r4_canonical_note:") + model.unique_key
    for row, at, key in rows(model, "r4_canonical_note", stamp, predicates, body, literal("notes"), key=key_expr):
        payload = row.payload if isinstance(row.payload, dict) else {}
        # clinician_code on an appointment is not evidence of the note's author.
        code = _string(payload.get("user_code"))
        raw_body = payload.get("note")
        item = add(row, at, key, "r4_canonical_note", "notes", CANONICAL_NOTE_DOMAINS[row.domain],
            body=raw_body if isinstance(raw_body, str) else None, occurred_at=at,
            date_basis="source" if at else "unknown", author=JournalAuthor(source_user_code=code),
            provenance=provenance("r4", row.r4_source, row.r4_source_id, row.legacy_patient_code,
                code, row.recorded_at, row.entered_at, row.extracted_at, row.content_hash),
            details={"domain": row.domain, "source_tooth": row.tooth, "source_surface": row.surface,
                     "source_code_id": row.code_id, "source_status": row.status,
                     "unique_key": row.unique_key, "source_versions": "latest_stored_payload_only",
                     **({"raw_note": raw_body} if raw_body is not None and not isinstance(raw_body, str) else {})})
        if code is not None:
            imported_authors[item.key] = ("r4", code)
