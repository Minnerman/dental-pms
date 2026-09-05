from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.core.security import create_access_token
from app.core.settings import settings
from app.db.session import SessionLocal
from app.models.audit_log import AuditLog
from app.models.clinical import Procedure, ToothCondition, ToothNote, TreatmentPlanItem
from app.models.invoice import Invoice, InvoiceStatus
from app.models.ledger import LedgerEntryType, PatientLedgerEntry
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
    assert audits[0].before_json["teeth"]["UR5"] == {
        "condition": None, "movement": None, "rotation": None, "root_observations": {}, "crown_observation": None, "revision": 0,
    }
    assert audits[-1].after_json["teeth"]["UR5"] == {
        "condition": "present", "movement": None, "rotation": None, "root_observations": {}, "crown_observation": None, "revision": 6,
    }


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
        # Arbitrary batches are now valid, but every selected tooth must support
        # the observation and the complete revision set is still mandatory.
        {"teeth": upper, "condition": "deciduous", "expected_revisions": {t: 0 for t in upper}},
        {"teeth": upper, "condition": "implant", "expected_revisions": {t: 0 for t in upper[:-1]}},
        {**_payload(), "movement": "left"},
        {**_payload(), "rotation": 15},
        {**_payload(), "rotation": "Clockwise"},
        {**_payload(), "movement": False},
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


def _action_payload(teeth, revisions=None, **observations):
    return {"teeth": teeth, "expected_revisions": revisions or {tooth: 0 for tooth in teeth},
            **observations}


def test_movement_and_rotation_preserve_condition_and_clear_only_explicit_attributes(api_client, auth_headers):
    patient_id = _patient(api_client, auth_headers)
    path = _path(patient_id)
    for tooth, condition in (("UR5", "implant"), ("LL3", "deciduous")):
        response = api_client.post(path, headers=auth_headers, json=_payload(tooth=tooth, condition=condition))
        assert response.status_code == 200
    before_counts = _counts(patient_id)
    teeth = ["UR5", "LL3"]
    forward = _action_payload(teeth, {tooth: 1 for tooth in teeth}, movement="forward")
    response = api_client.post(path, headers=auth_headers, json=forward)
    assert response.status_code == 200
    for tooth, condition in (("UR5", "implant"), ("LL3", "deciduous")):
        row = response.json()["teeth"][tooth]
        assert row["condition"] == condition
        assert row["movement"] == "forward"
        assert row["rotation"] is None
        assert row["revision"] == 2
    rotated = api_client.post(path, headers=auth_headers,
        json=_action_payload(teeth, {tooth: 2 for tooth in teeth}, rotation="anticlockwise"))
    assert rotated.status_code == 200
    clear_movement = api_client.post(path, headers=auth_headers,
        json=_action_payload(teeth, {tooth: 3 for tooth in teeth}, movement=None))
    assert clear_movement.status_code == 200
    for row in clear_movement.json()["teeth"].values():
        assert row["movement"] is None
        assert row["rotation"] == "anticlockwise"
        assert row["revision"] == 4
    # The deployed old condition-only client must not erase position attributes.
    old_client_clear = api_client.post(path, headers=auth_headers,
        json=_payload(condition=None, revision=4))
    assert old_client_clear.status_code == 200
    row = old_client_clear.json()["teeth"]["UR5"]
    assert row["condition"] is None
    assert row["rotation"] == "anticlockwise"
    assert row["revision"] == 5
    reset = api_client.post(path, headers=auth_headers, json=_action_payload(
        teeth, {"UR5": 5, "LL3": 4}, condition=None, movement=None, rotation=None))
    assert reset.status_code == 200
    for tooth, expected_revision in (("UR5", 6), ("LL3", 5)):
        row = reset.json()["teeth"][tooth]
        assert row["condition"] is row["movement"] is row["rotation"] is None
        assert row["revision"] == expected_revision
    assert _counts(patient_id) == before_counts
    audit = _audits(patient_id)[-1]
    assert audit.before_json["teeth"]["LL3"]["condition"] == "deciduous"
    assert audit.before_json["teeth"]["LL3"]["rotation"] == "anticlockwise"
    assert audit.after_json["request"]["movement"] is None


