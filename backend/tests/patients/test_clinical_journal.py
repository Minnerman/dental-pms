"""Synthetic local PostgreSQL projections; never connects to an R4 server."""
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import delete, event, select

from app.core.settings import settings
from app.db.session import SessionLocal
from app.models.appointment import Appointment
from app.models.audit_log import AuditLog
from app.models.capability import Capability, UserCapability
from app.models.clinical import Procedure, ToothNote, TreatmentPlanItem
from app.models.clinical_note import NativeNoteRevision
from app.models.note import Note
from app.models.patient import Patient
from app.models.patient_document import PatientDocument
from app.models.patient_recall import PatientRecall
from app.models.patient_recall_communication import PatientRecallCommunication
from app.models.r4_charting import R4OldPatientNote, R4PatientNote, R4TemporaryNote, R4TreatmentNote
from app.models.r4_charting_canonical import R4ChartingCanonicalRecord
from app.models.r4_patient_mapping import R4PatientMapping
from app.models.r4_user import R4User
from app.models.user import Role, User
from app.services.clinical_journal import clinical_journal

NOW = datetime(2025, 6, 12, 10, 30, tzinfo=timezone.utc)
CAPS = {"patients.view", "notes.view", "notes.write", "clinical.view", "clinical.write", "documents.download", "recalls.view"}


@pytest.fixture
def journal(monkeypatch):
    monkeypatch.setattr(settings, "feature_charting_viewer", True)
    with SessionLocal() as db:
        user = User(email=f"journal-{uuid4().hex}@example.com", full_name="Synthetic Journal Author",
                    hashed_password="not-used-by-service-tests", role=Role.dentist, is_active=True)
        db.add(user)
        db.flush()
        db.add_all([UserCapability(user_id=user.id, capability_id=cap.id)
                    for cap in db.scalars(select(Capability).where(Capability.code.in_(CAPS)))])
        patient = Patient(first_name="Synthetic", last_name="Journal", created_by_user_id=user.id,
                          legacy_source="r4", legacy_id=str(600000000 + uuid4().int % 100000000))
        db.add(patient)
        db.flush()
        def add(model, **values):
            if hasattr(model, "created_by_user_id"):
                values.setdefault("created_by_user_id", user.id)
            if hasattr(model, "patient_id"):
                values.setdefault("patient_id", patient.id)
            row = model(**values)
            db.add(row)
            db.flush()
            return row
        def feed(**values):
            return clinical_journal(db, patient_id=patient.id, user=user, **values)
        yield SimpleNamespace(db=db, user=user, patient=patient, add=add, feed=feed)
        db.rollback()


def _caps(j, codes):
    j.db.execute(delete(UserCapability).where(UserCapability.user_id == j.user.id))
    j.db.add_all([UserCapability(user_id=j.user.id, capability_id=cap.id)
                 for cap in j.db.scalars(select(Capability).where(Capability.code.in_(codes)))])
    j.db.flush()


def _import(j, model=R4PatientNote, **values):
    values.setdefault("legacy_source", "r4")
    values.setdefault("legacy_patient_code", int(j.patient.legacy_id))
    if model in {R4PatientNote, R4OldPatientNote}:
        values.setdefault("legacy_note_key", uuid4().hex)
    if model is R4TreatmentNote:
        values.setdefault("legacy_treatment_note_id", uuid4().int % 100000000)
    values.setdefault("note", "Synthetic imported note")
    return j.add(model, **values)


def _canonical(j, **values):
    values.setdefault("domain", "patient_note")
    values.setdefault("r4_source", "dbo.PatientNotes")
    values.setdefault("r4_source_id", uuid4().hex)
    values.setdefault("unique_key", uuid4().hex)
    values.setdefault("legacy_patient_code", int(j.patient.legacy_id))
    values.setdefault("payload", {"note": "Synthetic canonical note"})
    values.setdefault("extracted_at", NOW)
    return j.add(R4ChartingCanonicalRecord, **values)


def test_source_permissions_are_checked_before_queries_and_edit_rights_are_separate(journal):
    j = journal
    j.add(Note, body="Visible notes-only record")
    j.add(ToothNote, tooth="UR6", note="Hidden clinical record")
    _import(j)
    statements = []
    def record(_conn, _cursor, sql, _parameters, _context, _many):
        statements.append(sql.lower())
    _caps(j, {"patients.view", "notes.view"})
    event.listen(j.db.bind, "before_cursor_execute", record)
    try:
        result = j.feed()
    finally:
        event.remove(j.db.bind, "before_cursor_execute", record)
    assert [item.source_kind for item in result.items] == ["note"]
    assert not result.items[0].can_edit
    assert result.availability.clinical == result.availability.imported == "forbidden"
    for table in ("tooth_notes", "r4_patient_notes", "patient_documents", "patient_recall_communications", "audit_logs"):
        assert not any(f"from {table}" in sql for sql in statements)
    _caps(j, {"notes.view"})
    with pytest.raises(HTTPException) as exc:
        j.feed()
    assert exc.value.status_code == 403


