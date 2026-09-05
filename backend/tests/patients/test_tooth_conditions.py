from __future__ import annotations

from uuid import uuid4

from sqlalchemy import func, select

from app.core.security import create_access_token
from app.core.settings import settings
from app.db.session import SessionLocal
from app.models.audit_log import AuditLog
from app.models.clinical import Procedure, ToothCondition, ToothNote, TreatmentPlanItem
from app.models.invoice import Invoice
from app.models.ledger import PatientLedgerEntry
from app.models.user import Role
from app.services.capabilities import replace_user_capabilities
from app.services.users import create_user


def _patient(client, headers):
    response = client.post(
        "/patients", headers=headers,
        json={"first_name": "Synthetic", "last_name": f"ToothCondition-{uuid4().hex[:8]}"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _path(patient_id):
    return f"/patients/{patient_id}/clinical/tooth-conditions"


def _payload(tooth="UR5", condition="missing", revision=0):
    return {"teeth": [tooth], "condition": condition, "expected_revisions": {tooth: revision}}


def _audits(patient_id):
    with SessionLocal() as db:
        return list(db.scalars(select(AuditLog).where(
            AuditLog.entity_type == "patient",
            AuditLog.entity_id == str(patient_id),
            AuditLog.action == "clinical.tooth_conditions.recorded",
        ).order_by(AuditLog.id)))


def _counts(patient_id):
    with SessionLocal() as db:
        return {
            model.__tablename__: db.scalar(select(func.count()).select_from(model).where(model.patient_id == patient_id))
            for model in (ToothCondition, ToothNote, Procedure, TreatmentPlanItem, Invoice, PatientLedgerEntry)
        }


def _user_with_capabilities(codes):
    with SessionLocal() as db:
        user = create_user(
            db, email=f"tooth-condition-{uuid4().hex}@example.com", password="SyntheticCondition123!",
            role=Role.reception, full_name="Synthetic Chart User", is_active=True,
        )
        replace_user_capabilities(db, user.id, codes)
        token = create_access_token(
            subject=str(user.id), secret=settings.secret_key, alg=settings.jwt_alg,
            expires_minutes=10, extra={"role": Role.reception.value, "email": user.email},
        )
        return {"Authorization": f"Bearer {token}"}


def test_tooth_conditions_are_native_persistent_and_never_create_treatment_or_finance(api_client, auth_headers):
    patient_id = _patient(api_client, auth_headers)
    initial = api_client.get(_path(patient_id), headers=auth_headers)
    assert initial.status_code == 200, initial.text
    assert initial.json() == {"patient_id": patient_id, "teeth": {}, "note_teeth": []}
    before = _counts(patient_id)

    for revision, condition in enumerate(("missing", "deciduous", "implant", "unerupted", "impacted", "present")):
        changed = api_client.post(
            _path(patient_id), headers={**auth_headers, "Request-Id": uuid4().hex},
            json=_payload(condition=condition, revision=revision),
        )
        assert changed.status_code == 200, changed.text
        entry = changed.json()["teeth"]["UR5"]
        assert entry["condition"] == condition
        assert entry["revision"] == revision + 1
        assert entry["updated_at"] and entry["updated_by"]["id"]
        assert api_client.get(_path(patient_id), headers=auth_headers).json()["teeth"]["UR5"] == entry

    history = api_client.get(f"/patients/{patient_id}/tooth-history?tooth=UR5", headers=auth_headers)
    assert history.json() == {"notes": [], "procedures": []}
    after = _counts(patient_id)
    assert after.pop("tooth_conditions") == 1
    before.pop("tooth_conditions")
    assert after == before
    audits = _audits(patient_id)
    assert len(audits) == 6
    assert audits[0].before_json["teeth"]["UR5"] == {"condition": None, "revision": 0}
    assert audits[-1].after_json["teeth"]["UR5"] == {"condition": "present", "revision": 6}


def test_tooth_condition_retries_collisions_stale_writes_and_reset_preserve_revisions(api_client, auth_headers):
    patient_id = _patient(api_client, auth_headers)
    original_headers = {**auth_headers, "Request-Id": uuid4().hex}
    original_payload = _payload()
    first = api_client.post(_path(patient_id), headers=original_headers, json=original_payload)
    assert first.status_code == 200, first.text
    retry = api_client.post(_path(patient_id), headers=original_headers, json=original_payload)
    assert retry.status_code == 200
    assert retry.json() == first.json()
    assert len(_audits(patient_id)) == 1

    newer = api_client.post(_path(patient_id), headers=auth_headers, json=_payload(condition="implant", revision=1))
    assert newer.status_code == 200
    replay = api_client.post(_path(patient_id), headers=original_headers, json=original_payload)
    assert replay.status_code == 200
    assert replay.json()["teeth"]["UR5"]["condition"] == "implant"
    assert replay.json()["teeth"]["UR5"]["revision"] == 2
    collision = api_client.post(_path(patient_id), headers=original_headers, json=_payload(condition="present", revision=2))
    assert collision.status_code == 409
    stale = api_client.post(_path(patient_id), headers=auth_headers, json=_payload(condition="present", revision=1))
    assert stale.status_code == 409
    assert len(_audits(patient_id)) == 2

    reset = api_client.post(_path(patient_id), headers=auth_headers, json=_payload(condition=None, revision=2))
    assert reset.status_code == 200
    assert reset.json()["teeth"]["UR5"]["condition"] is None
    assert reset.json()["teeth"]["UR5"]["revision"] == 3
    assert _counts(patient_id)["tooth_conditions"] == 1
    stale_after_reset = api_client.post(_path(patient_id), headers=auth_headers, json=_payload(revision=0))
    assert stale_after_reset.status_code == 409
    assert api_client.get(_path(patient_id), headers=auth_headers).json()["teeth"]["UR5"]["revision"] == 3


def test_tooth_condition_validation_rejects_unsupported_and_ambiguous_updates_atomically(api_client, auth_headers):
    patient_id = _patient(api_client, auth_headers)
    upper = [f"U{side}{n}" for side in ("R", "L") for n in range(1, 9)]
    invalid = [
        _payload(tooth="UR9"), _payload(tooth="URe"), _payload(tooth="11"),
        _payload(tooth="UR6", condition="deciduous"),
        _payload(condition="retained_root"), _payload(condition=""),
        _payload(revision=-1), _payload(revision=True), _payload(revision="0"),
        {**_payload(), "fee_pence": 1000},
        {"teeth": ["UR5"], "expected_revisions": {"UR5": 0}},
        {**_payload(), "expected_revisions": {}},
        {**_payload(), "expected_revisions": {"UR5": 0, "LL5": 0}},
        {**_payload(), "teeth": ["UR5", "ur5"]},
        {"teeth": ["UR5", "UL5"], "condition": "missing", "expected_revisions": {"UR5": 0, "UL5": 0}},
        {"teeth": upper, "condition": "implant", "expected_revisions": {t: 0 for t in upper}},
        {"teeth": upper[:-1] + ["LL8"], "condition": "missing", "expected_revisions": {t: 0 for t in upper[:-1] + ["LL8"]}},
        {**_payload(), "teeth": [None]},
    ]
    before = _counts(patient_id)
    for payload in invalid:
        response = api_client.post(_path(patient_id), headers=auth_headers, json=payload)
        assert response.status_code == 422, response.text
    assert _counts(patient_id) == before
    assert _audits(patient_id) == []
    normalized = api_client.post(_path(patient_id), headers=auth_headers, json=_payload(tooth=" ur5 "))
    assert normalized.status_code == 200, normalized.text
    assert "UR5" in normalized.json()["teeth"]


def test_all_in_arch_missing_is_atomic_and_preserves_notes_and_other_arch(api_client, auth_headers):
    patient_id = _patient(api_client, auth_headers)
    for tooth in ("UR5", "LL6"):
        response = api_client.post(_path(patient_id), headers=auth_headers, json=_payload(tooth=tooth, condition="implant"))
        assert response.status_code == 200, response.text
    note = api_client.post(
        f"/patients/{patient_id}/tooth-notes", headers=auth_headers,
        json={"tooth": "UR5", "note": "Synthetic existing note; keep after missing or reset"},
    )
    assert note.status_code == 201, note.text
    before_counts = _counts(patient_id)
    before_audits = len(_audits(patient_id))
    upper = [f"U{side}{n}" for side in ("R", "L") for n in range(1, 9)]
    payload = {"teeth": upper, "condition": "missing", "expected_revisions": {t: 0 for t in upper}}
    stale = api_client.post(_path(patient_id), headers=auth_headers, json=payload)
    assert stale.status_code == 409
    assert _counts(patient_id) == before_counts
    assert len(_audits(patient_id)) == before_audits

    payload["expected_revisions"]["UR5"] = 1
    changed = api_client.post(_path(patient_id), headers=auth_headers, json=payload)
    assert changed.status_code == 200, changed.text
    teeth = changed.json()["teeth"]
    assert all(teeth[tooth]["condition"] == "missing" for tooth in upper)
    assert teeth["UR5"]["revision"] == 2
    assert teeth["LL6"]["condition"] == "implant"
    assert teeth["LL6"]["revision"] == 1
    assert changed.json()["note_teeth"] == ["UR5"]
    assert len(_audits(patient_id)) == before_audits + 1
    after_counts = _counts(patient_id)
    assert after_counts.pop("tooth_conditions") == 17
    before_counts.pop("tooth_conditions")
    assert after_counts == before_counts

    reset = api_client.post(_path(patient_id), headers=auth_headers, json=_payload(condition=None, revision=2))
    assert reset.status_code == 200
    history = api_client.get(f"/patients/{patient_id}/tooth-history?tooth=UR5", headers=auth_headers).json()
    assert history["notes"][0]["id"] == note.json()["id"]
    assert history["procedures"] == []
    assert "Synthetic existing note" not in str([(a.before_json, a.after_json) for a in _audits(patient_id)])


def test_note_markers_cover_all_notes_not_only_recent_summary_limit(api_client, auth_headers):
    patient_id = _patient(api_client, auth_headers)
    for index in range(22):
        note = api_client.post(
            f"/patients/{patient_id}/tooth-notes", headers=auth_headers,
            json={"tooth": "LL1" if index == 0 else "UR5", "note": f"Synthetic marker {index}"},
        )
        assert note.status_code == 201, note.text
    response = api_client.get(_path(patient_id), headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["note_teeth"] == ["LL1", "UR5"]
    assert response.json()["teeth"] == {}


def test_tooth_conditions_require_capabilities_and_reject_archived_patients(api_client, auth_headers):
    patient_id = _patient(api_client, auth_headers)
    denied_headers = _user_with_capabilities([])
    view_headers = _user_with_capabilities(["clinical.view"])
    write_headers = _user_with_capabilities(["clinical.view", "clinical.write"])
    write_only_headers = _user_with_capabilities(["clinical.write"])
    before = _counts(patient_id)
    assert api_client.get(_path(patient_id), headers=denied_headers).status_code == 403
    assert api_client.post(_path(patient_id), headers=denied_headers, json=_payload()).status_code == 403
    assert api_client.get(_path(2000000000), headers=denied_headers).status_code == 403
    assert api_client.get(_path(patient_id), headers=view_headers).status_code == 200
    assert api_client.post(_path(patient_id), headers=view_headers, json=_payload()).status_code == 403
    assert api_client.post(_path(patient_id), headers=write_only_headers, json=_payload()).status_code == 403
    assert _counts(patient_id) == before
    assert _audits(patient_id) == []
    allowed = api_client.post(_path(patient_id), headers=write_headers, json=_payload())
    assert allowed.status_code == 200, allowed.text
    before = _counts(patient_id)
    audit_count = len(_audits(patient_id))
    archived = api_client.post(f"/patients/{patient_id}/archive", headers=auth_headers)
    assert archived.status_code == 200, archived.text
    assert api_client.get(_path(patient_id), headers=auth_headers).status_code == 404
    assert api_client.post(_path(patient_id), headers=auth_headers, json=_payload(condition="present", revision=1)).status_code == 404
    assert _counts(patient_id) == before
    assert len(_audits(patient_id)) == audit_count
