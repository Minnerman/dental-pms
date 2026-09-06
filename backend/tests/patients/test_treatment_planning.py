"""Synthetic native-only planning: diagnosis/proposal/completion stay separate."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from uuid import uuid4
import subprocess
from threading import Event

import pytest
from sqlalchemy import event, func, select, text

from app.core.settings import settings
from app.db.session import SessionLocal, engine
from app.models.audit_log import AuditLog
from app.models.clinical import Procedure, ToothCondition, ToothNote, TreatmentPlanItem
from app.models.invoice import Invoice
from app.models.ledger import PatientLedgerEntry
from app.models.patient import Patient, PatientCategory
from app.models.r4_charting_canonical import R4ChartingCanonicalRecord
from app.models.r4_patient_mapping import R4PatientMapping
from app.models.treatment import Treatment, TreatmentFee, FeeType
from app.models.treatment_planning import PatientTreatmentPlan, TreatmentPlanItemRevision
from app.models.user import Role, User
from app.schemas.treatment_planning import PlanningTarget, PlanningItemCreate
from app.services.treatment_planning import validate_snapshot_target, create_item
from tests.patients.test_clinical_reliability import _create_patient, _create_user_headers, _set_capabilities


def headers(auth, key=None):
    return {**auth, "Request-Id": key or f"planning-test-{uuid4().hex}"}


def setup_case(client, auth, *, price=12345, fee_type=FeeType.fixed):
    patient_id = _create_patient(client, auth, f"planning-{uuid4().hex[:10]}")
    with SessionLocal() as db:
        actor = db.scalar(select(User).where(User.role == Role.superadmin))
        treatment = Treatment(name=f"Synthetic planning {uuid4().hex}", code=f"PLAN-{uuid4().hex[:10]}",
            description="Synthetic catalogue narrative", created_by_user_id=actor.id, updated_by_user_id=actor.id)
        db.add(treatment)
        db.flush()
        if fee_type is not None:
            db.add(TreatmentFee(treatment_id=treatment.id, patient_category=PatientCategory.clinic_private,
                fee_type=fee_type, amount_pence=price if fee_type == FeeType.fixed else None,
                min_amount_pence=1000 if fee_type == FeeType.range else None,
                max_amount_pence=2000 if fee_type == FeeType.range else None))
        db.commit()
        treatment_id = treatment.id
        treatment_code = treatment.code
    result = client.get(f"/patients/{patient_id}/planning/catalogue", params={"q": treatment_code}, headers=auth)
    assert result.status_code == 200
    quote = next(item for item in result.json()["items"] if item["id"] == treatment_id)
    return patient_id, quote


def start(client, auth, patient_id, key=None):
    response = client.post(f"/patients/{patient_id}/planning/start", headers=headers(auth, key), json={})
    assert response.status_code == 201, response.text
    return response.json()


def payload(quote, **overrides):
    return {"treatment_id": quote["id"], "quote_token": quote["quote_token"],
        "target": {"level": "surface", "tooth": "UR4", "surfaces": ["O", "M", "P"]},
        "drawing_kind": "filling", "fee_mode": "catalogue", **overrides}


def add(client, auth, patient_id, quote, **overrides):
    response = client.post(f"/patients/{patient_id}/planning/items", headers=headers(auth), json=payload(quote, **overrides))
    assert response.status_code == 201, response.text
    return response.json()


def counts(patient_id):
    with SessionLocal() as db:
        return tuple(db.scalar(select(func.count(model.id)).where(model.patient_id == patient_id))
            for model in (Procedure, PatientLedgerEntry, Invoice, ToothNote))


def test_snapshot_is_frozen_once_and_proposals_are_not_diagnoses_or_bills(api_client, auth_headers):
    pid, quote = setup_case(api_client, auth_headers)
    with SessionLocal() as db:
        actor = db.scalar(select(User).where(User.role == Role.superadmin))
        db.add(ToothCondition(patient_id=pid, tooth="UR4", condition="deciduous", dentition="deciduous", revision=1,
            root_observations={"1": {"condition": "filled_sound", "apicectomy": False}},
            surface_observations={"O": {"kind": "restored", "material": "amalgam", "condition": None, "defects": []}},
            created_by_user_id=actor.id, updated_by_user_id=actor.id))
        db.commit()
    first = start(api_client, auth_headers, pid)
    snapshot = deepcopy(first["plan"]["snapshot"])
    assert snapshot["native"]["teeth"]["UR4"]["dentition"] == "deciduous"
    before = counts(pid)
    item = add(api_client, auth_headers, pid, quote)
    assert item["fee_pence"] == 12345
    assert item["target"]["surfaces"] == ["M", "O", "P"]
    assert item["surface"] == "MOL"  # legacy L preserved separately from native P.
    assert item["revision"] == 1 and item["status"] == "proposed"
    with SessionLocal() as db:
        row = db.scalar(select(ToothCondition).where(ToothCondition.patient_id == pid))
        row.movement = "forward"
        row.revision += 1
        db.commit()
    repeated = start(api_client, auth_headers, pid)
    assert repeated["plan"]["id"] == first["plan"]["id"]
    assert repeated["plan"]["snapshot"] == snapshot
    assert repeated["plan"]["items"][0]["id"] == item["id"]
    assert counts(pid) == before
    with SessionLocal() as db:
        row = db.scalar(select(ToothCondition).where(ToothCondition.patient_id == pid))
        assert row.revision == 2 and row.movement == "forward" and row.dentition == "deciduous"


@pytest.mark.parametrize("kind,level,surfaces", [
    ("extraction", "tooth", []), ("implant", "tooth", []), ("root_canal", "root", []),
    ("apicectomy", "root", []), ("post_core", "root", []), ("crown", "crown", []),
    ("bridge", "crown", []), ("denture", "crown", []), ("inlay_onlay", "crown", []),
    ("veneer", "crown", []), ("sealant", "surface", ["O"]), ("other", "general", []),
])
def test_explicit_drawing_kinds_and_levels(api_client, auth_headers, kind, level, surfaces):
    pid, quote = setup_case(api_client, auth_headers)
    start(api_client, auth_headers, pid)
    item = add(api_client, auth_headers, pid, quote, drawing_kind=kind,
        target={"level": level, "tooth": None if level == "general" else "UR4", "surfaces": surfaces})
    assert item["drawing_kind"] == kind


@pytest.mark.parametrize("changes", [
    {"drawing_kind": "extraction"},
    {"target": {"level": "surface", "tooth": "UR1", "surfaces": ["O"]}},
    {"target": {"level": "surface", "tooth": "UR4", "surfaces": ["L"]}},
    {"target": {"level": "surface", "tooth": "LL4", "surfaces": ["P"]}},
    {"target": {"level": "surface", "tooth": "UR4", "surfaces": ["O", "O"]}},
    {"target": {"level": "general", "tooth": "UR4", "surfaces": []}, "drawing_kind": "other"},
    {"fee_mode": "override", "fee_pence": 10.5, "fee_reason": "Synthetic reason"},
    {"fee_mode": "override", "fee_pence": True, "fee_reason": "Synthetic reason"},
    {"fee_mode": "override", "fee_pence": -1, "fee_reason": "Synthetic reason"},
    {"fee_mode": "override", "fee_pence": 100_000_001, "fee_reason": "Synthetic reason"},
    {"unexpected": "no"},
])
def test_invalid_target_money_or_fields_are_atomic(api_client, auth_headers, changes):
    pid, quote = setup_case(api_client, auth_headers)
    start(api_client, auth_headers, pid)
    response = api_client.post(f"/patients/{pid}/planning/items", headers=headers(auth_headers), json=payload(quote, **changes))
    assert response.status_code == 422, response.text
    assert api_client.get(f"/patients/{pid}/planning", headers=auth_headers).json()["plan"]["items"] == []
    assert counts(pid) == (0, 0, 0, 0)


@pytest.mark.parametrize("state", ["missing", "implant", "unerupted"])
def test_absent_roots_and_surfaces_rejected_but_future_prosthetic_crown_allowed(api_client, auth_headers, state):
    pid, quote = setup_case(api_client, auth_headers)
    with SessionLocal() as db:
        actor = db.scalar(select(User).where(User.role == Role.superadmin))
        db.add(ToothCondition(patient_id=pid, tooth="UR4", condition=state, revision=1,
            created_by_user_id=actor.id, updated_by_user_id=actor.id))
        db.commit()
    start(api_client, auth_headers, pid)
    for kind, level, surfaces in (("filling", "surface", ["O"]), ("root_canal", "root", [])):
        response = api_client.post(f"/patients/{pid}/planning/items", headers=headers(auth_headers), json=payload(quote,
            drawing_kind=kind, target={"level": level, "tooth": "UR4", "surfaces": surfaces}))
        assert response.status_code == 422
    item = add(api_client, auth_headers, pid, quote, drawing_kind="crown", target={"level": "crown", "tooth": "UR4", "surfaces": []})
    assert item["status"] == "proposed"


@pytest.mark.parametrize("fee_type,mode,amount,reason,expected", [
    (FeeType.fixed, "catalogue", None, None, 201),
    (FeeType.fixed, "catalogue", 12346, None, 422),
    (FeeType.fixed, "override", 12001, "Synthetic agreed discount", 201),
    (FeeType.fixed, "override", 12001, " ", 422),
    (FeeType.fixed, "override", 0, "Synthetic", 422),
    (FeeType.fixed, "waived", 0, "Synthetic waiver", 201),
    (FeeType.fixed, "waived", 0, None, 422),
    (FeeType.fixed, "agreed", 1500, "Synthetic", 422),
    (FeeType.range, "catalogue", None, None, 422),
    (FeeType.range, "agreed", 1523, None, 201),
    (FeeType.range, "agreed", 2500, None, 422),
    (FeeType.range, "override", 2500, "Synthetic complex case", 201),
    (FeeType.not_applicable, "agreed", 1999, "Synthetic agreement", 201),
    (None, "agreed", 1999, None, 422),
    (None, "agreed", 1999, "Synthetic agreement", 201),
    (None, "waived", 0, "Synthetic waiver", 201),
])
def test_price_source_and_reason_are_explicit(api_client, auth_headers, fee_type, mode, amount, reason, expected):
    pid, quote = setup_case(api_client, auth_headers, fee_type=fee_type)
    start(api_client, auth_headers, pid)
    response = api_client.post(f"/patients/{pid}/planning/items", headers=headers(auth_headers), json=payload(quote,
        fee_mode=mode, fee_pence=amount, fee_reason=reason))
    assert response.status_code == expected, response.text
    if expected == 201:
        assert response.json()["fee_pence"] == (12345 if mode == "catalogue" else amount)
        assert response.json()["catalogue_snapshot"]["fee"] == quote["fee"]
    assert counts(pid) == (0, 0, 0, 0)


@pytest.mark.parametrize("mode,reason", [("catalogue", None), ("waived", "Synthetic waiver")])
def test_zero_fee_completion_still_creates_one_procedure_and_no_charge(api_client, auth_headers, mode, reason):
    pid, quote = setup_case(api_client, auth_headers, price=0 if mode == "catalogue" else 12345)
    start(api_client, auth_headers, pid)
    item = add(api_client, auth_headers, pid, quote, fee_mode=mode, fee_pence=0, fee_reason=reason)
    response = api_client.patch(f"/patients/{pid}/planning/items/{item['id']}", headers=headers(auth_headers),
        json={"expected_revision": 1, "status": "completed", "confirm_finance": True})
    assert response.status_code == 200, response.text
    assert counts(pid) == (1, 0, 0, 0)


def test_completion_revision_replay_finality_and_immutable_fee_history(api_client, auth_headers):
    pid, quote = setup_case(api_client, auth_headers)
    snapshot = start(api_client, auth_headers, pid)["plan"]["snapshot"]
    item = add(api_client, auth_headers, pid, quote)
    path = f"/patients/{pid}/planning/items/{item['id']}"
    fee_change = {"expected_revision": 1, "fee_mode": "override", "fee_pence": 9876, "fee_reason": "Synthetic patient agreement"}
    response = api_client.patch(path, headers=headers(auth_headers), json=fee_change)
    assert response.status_code == 200, response.text
    assert response.json()["revision"] == 2
    stale = api_client.patch(path, headers=headers(auth_headers), json={"expected_revision": 1, "status": "completed", "confirm_finance": True})
    assert stale.status_code == 409
    no_confirm = api_client.patch(path, headers=headers(auth_headers), json={"expected_revision": 2, "status": "completed"})
    assert no_confirm.status_code == 422
    key = headers(auth_headers)
    completion = {"expected_revision": 2, "status": "completed", "confirm_finance": True}
    complete = api_client.patch(path, headers=key, json=completion)
    repeated = api_client.patch(path, headers=key, json=completion)
    assert complete.status_code == repeated.status_code == 200
    assert complete.json()["revision"] == 3
    assert complete.json()["completed_procedure_id"] == repeated.json()["completed_procedure_id"]
    unchanged = api_client.patch(path, headers=headers(auth_headers), json={**completion, "expected_revision": 3})
    assert unchanged.status_code == 200 and unchanged.json()["revision"] == 3
    final = api_client.patch(path, headers=headers(auth_headers), json={**fee_change, "expected_revision": 3})
    # Same values are harmless no-ops even after finalization.
    assert final.status_code == 200
    changed = api_client.patch(path, headers=headers(auth_headers), json={**fee_change, "expected_revision": 3, "fee_pence": 9000})
    assert changed.status_code == 409
    assert counts(pid) == (1, 1, 0, 0)
    with SessionLocal() as db:
        charge = db.scalar(select(PatientLedgerEntry).where(PatientLedgerEntry.patient_id == pid))
        assert charge.amount_pence == 9876 and charge.reference == f"TREATMENT-PLAN:{item['id']}"
        assert db.scalar(select(PatientTreatmentPlan).where(PatientTreatmentPlan.patient_id == pid)).snapshot == snapshot
    history = api_client.get(f"{path}/history?limit=2", headers=auth_headers).json()
    assert [row["revision"] for row in history["items"]] == [3, 2]
    assert history["items"][0]["snapshot"]["fee_reason"] == "Synthetic patient agreement"
    assert history["next_before_revision"] == 2
    earlier = api_client.get(f"{path}/history?before_revision=2", headers=auth_headers).json()
    assert earlier["items"][0]["snapshot"]["fee_pence"] == 12345


def test_request_collision_target_lock_and_old_endpoint_cannot_bypass_guards(api_client, auth_headers):
    pid, quote = setup_case(api_client, auth_headers)
    start_key = f"planning-start-{uuid4().hex}"
    start(api_client, auth_headers, pid, start_key)
    collision = api_client.post(f"/patients/{pid}/planning/items", headers=headers(auth_headers, start_key), json=payload(quote))
    assert collision.status_code == 409
    key = headers(auth_headers)
    body = payload(quote)
    first = api_client.post(f"/patients/{pid}/planning/items", headers=key, json=body)
    repeated = api_client.post(f"/patients/{pid}/planning/items", headers=key, json=body)
    assert first.status_code == repeated.status_code == 201
    assert first.json()["id"] == repeated.json()["id"]
    collision = api_client.post(f"/patients/{pid}/planning/items", headers=key, json={**body, "drawing_kind": "other"})
    assert collision.status_code == 409
    item_id = first.json()["id"]
    legacy = api_client.patch(f"/treatment-plan/{item_id}", headers=auth_headers, json={"fee_pence": 1, "status": "completed"})
    assert legacy.status_code == 409
    altered = api_client.patch(f"/patients/{pid}/planning/items/{item_id}", headers=headers(auth_headers),
        json={"expected_revision": 1, "target": {"level": "tooth", "tooth": "LL3", "surfaces": []}})
    assert altered.status_code == 422
    assert counts(pid) == (0, 0, 0, 0)


def test_catalogue_change_and_category_change_require_review_and_never_reprice_saved_items(api_client, auth_headers):
    pid, quote = setup_case(api_client, auth_headers)
    start(api_client, auth_headers, pid)
    item = add(api_client, auth_headers, pid, quote)
    with SessionLocal() as db:
        db.scalar(select(TreatmentFee).where(TreatmentFee.treatment_id == quote["id"])).amount_pence = 22222
        db.commit()
    stale_quote = api_client.post(f"/patients/{pid}/planning/items", headers=headers(auth_headers), json=payload(quote))
    assert stale_quote.status_code == 409
    assert api_client.get(f"/patients/{pid}/planning", headers=auth_headers).json()["plan"]["items"][0]["fee_pence"] == item["fee_pence"]
    latest = next(row for row in api_client.get(f"/patients/{pid}/planning/catalogue", params={"q": quote["code"]}, headers=auth_headers).json()["items"] if row["id"] == quote["id"])
    with SessionLocal() as db:
        db.get(Patient, pid).patient_category = PatientCategory.denplan
        db.commit()
    category_changed = api_client.post(f"/patients/{pid}/planning/items", headers=headers(auth_headers), json=payload(latest))
    assert category_changed.status_code == 409


def test_locked_fee_refresh_detects_a_concurrent_catalogue_change(api_client, auth_headers):
    from fastapi import HTTPException
    pid, quote = setup_case(api_client, auth_headers)
    start(api_client, auth_headers, pid)
    reached_fee_lock = Event()

    def observed(_connection, _cursor, statement, _parameters, _context, _many):
        if "FROM treatment_fees" in statement and "FOR SHARE" in statement:
            reached_fee_lock.set()

    def attempt():
        with SessionLocal() as session:
            actor = session.scalar(select(User).where(User.role == Role.superadmin))
            try:
                create_item(session, pid, PlanningItemCreate(**payload(quote)), actor, f"planning-concurrency-{uuid4().hex}")
                return 201
            except HTTPException as error:
                return error.status_code

    event.listen(engine, "before_cursor_execute", observed)
    try:
        with SessionLocal() as changing, ThreadPoolExecutor(max_workers=1) as executor:
            fee = changing.scalar(select(TreatmentFee).where(TreatmentFee.treatment_id == quote["id"]))
            fee.amount_pence = 22222
            changing.flush()  # Hold the fee row while the proposal reaches it.
            pending = executor.submit(attempt)
            assert reached_fee_lock.wait(5), "proposal did not reach the quoted fee lock"
            changing.commit()
            assert pending.result(timeout=10) == 409
    finally:
        event.remove(engine, "before_cursor_execute", observed)
    assert api_client.get(f"/patients/{pid}/planning", headers=auth_headers).json()["plan"]["items"] == []


def test_capabilities_cross_patient_archive_and_earlier_items(api_client, auth_headers):
    pid, quote = setup_case(api_client, auth_headers)
    old = api_client.post(f"/patients/{pid}/treatment-plan", headers=auth_headers,
        json={"procedure_code": "EARLIER", "description": "Earlier synthetic plan", "fee_pence": 500})
    assert old.status_code == 201
    workspace = start(api_client, auth_headers, pid)
    assert workspace["earlier_items_total"] == 1 and workspace["earlier_items"][0]["id"] == old.json()["id"]
    assert workspace["earlier_items"][0]["plan_id"] is None
    item = add(api_client, auth_headers, pid, quote)
    user_id, restricted = _create_user_headers(api_client)
    _set_capabilities(user_id, ["clinical.write"])
    assert api_client.get(f"/patients/{pid}/planning", headers=restricted).status_code == 403
    assert api_client.post(f"/patients/{pid}/planning/start", headers=headers(restricted), json={}).status_code == 403
    _set_capabilities(user_id, ["clinical.view"])
    assert api_client.get(f"/patients/{pid}/planning/catalogue", headers=restricted).status_code == 200
    assert api_client.get("/treatments", headers=restricted).status_code == 403
    assert api_client.post("/treatments", headers=restricted, json={"name": "Unauthorized"}).status_code == 403
    assert api_client.post(f"/patients/{pid}/planning/items", headers=headers(restricted), json=payload(quote)).status_code == 403
    _set_capabilities(user_id, ["clinical.view", "clinical.write"])
    denied = api_client.patch(f"/patients/{pid}/planning/items/{item['id']}", headers=headers(restricted),
        json={"expected_revision": 1, "status": "completed", "confirm_finance": True})
    assert denied.status_code == 403
    other_pid = _create_patient(api_client, auth_headers, f"other-{uuid4().hex[:8]}")
    assert api_client.get(f"/patients/{other_pid}/planning/items/{item['id']}/history", headers=auth_headers).status_code == 404
    assert api_client.patch(f"/patients/{other_pid}/planning/items/{item['id']}", headers=headers(auth_headers), json={"expected_revision": 1, "status": "accepted"}).status_code == 404
    with SessionLocal() as db:
        db.get(Patient, pid).deleted_at = datetime.now(timezone.utc)
        db.commit()
    assert api_client.get(f"/patients/{pid}/planning", headers=auth_headers).status_code == 404
    assert api_client.post(f"/patients/{pid}/planning/start", headers=headers(auth_headers), json={}).status_code == 404
    assert counts(pid) == (0, 0, 0, 0)


def test_snapshot_uses_only_already_stored_legacy_projection_and_preserves_unknowns(api_client, auth_headers, monkeypatch):
    pid, _quote = setup_case(api_client, auth_headers)
    monkeypatch.setattr(settings, "feature_charting_viewer", True)
    code = 70_000_000 + pid
    source_id = uuid4().hex
    with SessionLocal() as db:
        row = db.get(Patient, pid)
        row.legacy_source, row.legacy_id = "r4", str(code)
        db.add(R4ChartingCanonicalRecord(unique_key=source_id, domain="restorative_treatment", r4_source="synthetic.local",
            r4_source_id=source_id, legacy_patient_code=code, patient_id=pid, tooth=14,
            payload={"description": "Unmapped synthetic restoration", "raw_unmapped": "保持原文"}))
        db.commit()
    frozen = start(api_client, auth_headers, pid)["plan"]["snapshot"]
    assert frozen["coverage"]["legacy"] == "captured"
    assert frozen["legacy"]["legacy_patient_code"] == code
    assert "14" in frozen["legacy"]["teeth"]
    assert frozen["native"]["teeth"] == {}
    with SessionLocal() as db:
        stored = db.scalar(select(R4ChartingCanonicalRecord).where(R4ChartingCanonicalRecord.unique_key == source_id))
        assert stored.payload["raw_unmapped"] == "保持原文"
        assert stored.recorded_at is None
    monkeypatch.setattr(settings, "feature_charting_viewer", False)
    hidden = api_client.get(f"/patients/{pid}/planning", headers=auth_headers).json()["plan"]["snapshot"]
    assert hidden["legacy"] is None and hidden["coverage"]["legacy"] == "unavailable"
    with SessionLocal() as db:
        assert db.scalar(select(PatientTreatmentPlan).where(PatientTreatmentPlan.patient_id == pid)).snapshot == frozen


@pytest.mark.parametrize("conflict", ["canonical_patient", "mapping_patient", "mapping_code"])
def test_conflicting_legacy_linkage_is_unavailable_not_other_patient_snapshot(api_client, auth_headers, monkeypatch, conflict):
    pid, _quote = setup_case(api_client, auth_headers)
    other = _create_patient(api_client, auth_headers, f"planning-other-{uuid4().hex[:8]}")
    monkeypatch.setattr(settings, "feature_charting_viewer", True)
    code = 70_000_000 + pid
    with SessionLocal() as db:
        actor = db.scalar(select(User).where(User.role == Role.superadmin))
        row = db.get(Patient, pid)
        row.legacy_source, row.legacy_id = "r4", str(code)
        if conflict == "canonical_patient":
            source = uuid4().hex
            db.add(R4ChartingCanonicalRecord(unique_key=source, domain="restorative_treatment", r4_source="synthetic.local",
                r4_source_id=source, legacy_patient_code=code, patient_id=other, tooth=14,
                payload={"description": "Conflicting synthetic source"}))
        else:
            db.add(R4PatientMapping(legacy_source="r4", legacy_patient_code=code if conflict == "mapping_patient" else code + 1_000_000,
                patient_id=other if conflict == "mapping_patient" else pid, created_by_user_id=actor.id, updated_by_user_id=actor.id))
        db.commit()
    snapshot = start(api_client, auth_headers, pid)["plan"]["snapshot"]
    assert snapshot["legacy"] is None
    assert snapshot["coverage"]["legacy"] == "unavailable"
    assert "linkage" in snapshot["coverage"]["legacy_reason"]


@pytest.mark.parametrize("level,native,legacy,allowed", [
    ("root", {"root_observations": {"1": {"condition": "filled_sound", "apicectomy": False}}}, {"restorations": [{"type": "implant"}]}, True),
    ("surface", {"root_observations": {"1": {"condition": None, "apicectomy": False}}}, {"missing": True, "restorations": [{"type": "implant"}]}, True),
    ("root", {"crown_observation": {"kind": "metal", "issues": []}}, {"missing": True}, True),
    ("surface", {"surface_observations": {"O": {"kind": None}}}, {"missing": True}, True),
    ("root", {"surface_observations": {"O": {"kind": "restored"}}}, {"missing": True}, False),
    ("root", {"crown_observation": {"kind": "metal", "issues": []}}, {"restorations": [{"type": "implant"}]}, False),
    ("surface", {"dentition": "deciduous"}, {"restorations": [{"type": "implant"}]}, True),
    ("root", {"condition": "implant", "root_observations": {"1": {"condition": "filled_sound"}}}, {}, False),
])
def test_independent_native_evidence_wins_without_granting_roots_from_surface_only(level, native, legacy, allowed):
    from fastapi import HTTPException
    target = PlanningTarget(level=level, tooth="UR4", surfaces=["O"] if level == "surface" else [])
    snapshot = {"native": {"teeth": {"UR4": native}}, "legacy": {"teeth": {"14": legacy}}}
    if allowed:
        validate_snapshot_target(snapshot, target)
    else:
        with pytest.raises(HTTPException) as error:
            validate_snapshot_target(snapshot, target)
        assert error.value.status_code == 422


@pytest.mark.parametrize("status", ["declined", "cancelled"])
def test_final_non_completed_states_cannot_be_completed_or_repriced(api_client, auth_headers, status):
    pid, quote = setup_case(api_client, auth_headers)
    start(api_client, auth_headers, pid)
    item = add(api_client, auth_headers, pid, quote)
    path = f"/patients/{pid}/planning/items/{item['id']}"
    saved = api_client.patch(path, headers=headers(auth_headers), json={"expected_revision": 1, "status": status})
    assert saved.status_code == 200 and saved.json()["revision"] == 2
    assert api_client.patch(path, headers=headers(auth_headers), json={"expected_revision": 2, "status": "completed", "confirm_finance": True}).status_code == 409
    assert api_client.patch(path, headers=headers(auth_headers), json={"expected_revision": 2, "fee_mode": "waived", "fee_reason": "Synthetic waiver"}).status_code == 409
    assert counts(pid) == (0, 0, 0, 0)


def test_populated_planning_migration_downgrade_refuses_without_data_loss(api_client, auth_headers):
    pid, quote = setup_case(api_client, auth_headers)
    snapshot = start(api_client, auth_headers, pid)["plan"]["snapshot"]
    item = add(api_client, auth_headers, pid, quote)
    result = subprocess.run(["alembic", "downgrade", "0058_clinical_note_revisions"], capture_output=True, text=True)
    assert result.returncode != 0
    assert ("Cannot downgrade: native planning" in result.stderr
            or "Cannot downgrade: treatment completion cycles" in result.stderr)
    with SessionLocal() as db:
        assert db.execute(text("SELECT version_num FROM alembic_version")).scalar() == "0060_treatment_completion_reversals"
        assert db.scalar(select(PatientTreatmentPlan).where(PatientTreatmentPlan.patient_id == pid)).snapshot == snapshot
        assert db.get(TreatmentPlanItem, item["id"]).revision == 1