def test_stable_cursor_pages_all_ties_and_undated_rows_and_searches_beyond_first_page(journal):
    j = journal
    for index in range(63):
        j.add(Note, body=f"Original note {index}" + (" needle Ω" if index == 0 else ""), created_at=NOW)
    for index in range(3):
        _import(j, note=f"Undated note {index}")
    seen, cursor = [], None
    for _ in range(20):
        response = j.feed(limit=7, before=cursor)
        seen.extend(response.items)
        cursor = response.next_cursor
        if cursor is None:
            break
    assert len(seen) == len({item.key for item in seen}) == 66
    assert all(item.occurred_at is None and item.date_basis == "unknown" for item in seen[-3:])
    assert len(j.feed(limit=5, q="needle Ω").items) == 1
    cursor = j.feed(limit=7).next_cursor
    with pytest.raises(HTTPException) as exc:
        j.feed(before=cursor, q="another filter")
    assert exc.value.status_code == 422
    for invalid in ("%%%", "e30", "not-a-cursor"):
        with pytest.raises(HTTPException):
            j.feed(before=invalid)


def test_raw_multiline_unicode_and_date_author_unknowns_are_preserved(journal):
    j = journal
    raw = "  Ω—日本語\n\n{\\rtf1 original <script>not executable</script>}\n" + "Long note — " * 2000
    row = _import(j, note=raw, user_code=731, tooth=13, surface=7)
    j.add(R4User, legacy_source="r4", legacy_user_code=731, display_name="Synthetic R4 Author")
    result = j.feed().items[0]
    assert result.body == raw
    assert result.occurred_at is None and result.date_basis == "unknown"
    assert result.author.name == "Synthetic R4 Author" and result.author.user_id is None
    assert result.author.source_user_code == "731"
    assert result.provenance.source_key == row.legacy_note_key
    assert result.provenance.source_recorded_at is None and result.provenance.imported_at
    assert result.tooth is None and result.surface is None
    assert result.details["source_tooth"] == 13 and result.details["source_surface"] == 7
    assert not result.can_edit and result.history_url is None
    assert j.feed(tooth="UR3").items == []
    j.add(Note, body="Explicit clinical date", clinical_date=date(2026, 3, 4), created_at=NOW)
    latest = j.feed().items[0]
    assert latest.clinical_date == date(2026, 3, 4) and latest.date_basis == "clinical_date"
    assert latest.occurred_at == NOW


def test_exact_import_identity_dedup_and_namespace_and_divergent_payloads(journal):
    j = journal
    row = _import(j, legacy_note_key="123:456", note="Same text", note_date=NOW)
    _canonical(j, r4_source_id=row.legacy_note_key, payload={"note": row.note}, recorded_at=NOW)
    _canonical(j, r4_source_id="different-id", payload={"note": row.note}, recorded_at=NOW)
    _canonical(j, r4_source_id=row.legacy_note_key, payload={"note": "Different stored version"}, recorded_at=NOW)
    # A separate imported namespace must not be confused with canonical r4.
    j.add(R4PatientMapping, legacy_source="other-import", legacy_patient_code=92)
    _import(j, legacy_source="other-import", legacy_patient_code=92, legacy_note_key="other:92", note="Other namespace", note_date=NOW)
    _canonical(j, r4_source_id="other:92", payload={"note": "Other namespace"}, recorded_at=NOW)
    result = j.feed()
    assert len(result.items) == 5
    assert len([i for i in result.items if i.source_kind == "r4_canonical_note"]) == 3
    assert "Different stored version" in [i.body for i in result.items]


def test_import_patient_mapping_no_name_guess_and_conflicting_mapping_wins(journal):
    j = journal
    other = j.add(Patient, first_name="Synthetic", last_name="Journal")
    _import(j, note="Fallback must not override explicit mapping")
    j.add(R4PatientMapping, legacy_source="r4", legacy_patient_code=int(j.patient.legacy_id), patient_id=other.id)
    _canonical(j, patient_id=other.id, payload={"note": "Other patient's canonical note"})
    _canonical(j, patient_id=j.patient.id, payload={"note": "Stale direct patient ID conflicts with mapping"})
    assert j.feed().items == []
    j.add(R4PatientMapping, legacy_source="r4", legacy_patient_code=400003)
    _import(j, legacy_patient_code=400003, note="Explicit identity mapping")
    _canonical(j, legacy_patient_code=400003, patient_id=None, payload={"note": "Mapped canonical identity"})
    assert {i.body for i in j.feed().items} == {"Explicit identity mapping", "Mapped canonical identity"}