def test_arbitrary_multitooth_batches_and_full_mouth_are_atomic_and_revision_guarded(api_client, auth_headers):
    patient_id = _patient(api_client, auth_headers)
    path = _path(patient_id)
    selected = ["UR2", "UL6", "LR8", "LL1"]
    before = _counts(patient_id)
    initial = api_client.post(path, headers=auth_headers,
        json=_action_payload(selected, movement="backward"))
    assert initial.status_code == 200
    assert set(initial.json()["teeth"]) == set(selected)
    assert all(row["condition"] is None for row in initial.json()["teeth"].values())
    assert all(row["movement"] == "backward" for row in initial.json()["teeth"].values())
    all_teeth = [f"{quadrant}{number}" for quadrant in ("UR", "UL", "LR", "LL") for number in range(1, 9)]
    stale_payload = _action_payload(all_teeth, condition="missing")
    prior = api_client.get(path, headers=auth_headers).json()
    audit_count = len(_audits(patient_id))
    stale = api_client.post(path, headers=auth_headers, json=stale_payload)
    assert stale.status_code == 409
    assert api_client.get(path, headers=auth_headers).json() == prior
    assert len(_audits(patient_id)) == audit_count
    stale_payload["expected_revisions"].update({tooth: 1 for tooth in selected})
    full = api_client.post(path, headers=auth_headers, json=stale_payload)
    assert full.status_code == 200
    assert len(full.json()["teeth"]) == 32
    assert all(row["condition"] == "missing" for row in full.json()["teeth"].values())
    for tooth in selected:
        assert full.json()["teeth"][tooth]["movement"] == "backward"
    after = _counts(patient_id)
    assert after.pop("tooth_conditions") == 32
    before.pop("tooth_conditions")
    assert after == before


def test_position_retries_collisions_and_unchanged_observations_are_safe(api_client, auth_headers):
    patient_id = _patient(api_client, auth_headers)
    path = _path(patient_id)
    headers = {**auth_headers, "Request-Id": uuid4().hex}
    payload = _action_payload(["LL8", "UR1"], rotation="clockwise")
    first = api_client.post(path, headers=headers, json=payload)
    assert first.status_code == 200
    assert api_client.post(path, headers=headers, json=payload).json() == first.json()
    assert len(_audits(patient_id)) == 1
    # An explicit clearing of condition is not the same operation as omitting it.
    collision = api_client.post(path, headers=headers, json={**payload, "condition": None})
    assert collision.status_code == 409
    assert len(_audits(patient_id)) == 1
    unchanged = api_client.post(path, headers=auth_headers, json=_action_payload(
        ["UR1", "LL8"], {"UR1": 1, "LL8": 1}, rotation="clockwise"))
    assert unchanged.status_code == 200
    assert all(row["revision"] == 1 for row in unchanged.json()["teeth"].values())
    assert _audits(patient_id)[-1].after_json["changed_teeth"] == []
    changed = api_client.post(path, headers=auth_headers, json=_action_payload(
        ["UR1", "LL8"], {"UR1": 1, "LL8": 1}, movement="forward"))
    assert changed.status_code == 200
    replay = api_client.post(path, headers=headers, json=payload)
    assert replay.status_code == 200
    assert all(row["revision"] == 2 for row in replay.json()["teeth"].values())
    assert all(row["movement"] == "forward" for row in replay.json()["teeth"].values())


def test_concurrent_multitooth_actions_have_one_atomic_winner(api_client, auth_headers):
    patient_id = _patient(api_client, auth_headers)
    path = _path(patient_id)
    teeth = ["UR7", "LL5", "UL1"]

    def submit(direction):
        return api_client.post(path, headers={**auth_headers, "Request-Id": uuid4().hex},
            json=_action_payload(teeth, movement=direction))

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(submit, ["forward", "backward"]))
    assert sorted(response.status_code for response in responses) == [200, 409]
    winner = next(response for response in responses if response.status_code == 200).json()
    current = api_client.get(path, headers=auth_headers).json()
    assert current == winner
    assert len({row["movement"] for row in current["teeth"].values()}) == 1
    assert all(row["revision"] == 1 for row in current["teeth"].values())
    assert len(_audits(patient_id)) == 1


