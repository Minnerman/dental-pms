"""Synthetic-only note amendments, snapshots and template safety."""
from datetime import datetime, timezone
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import func, select

from app.core.security import create_access_token
from app.core.settings import settings
from app.db.session import SessionLocal
from app.models.audit_log import AuditLog
from app.models.clinical import Procedure, ToothNote, TreatmentPlanItem
from app.models.clinical_note import ClinicalNoteTemplateRevision, NativeNoteRevision
from app.models.ledger import PatientLedgerEntry
from app.models.note import Note, NoteType
from app.models.patient import Patient
from app.models.user import Role, User
from app.services.capabilities import replace_user_capabilities
from app.services.users import create_user
from app.services.audit import log_event


def patient(client, headers):
    result = client.post("/patients", headers=headers, json={"first_name": "Synthetic journal", "last_name": uuid4().hex})
    assert result.status_code == 201
    return result.json()["id"]


def note(client, headers, patient_id, **fields):
    result = client.post(f"/patients/{patient_id}/notes", headers=headers, json={"body": "Synthetic original", **fields})
    assert result.status_code == 201
    return result.json()


def template(client, headers, **fields):
    result = client.post("/clinical-note-templates", headers=headers, json={
        "title": f"Synthetic {uuid4().hex}", "category": "clinical", "body": "Finding: {{finding}}",
        "fields": [{"key": "finding", "label": "Finding", "options": ["Discussed", "Deferred"], "required": True}],
        "codes": ["EXAMPLE-LABEL"], **fields,
    })
    assert result.status_code == 201
    return result.json()


def restricted(codes):
    with SessionLocal() as db:
        user = create_user(db, email=f"journal-{uuid4().hex}@example.com", password="SyntheticOnly2026!", role=Role.reception, full_name="Synthetic Journal Operator", is_active=True)
        replace_user_capabilities(db, user.id, codes)
        token = create_access_token(subject=str(user.id), secret=settings.secret_key, alg=settings.jwt_alg,
                                    expires_minutes=20, extra={"role": user.role.value, "email": user.email})
    return {"Authorization": f"Bearer {token}"}


def counts(patient_id):
    with SessionLocal() as db:
        return tuple(db.scalar(select(func.count(model.id)).where(model.patient_id == patient_id)) for model in (Procedure, TreatmentPlanItem, PatientLedgerEntry))


def test_note_amendments_preserve_full_text_and_original_metadata(api_client, auth_headers):
    pid = patient(api_client, auth_headers)
    original = "Unicode Ω 漢字\n" * 500
    saved = note(api_client, auth_headers, pid, body=original, clinical_date="2020-02-29", category="soft_tissue")
    assert saved["revision"] == 1
    baseline = counts(pid)
    changed = api_client.post(f"/notes/{saved['id']}/amendments", headers=auth_headers, json={
        "expected_revision": 1, "body": "  amended Ω\n\n", "reason": "Corrected wording", "clinical_date": "2020-03-01",
    })
    assert changed.status_code == 200
    assert changed.json()["revision"] == 2
    assert changed.json()["body"] == "  amended Ω\n\n"
    assert changed.json()["created_at"] == saved["created_at"]
    assert changed.json()["created_by"] == saved["created_by"]
    versions = api_client.get(f"/notes/{saved['id']}/revisions", headers=auth_headers).json()["items"]
    assert [item["revision"] for item in versions] == [2, 1]
    assert versions[1]["body"] == original.strip()
    assert versions[1]["clinical_date"] == "2020-02-29"
    assert versions[0]["reason"] == "Corrected wording"
    assert counts(pid) == baseline
    with SessionLocal() as db:
        logs = list(db.scalars(select(AuditLog).where(AuditLog.entity_type == "note", AuditLog.entity_id == str(saved["id"]))))
        assert all("body" not in (row.after_json or {}) and "body" not in (row.before_json or {}) for row in logs)