def test_all_local_import_note_families_are_read_only_and_feature_and_role_gated(journal, monkeypatch):
    j = journal
    for model in (R4PatientNote, R4OldPatientNote, R4TreatmentNote, R4TemporaryNote):
        _import(j, model)
    for domain in ("appointment_note", "completed_questionnaire_note"):
        _canonical(j, domain=domain, payload={"note": domain, "clinician_code": 99})
    result = j.feed()
    assert len(result.items) == 6
    assert all(not item.can_edit and item.author.name is None for item in result.items)
    # A questionnaire domain alone is not evidence that its subject was medical.
    assert j.feed(category="medical").items == []
    monkeypatch.setattr(settings, "feature_charting_viewer", False)
    assert j.feed().items == [] and j.feed().availability.imported == "disabled"
    monkeypatch.setattr(settings, "feature_charting_viewer", True)
    j.user.role = Role.external
    assert j.feed().items == [] and j.feed().availability.imported == "forbidden"


def test_native_notes_match_existing_lifecycle_scope_and_archive_is_fail_closed(journal):
    j = journal
    other = j.add(Patient, first_name="Synthetic", last_name="Other")
    wrong_appointment = j.add(Appointment, patient_id=other.id, starts_at=NOW, ends_at=NOW + timedelta(minutes=30))
    archived = j.add(Appointment, starts_at=NOW, ends_at=NOW + timedelta(minutes=30), deleted_at=NOW)
    j.add(Note, body="Wrong patient appointment", appointment_id=wrong_appointment.id)
    j.add(Note, body="Archived appointment", appointment_id=archived.id)
    j.add(Note, body="Archived note", deleted_at=NOW)
    kept = j.add(Note, body="Active unlinked note")
    result = j.feed()
    assert [item.source_id for item in result.items] == [str(kept.id)]
    assert result.items[0].can_edit and result.items[0].history_url == f"/notes/{kept.id}/revisions"
    j.patient.deleted_at = NOW
    with pytest.raises(HTTPException) as exc:
        j.feed()
    assert exc.value.status_code == 404


def test_native_diagnosis_bpe_and_medical_projection_is_narrow_and_source_status_exact(journal):
    j = journal
    j.add(AuditLog, entity_type="patient", entity_id=str(j.patient.id), actor_user_id=j.user.id,
          action="clinical.tooth_conditions.recorded", created_at=NOW,
          after_json={"changed_teeth": ["UR6"], "teeth": {"UR6": {"condition": "missing", "revision": 3}}})
    j.add(AuditLog, entity_type="patient", entity_id=str(j.patient.id), action="clinical.bpe.recorded",
          after_json={"scores": ["1", "2", "3", "4", "*", "0"], "recorded_at": "2025-01-01"})
    j.add(AuditLog, entity_type="patient", entity_id=str(j.patient.id), action="update",
          before_json={"medical_alerts": "Old alert", "phone": "do not expose"},
          after_json={"medical_alerts": "New alert", "phone": "unrelated sensitive field"})
    j.add(AuditLog, entity_type="patient", entity_id=str(j.patient.id), action="update",
          before_json={"medical_alerts": "New alert", "phone": "old"},
          after_json={"medical_alerts": "New alert", "phone": "changed"})
    j.add(AuditLog, entity_type="patient", entity_id=str(j.patient.id), action="update",
          before_json={"allergies": None, "address_line1": "private address"},
          after_json={"allergies": "Synthetic allergy", "address_line1": "private address"})
    diagnosis = j.feed(category="diagnosis", tooth="UR6").items
    assert len(diagnosis) == 1 and "UR6 — condition: missing" in diagnosis[0].body
    assert j.feed(category="diagnosis", tooth="LL6").items == []
    medical = j.feed(category="medical").items
    assert {item.source_kind for item in medical} == {"bpe", "medical_update"}
    serialized = " ".join(item.model_dump_json() for item in medical)
    assert "phone" not in serialized and "unrelated sensitive field" not in serialized
    assert "Synthetic allergy" in serialized and "private address" not in serialized
    assert j.feed(q="unrelated sensitive field").items == []