def _seed_reset_related_records(patient_id, actor_id, teeth):
    """Nonempty synthetic records ensure reset preservation is not vacuous."""
    with SessionLocal() as db:
        for tooth in teeth:
            db.add(ToothNote(patient_id=patient_id, tooth=tooth,
                note=f"Synthetic existing note for {tooth}", created_by_user_id=actor_id))
            db.add(Procedure(patient_id=patient_id, tooth=tooth, procedure_code="SYNTHETIC",
                description=f"Synthetic historical treatment for {tooth}", fee_pence=2500,
                performed_at=datetime(2035, 1, 2, 10, tzinfo=timezone.utc), created_by_user_id=actor_id))
            db.add(TreatmentPlanItem(patient_id=patient_id, tooth=tooth, procedure_code="SYNTHETIC-PLAN",
                description=f"Synthetic retained plan for {tooth}", fee_pence=5000,
                created_by_user_id=actor_id))
        invoice = Invoice(patient_id=patient_id, invoice_number=f"RESET-{uuid4().hex[:20]}",
            issue_date=date(2035, 1, 2), status=InvoiceStatus.issued,
            subtotal_pence=12000, total_pence=12000, created_by_user_id=actor_id)
        db.add(invoice)
        db.flush()
        db.add(PatientLedgerEntry(patient_id=patient_id, entry_type=LedgerEntryType.charge,
            amount_pence=12000, related_invoice_id=invoice.id,
            note="Synthetic retained charge", created_by_user_id=actor_id))
        db.commit()


def _reset_related_snapshot(patient_id):
    # Compare every stored column, not merely counts, for this synthetic patient.
    with SessionLocal() as db:
        return {
            model.__tablename__: [dict(row) for row in db.execute(
                select(*model.__table__.columns).where(model.patient_id == patient_id).order_by(model.id)
            ).mappings()]
            for model in (ToothNote, Procedure, TreatmentPlanItem, Invoice, PatientLedgerEntry)
        }