def test_legacy_patch_and_existing_raw_baseline_are_revisioned(api_client, auth_headers):
    pid = patient(api_client, auth_headers)
    raw = " \tUnmodified pre-feature text Ω\n\n"
    with SessionLocal() as db:
        actor = db.scalar(select(User).where(User.role == Role.superadmin))
        row = Note(patient_id=pid, body=raw, note_type=NoteType.clinical, created_by_user_id=actor.id, updated_by_user_id=actor.id)
        db.add(row)
        db.commit()
        nid = row.id
    before = api_client.get(f"/notes/{nid}/revisions", headers=auth_headers).json()
    assert before["items"][0]["baseline"] is True
    assert before["items"][0]["body"] == raw
    # Date-only edit must not normalize hidden/unchanged text.
    updated = api_client.patch(f"/notes/{nid}", headers=auth_headers, json={"clinical_date": "2024-02-29"})
    assert updated.status_code == 200
    assert updated.json()["body"] == raw
    assert updated.json()["revision"] == 2
    versions = api_client.get(f"/notes/{nid}/revisions", headers=auth_headers).json()["items"]
    assert [v["body"] for v in versions] == [raw, raw]
    assert versions[1]["baseline"] is True


def test_stale_noop_replay_and_cross_operation_collision(api_client, auth_headers):
    pid = patient(api_client, auth_headers)
    request_headers = {**auth_headers, "Request-Id": uuid4().hex}
    saved = note(api_client, request_headers, pid)
    assert note(api_client, request_headers, pid)["id"] == saved["id"]
    assert api_client.post(f"/patients/{pid}/notes", headers=request_headers, json={"body": "Different"}).status_code == 409
    assert api_client.post(f"/patients/{pid}/tooth-notes", headers=request_headers, json={"tooth": "UR1", "note": "Different"}).status_code == 409
    edit_headers = {**auth_headers, "Request-Id": uuid4().hex}
    payload = {"expected_revision": 1, "body": "Changed"}
    url = f"/notes/{saved['id']}/amendments"
    first = api_client.post(url, headers=edit_headers, json=payload)
    assert first.status_code == 200 and first.json()["revision"] == 2
    assert api_client.post(url, headers=edit_headers, json=payload).json()["revision"] == 2
    assert api_client.post(url, headers=auth_headers, json=payload).status_code == 409
    noop_headers = {**auth_headers, "Request-Id": uuid4().hex}
    noop = {"expected_revision": 2, "body": "Changed"}
    assert api_client.post(url, headers=noop_headers, json=noop).json()["revision"] == 2
    assert api_client.post(url, headers=noop_headers, json=noop).json()["revision"] == 2
    assert len(api_client.get(f"/notes/{saved['id']}/revisions", headers=auth_headers).json()["items"]) == 2


@pytest.mark.parametrize("invalid", [{}, {"expected_revision": True}, {"expected_revision": 0}, {"expected_revision": "1"}, {"expected_revision": 1, "body": None}, {"expected_revision": 1, "body": "  "}, {"expected_revision": 1, "tooth": "UR1"}])
def test_amendment_validation(api_client, auth_headers, invalid):
    saved = note(api_client, auth_headers, patient(api_client, auth_headers))
    assert api_client.post(f"/notes/{saved['id']}/amendments", headers=auth_headers, json=invalid).status_code == 422


def test_tooth_amendments_scope_replay_permissions_and_archived_guard(api_client, auth_headers):
    pid, other = patient(api_client, auth_headers), patient(api_client, auth_headers)
    baseline = counts(pid)
    response = api_client.post(f"/patients/{pid}/tooth-notes", headers=auth_headers, json={"tooth": "UR1", "surface": "I", "note": "Synthetic tooth", "category": "clinical"})
    assert response.status_code == 201
    saved = response.json()
    url = f"/patients/{pid}/tooth-notes/{saved['id']}"
    body = {"expected_revision": 1, "note": "  corrected tooth\n", "clinical_date": "2024-01-01"}
    req_headers = {**auth_headers, "Request-Id": uuid4().hex}
    assert api_client.patch(url, headers=req_headers, json=body).json()["revision"] == 2
    assert api_client.patch(url, headers=req_headers, json=body).json()["revision"] == 2
    assert api_client.patch(url, headers=auth_headers, json=body).status_code == 409
    assert api_client.patch(f"/patients/{other}/tooth-notes/{saved['id']}", headers=auth_headers, json=body).status_code == 404
    assert api_client.get(f"/patients/{other}/tooth-notes/{saved['id']}/revisions", headers=auth_headers).status_code == 404
    for caps in ([], ["notes.view", "notes.write"], ["clinical.write"]):
        headers = restricted(caps)
        assert api_client.get(f"{url}/revisions", headers=headers).status_code == 403
        assert api_client.patch(url, headers=headers, json=body).status_code == 403
    versions = api_client.get(f"{url}/revisions", headers=auth_headers).json()["items"]
    assert versions[1]["body"] == "Synthetic tooth"
    assert versions[0]["body"] == "  corrected tooth\n"
    assert counts(pid) == baseline
    with SessionLocal() as db:
        row = db.get(Patient, pid)
        row.deleted_at = datetime.now(timezone.utc)
        db.commit()
    assert api_client.get(f"{url}/revisions", headers=auth_headers).status_code == 404
    assert api_client.patch(url, headers=auth_headers, json={"expected_revision": 2, "note": "No"}).status_code == 404