def test_treatment_and_correspondence_do_not_claim_document_delivery_or_infer_status(journal):
    j = journal
    j.add(Procedure, procedure_code="SYN-FILL", description="Recorded procedure", performed_at=NOW, status="completed")
    j.add(TreatmentPlanItem, procedure_code="SYN-PLAN", description="Plan remains proposed", status="proposed")
    j.add(PatientDocument, title="Synthetic generated letter", rendered_content="Raw generated body")
    recall = j.add(PatientRecall, kind="exam", due_date=date(2025, 7, 1))
    j.add(PatientRecallCommunication, recall_id=recall.id, channel="phone", status="failed",
          notes="Manual call note", outcome="No answer", contacted_at=NOW)
    result = j.feed()
    by_kind = {i.source_kind: i for i in result.items}
    assert by_kind["procedure"].details["status"] == "completed"
    assert by_kind["treatment_plan"].details["status"] == "proposed"
    assert "fee_pence" not in by_kind["procedure"].details
    assert "fee_pence" not in by_kind["treatment_plan"].details
    assert by_kind["document"].details["delivery_status"] == "not_recorded"
    assert by_kind["document"].link == f"/patients/{j.patient.id}/documents"
    assert by_kind["recall_communication"].details["status"] == "failed"
    assert by_kind["recall_communication"].details["delivery_status"] == "not_verified"
    assert j.feed(q="SYN-PLAN").items[0].source_kind == "treatment_plan"
    assert j.feed(q="No answer").items[0].source_kind == "recall_communication"
    _caps(j, {"patients.view", "documents.download"})
    restricted = j.feed()
    assert restricted.availability.documents == "available"
    assert restricted.availability.recalls == "forbidden"
    assert {i.source_kind for i in restricted.items} == {"document"}


def test_literal_search_does_not_treat_percent_or_underscore_as_wildcard(journal):
    j = journal
    j.add(Note, body="Literal 50% and code_X")
    j.add(Note, body="Other ordinary note")
    assert len(j.feed(q="%", limit=1).items) == 1
    assert len(j.feed(q="_", limit=1).items) == 1
    assert len(j.feed(q="code_X", limit=1).items) == 1


def test_current_revision_author_is_separate_from_original_note_author(journal):
    j = journal
    editor = j.add(User, email=f"journal-editor-{uuid4().hex}@example.com", full_name="Synthetic Amendment Author",
                   hashed_password="unused", role=Role.dentist, is_active=True)
    note = j.add(Note, body="Latest amended body", revision=2, created_at=NOW)
    j.add(NativeNoteRevision, note_id=note.id, revision=1, snapshot={"body": "Original body"},
          recorded_by_user_id=j.user.id, recorded_at=NOW)
    j.add(NativeNoteRevision, note_id=note.id, revision=2, snapshot={"body": note.body},
          recorded_by_user_id=editor.id, recorded_at=NOW + timedelta(days=1))
    result = j.feed().items[0]
    assert result.author.name == "Synthetic Journal Author"
    assert result.details["latest_revision"]["actor_name"] == "Synthetic Amendment Author"
    assert result.details["latest_revision"]["revision"] == 2
    assert result.body == "Latest amended body"
    tooth_note = j.add(ToothNote, tooth="LL6", note="Pre-feature latest content", revision=1)
    j.add(NativeNoteRevision, tooth_note_id=tooth_note.id, revision=1, snapshot={"body": tooth_note.note},
          baseline=True, recorded_by_user_id=None, recorded_at=NOW)
    baseline = next(i for i in j.feed().items if i.source_kind == "tooth_note")
    assert baseline.details["latest_revision"]["actor_name"] is None
    assert baseline.details["latest_revision"]["baseline"] is True


def test_malformed_import_note_retains_raw_value_and_record_queries_are_bounded(journal):
    j = journal
    raw = {"unexpected": ["Original", "Ω", 7]}
    _canonical(j, payload={"note": raw})
    statements = []
    def record(_conn, _cursor, sql, parameters, _context, _many):
        if "journal_stamp" in sql:
            statements.append((sql.lower(), parameters))
    event.listen(j.db.bind, "before_cursor_execute", record)
    try:
        result = j.feed(limit=3, q="Original")
    finally:
        event.remove(j.db.bind, "before_cursor_execute", record)
    assert len(result.items) == 1
    assert result.items[0].body is None and result.items[0].details["raw_note"] == raw
    assert statements
    for sql, parameters in statements:
        assert " limit " in sql and "where" in sql and "ilike" in sql
        assert 4 in parameters.values()