@pytest.mark.parametrize("selected", [["UR5"], ["UR5", "LL3", "UL7"]], ids=["single", "batch"])
def test_explicit_reset_is_atomic_retains_all_history_and_records_neutral_not_healthy(
    api_client, auth_headers, selected
):
    patient_id = _patient(api_client, auth_headers)
    path = _path(patient_id)
    untouched = "LR6"
    all_teeth = [*selected, untouched]
    initial = api_client.post(path, headers=auth_headers, json=_action_payload(
        all_teeth, condition="implant", movement="forward", rotation="clockwise"))
    assert initial.status_code == 200
    actor_id = initial.json()["teeth"][untouched]["updated_by"]["id"]
    _seed_reset_related_records(patient_id, actor_id, all_teeth)
    # One newer observation must block the entire reset, including other teeth
    # whose revisions still match. There must be no partially cleared batch.
    advanced_tooth = selected[-1]
    changed = api_client.post(path, headers=auth_headers, json=_action_payload(
        [advanced_tooth], {advanced_tooth: 1}, rotation="anticlockwise"))
    assert changed.status_code == 200
    before_chart = api_client.get(path, headers=auth_headers).json()
    before_counts = _counts(patient_id)
    before_related = _reset_related_snapshot(patient_id)
    before_audits = [(a.id, a.before_json, a.after_json) for a in _audits(patient_id)]
    assert all(before_related.values())
    reset_payload = _action_payload(selected, {tooth: 1 for tooth in selected},
        condition="unrecorded", movement=None, rotation=None)
    rejected = api_client.post(path, headers=auth_headers, json=reset_payload)
    assert rejected.status_code == 409
    assert api_client.get(path, headers=auth_headers).json() == before_chart
    assert _counts(patient_id) == before_counts
    assert _reset_related_snapshot(patient_id) == before_related
    assert [(a.id, a.before_json, a.after_json) for a in _audits(patient_id)] == before_audits

    reset_payload["expected_revisions"][advanced_tooth] = 2
    reset_headers = {**auth_headers, "Request-Id": uuid4().hex}
    reset = api_client.post(path, headers=reset_headers, json=reset_payload)
    assert reset.status_code == 200
    after_chart = reset.json()
    for tooth in selected:
        row = after_chart["teeth"][tooth]
        assert row["condition"] == "unrecorded"
        assert row["movement"] is row["rotation"] is None
        assert row["revision"] == before_chart["teeth"][tooth]["revision"] + 1
    assert after_chart["teeth"][untouched] == before_chart["teeth"][untouched]
    assert after_chart["note_teeth"] == before_chart["note_teeth"] == sorted(all_teeth)
    assert _counts(patient_id) == before_counts
    assert _reset_related_snapshot(patient_id) == before_related
    audits = _audits(patient_id)
    assert len(audits) == len(before_audits) + 1
    assert [(a.id, a.before_json, a.after_json) for a in audits[:-1]] == before_audits
    audit = audits[-1]
    assert audit.after_json["changed_teeth"] == sorted(selected)
    assert audit.after_json["request"]["condition"] == "unrecorded"
    assert audit.after_json["request"]["movement"] is audit.after_json["request"]["rotation"] is None
    for tooth in selected:
        assert audit.before_json["teeth"][tooth] == {
            field: before_chart["teeth"][tooth][field]
            for field in ("condition", "movement", "rotation", "root_observations", "crown_observation", "revision")
        }
        assert audit.after_json["teeth"][tooth] == {
            field: after_chart["teeth"][tooth][field]
            for field in ("condition", "movement", "rotation", "root_observations", "crown_observation", "revision")
        }
        history = api_client.get(f"/patients/{patient_id}/tooth-history", headers=auth_headers,
                                 params={"tooth": tooth})
        assert history.status_code == 200
        assert len(history.json()["notes"]) == len(history.json()["procedures"]) == 1
    assert api_client.post(path, headers=reset_headers, json=reset_payload).json() == after_chart
    assert len(_audits(patient_id)) == len(audits)

    # Later position editing must retain the explicit neutral override rather
    # than expose historical missing/restored state or invent a healthy tooth.
    later = api_client.post(path, headers=auth_headers, json=_action_payload(
        selected, {tooth: after_chart["teeth"][tooth]["revision"] for tooth in selected}, movement="backward"))
    assert later.status_code == 200
    assert all(later.json()["teeth"][tooth]["condition"] == "unrecorded" for tooth in selected)
    assert _reset_related_snapshot(patient_id) == before_related


def test_unrecorded_migration_downgrade_refuses_before_any_schema_change(api_client, auth_headers, monkeypatch):
    patient_id = _patient(api_client, auth_headers)
    response = api_client.post(_path(patient_id), headers=auth_headers,
        json=_action_payload(["UR5"], condition="unrecorded", movement=None, rotation=None))
    assert response.status_code == 200
    migration_path = Path(__file__).resolve().parents[2] / "alembic/versions/0051_unrecorded_tooth_condition.py"
    spec = spec_from_file_location("unrecorded_tooth_migration", migration_path)
    assert spec is not None and spec.loader is not None
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)
    before = response.json()

    def forbid_ddl(*_args, **_kwargs):
        pytest.fail("Downgrade must refuse before attempting to alter constraints")

    # Call the real guard against synthetic data, but never allow DDL on the
    # shared isolated test schema (parallel browser tests may be using it).
    with SessionLocal() as db:
        monkeypatch.setattr(migration.op, "get_bind", lambda: db.connection())
        monkeypatch.setattr(migration.op, "drop_constraint", forbid_ddl)
        monkeypatch.setattr(migration.op, "create_check_constraint", forbid_ddl)
        with pytest.raises(RuntimeError, match="unrecorded tooth observations exist"):
            migration.downgrade()
    assert api_client.get(_path(patient_id), headers=auth_headers).json() == before