def test_history_paging_and_archive_restore_snapshots(api_client, auth_headers):
    saved = note(api_client, auth_headers, patient(api_client, auth_headers))
    url = f"/notes/{saved['id']}"
    assert api_client.post(f"{url}/archive", headers=auth_headers).json()["revision"] == 2
    assert api_client.post(f"{url}/restore", headers=auth_headers).json()["revision"] == 3
    page = api_client.get(f"{url}/revisions?limit=1", headers=auth_headers).json()
    assert page["next_before_revision"] == 3
    assert page["items"][0]["archived"] is False
    older = api_client.get(f"{url}/revisions?limit=1&before_revision=3", headers=auth_headers).json()
    assert older["items"][0]["archived"] is True
    assert older["items"][0]["deleted_at"] is not None
    assert older["next_before_revision"] == 2


def test_templates_snapshot_codes_revisions_and_never_create_treatment(api_client, auth_headers):
    pid = patient(api_client, auth_headers)
    baseline = counts(pid)
    row = template(api_client, auth_headers)
    saved = note(api_client, auth_headers, pid, body="Finding: Discussed", template_id=row["id"], template_revision=1)
    assert saved["codes"] == ["EXAMPLE-LABEL"]
    revised = api_client.patch(f"/clinical-note-templates/{row['id']}", headers=auth_headers, json={"expected_revision": 1, "body": "Changed: {{finding}}", "codes": ["NEW-LABEL"]})
    assert revised.status_code == 200 and revised.json()["revision"] == 2
    assert api_client.patch(f"/clinical-note-templates/{row['id']}", headers=auth_headers, json={"expected_revision": 1, "title": "Stale"}).status_code == 409
    assert api_client.post(f"/patients/{pid}/notes", headers=auth_headers, json={"body": "Stale draft", "template_id": row["id"], "template_revision": 1}).status_code == 409
    assert api_client.post(f"/patients/{pid}/notes", headers=auth_headers, json={"body": "Wrong codes", "template_id": row["id"], "template_revision": 2, "codes": ["EXAMPLE-LABEL"]}).status_code == 422
    versions = api_client.get(f"/notes/{saved['id']}/revisions", headers=auth_headers).json()["items"]
    assert versions[0]["template_revision"] == 1
    assert versions[0]["codes"] == ["EXAMPLE-LABEL"]
    assert versions[0]["body"] == "Finding: Discussed"
    assert counts(pid) == baseline
    with SessionLocal() as db:
        snapshots = list(db.scalars(select(ClinicalNoteTemplateRevision).where(ClinicalNoteTemplateRevision.template_id == row["id"]).order_by(ClinicalNoteTemplateRevision.revision)))
        assert snapshots[0].snapshot["body"] == "Finding: {{finding}}"
        assert snapshots[1].snapshot["codes"] == ["NEW-LABEL"]


@pytest.mark.parametrize("change", [
    {"body": "{{unknown}}"}, {"fields": []}, {"codes": ["same", "same"]},
    {"fields": [{"key": "invalid.dot", "label": "X", "options": ["A"], "required": True}]},
    {"fields": [{"key": "finding", "label": "X", "options": ["A", "A"], "required": True}]},
    {"fields": [{"key": "finding", "label": "X", "options": ["A"], "required": True, "default": "A"}]},
    {"body": "{{finding}} {{"}, {"title": " "},
])
def test_template_prompt_validation(api_client, auth_headers, change):
    values = {"title": "Synthetic invalid", "category": "clinical", "body": "{{finding}}", "fields": [{"key": "finding", "label": "Finding", "options": ["A"], "required": True}], **change}
    assert api_client.post("/clinical-note-templates", headers=auth_headers, json=values).status_code == 422


def test_note_and_template_capability_boundaries(api_client, auth_headers):
    pid = patient(api_client, auth_headers)
    saved = note(api_client, auth_headers, pid)
    for caps in ([], ["clinical.view", "clinical.write"], ["notes.write"]):
        headers = restricted(caps)
        assert api_client.get(f"/notes/{saved['id']}/revisions", headers=headers).status_code == 403
        assert api_client.post(f"/notes/{saved['id']}/amendments", headers=headers, json={"expected_revision": 1, "body": "Denied"}).status_code == 403
        assert api_client.get("/clinical-note-templates", headers=headers).status_code == 403
        assert api_client.post("/clinical-note-templates", headers=headers, json={"title": "Denied", "body": "Denied"}).status_code == 403
    headers = restricted(["notes.view"])
    assert api_client.get(f"/notes/{saved['id']}/revisions", headers=headers).status_code == 200
    assert api_client.get("/clinical-note-templates", headers=headers).status_code == 200
    assert api_client.post("/clinical-note-templates", headers=headers, json={"title": "Denied", "body": "Denied"}).status_code == 403


def test_old_audit_only_request_is_not_recreated(api_client, auth_headers):
    pid = patient(api_client, auth_headers)
    req_id = uuid4().hex
    with SessionLocal() as db:
        actor = db.scalar(select(User).where(User.role == Role.superadmin))
        row = Note(patient_id=pid, body="Legacy native", note_type=NoteType.clinical, created_by_user_id=actor.id, updated_by_user_id=actor.id)
        db.add(row)
        db.flush()
        log_event(db, actor=actor, action="note.created", entity_type="note", entity_id=str(row.id), request_id=req_id,
                  after_data={"note_id": row.id, "patient_id": pid})
        db.commit()
    response = api_client.post(f"/patients/{pid}/notes", headers={**auth_headers, "Request-Id": req_id}, json={"body": "Legacy native"})
    assert response.status_code == 409
    with SessionLocal() as db:
        assert db.scalar(select(func.count(Note.id)).where(Note.patient_id == pid)) == 1


def test_archive_replay_does_not_undo_later_restore(api_client, auth_headers):
    saved = note(api_client, auth_headers, patient(api_client, auth_headers))
    url = f"/notes/{saved['id']}"
    headers = {**auth_headers, "Request-Id": uuid4().hex}
    assert api_client.post(f"{url}/archive", headers=headers).json()["revision"] == 2
    assert api_client.post(f"{url}/restore", headers=auth_headers).json()["revision"] == 3
    replay = api_client.post(f"{url}/archive", headers=headers)
    assert replay.status_code == 200
    assert replay.json()["revision"] == 3 and replay.json()["deleted_at"] is None


def test_template_inactive_and_noop_replay(api_client, auth_headers):
    row = template(api_client, auth_headers, body="Plain synthetic text", fields=[], codes=[])
    url = f"/clinical-note-templates/{row['id']}"
    headers = {**auth_headers, "Request-Id": uuid4().hex}
    payload = {"expected_revision": 1, "is_active": False}
    assert api_client.patch(url, headers=headers, json=payload).json()["revision"] == 2
    assert api_client.patch(url, headers=headers, json=payload).json()["revision"] == 2
    assert all(item["id"] != row["id"] for item in api_client.get("/clinical-note-templates", headers=auth_headers).json())
    assert any(item["id"] == row["id"] for item in api_client.get("/clinical-note-templates?include_inactive=true", headers=auth_headers).json())
    assert api_client.post(f"/patients/{patient(api_client, auth_headers)}/notes", headers=auth_headers,
                           json={"body": "Draft", "template_id": row["id"], "template_revision": 2}).status_code == 409


def test_concurrent_native_amendments_have_one_winner(api_client, auth_headers):
    saved = note(api_client, auth_headers, patient(api_client, auth_headers))
    url = f"/notes/{saved['id']}/amendments"
    def amend(body):
        return api_client.post(url, headers=auth_headers, json={"expected_revision": 1, "body": body})
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(amend, ["Synthetic contender A", "Synthetic contender B"]))
    assert sorted(result.status_code for result in results) == [200, 409]
    versions = api_client.get(f"/notes/{saved['id']}/revisions", headers=auth_headers).json()["items"]
    assert [row["revision"] for row in versions] == [2, 1]
    assert versions[1]["body"] == "Synthetic original"
