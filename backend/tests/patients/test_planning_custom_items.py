"""Synthetic miscellaneous treatments share the existing audited lifecycle."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text

from app.db.session import SessionLocal
from app.models.audit_log import AuditLog
from app.models.clinical import Procedure, ProcedureStatus, TreatmentPlanItem
from app.models.ledger import PatientLedgerEntry
from app.models.patient import Patient
from app.models.treatment import Treatment, TreatmentFee
from app.models.treatment_planning import TreatmentPlanItemRevision
from tests.patients.test_clinical_reliability import _create_patient, _create_user_headers, _set_capabilities
from tests.patients.test_treatment_planning import counts, headers, start
from tests.patients.test_treatment_uncomplete import change, undo


def custom_patient(client, auth):
    pid = _create_patient(client, auth, f"miscellaneous-{uuid4().hex[:10]}")
    start(client, auth, pid)
    return pid


def custom(client, auth, pid, *, key=None, **patch):
    return client.post(f"/patients/{pid}/planning/custom-items", headers=headers(auth, key), json={
        "description": "Synthetic miscellaneous review", "fee_pence": 1250, "fee_mode": "agreed", **patch})


def test_custom_proposal_has_explicit_non_catalogue_source_and_no_collateral_writes(api_client, auth_headers):
    pid = custom_patient(api_client, auth_headers)
    before = counts(pid)
    baseline = api_client.get(f"/patients/{pid}/clinical/tooth-conditions", headers=auth_headers).json()
    snapshot = api_client.get(f"/patients/{pid}/planning", headers=auth_headers).json()["plan"]["snapshot"]
    with SessionLocal() as db:
        catalogue_before = tuple(db.scalar(select(func.count(model.id))) for model in (Treatment, TreatmentFee))
    response = custom(api_client, auth_headers, pid, description="  Synthetic review — α\nSecond line  ")
    assert response.status_code == 201, response.text
    item = response.json()
    assert item["description"] == "Synthetic review — α\nSecond line"
    assert item["treatment_id"] is None and item["catalogue_snapshot"] == {"source": "custom"}
    assert item["target"] == {"level": "general", "tooth": None, "surfaces": []}
    assert item["drawing_kind"] == "other" and item["procedure_code"] == "MISCELLANEOUS"
    assert item["status"] == "proposed" and item["revision"] == 1
    assert item["fee_mode"] == "agreed" and item["fee_reason"] is None
    assert item["tooth"] is None and item["surface"] is None
    assert counts(pid) == before
    workspace = api_client.get(f"/patients/{pid}/planning", headers=auth_headers).json()
    assert workspace["plan"]["items"] == [item] and workspace["plan"]["snapshot"] == snapshot
    assert api_client.get(f"/patients/{pid}/clinical/tooth-conditions", headers=auth_headers).json() == baseline
    with SessionLocal() as db:
        assert tuple(db.scalar(select(func.count(model.id))) for model in (Treatment, TreatmentFee)) == catalogue_before
        revision = db.scalar(select(TreatmentPlanItemRevision).where(TreatmentPlanItemRevision.item_id == item["id"]))
        assert revision.snapshot["catalogue_snapshot"] == {"source": "custom"}
        assert revision.snapshot["description"] == item["description"]
        audit = db.scalar(select(AuditLog).where(AuditLog.entity_id == str(pid), AuditLog.action == "clinical.planning.custom_item.created"))
        assert audit.after_json["source"] == "custom" and audit.after_json["fee_pence"] == 1250
        assert "description" not in audit.after_json  # Full text belongs to immutable item history.
        assert db.execute(text("SELECT version_num FROM alembic_version")).scalar() == "0061_treatment_index_effective_fees"


@pytest.mark.parametrize("patch", [
    {"description": ""}, {"description": " \n "}, {"description": "x" * 2001},
    {"fee_pence": 12.5}, {"fee_pence": True}, {"fee_pence": -1}, {"fee_pence": 100_000_001},
    {"fee_pence": 0}, {"fee_pence": None}, {"fee_mode": "catalogue"}, {"fee_mode": "override"},
    {"fee_mode": "waived", "fee_pence": 10, "fee_reason": "Synthetic waiver"},
    {"fee_mode": "waived", "fee_pence": 0},
    {"fee_mode": "waived", "fee_pence": 0, "fee_reason": "  "},
    {"fee_reason": "x" * 501}, {"target": {"level": "surface", "tooth": "UR4", "surfaces": ["I"]}},
    {"treatment_id": 1}, {"catalogue_snapshot": {"fee": {"type": "FIXED", "amount_pence": 1}}},
    {"description": None},
])
def test_invalid_custom_target_source_text_or_fee_rejected_atomically(api_client, auth_headers, patch):
    pid = custom_patient(api_client, auth_headers)
    assert custom(api_client, auth_headers, pid, **patch).status_code == 422
    assert counts(pid) == (0, 0, 0, 0)
    assert api_client.get(f"/patients/{pid}/planning", headers=auth_headers).json()["plan"]["items"] == []


def test_maximum_description_and_fee_and_optional_reason_are_supported(api_client, auth_headers):
    pid = custom_patient(api_client, auth_headers)
    response = custom(api_client, auth_headers, pid, description="x" * 2000, fee_pence=100_000_000, fee_reason="  Explicit agreed fee  ")
    assert response.status_code == 201
    assert response.json()["fee_reason"] == "Explicit agreed fee"


def test_custom_fee_edits_completion_correction_and_recompletion_share_existing_guards(api_client, auth_headers):
    pid = custom_patient(api_client, auth_headers)
    item = custom(api_client, auth_headers, pid).json()
    for mode in ("catalogue", "override"):
        assert change(api_client, auth_headers, pid, item, fee_mode=mode, fee_pence=1550, fee_reason="Synthetic reason").status_code == 422
    assert change(api_client, auth_headers, pid, item, description="Do not rewrite the saved description").status_code == 422
    edited = change(api_client, auth_headers, pid, item, fee_mode="agreed", fee_pence=1550)
    assert edited.status_code == 200, edited.text
    assert edited.json()["revision"] == 2 and edited.json()["fee_pence"] == 1550
    assert change(api_client, auth_headers, pid, item, fee_mode="agreed", fee_pence=1650).status_code == 409
    assert counts(pid) == (0, 0, 0, 0)
    complete = change(api_client, auth_headers, pid, edited.json(), status="completed", confirm_finance=True)
    assert complete.status_code == 200, complete.text
    completed = complete.json()
    assert change(api_client, auth_headers, pid, completed, fee_mode="agreed", fee_pence=1650).status_code == 409
    corrected = undo(api_client, auth_headers, pid, completed)
    assert corrected.status_code == 200, corrected.text
    restored = corrected.json()
    assert restored["status"] == "proposed" and restored["catalogue_snapshot"] == {"source": "custom"}
    assert restored["description"] == item["description"] and restored["completed_procedure_id"] is None
    revised = change(api_client, auth_headers, pid, restored, fee_mode="agreed", fee_pence=1650)
    assert revised.status_code == 200
    recompleted = change(api_client, auth_headers, pid, revised.json(), status="completed", confirm_finance=True)
    assert recompleted.status_code == 200
    with SessionLocal() as db:
        procedures = list(db.scalars(select(Procedure).where(Procedure.patient_id == pid).order_by(Procedure.id)))
        assert [row.status for row in procedures] == [ProcedureStatus.voided, ProcedureStatus.completed]
        assert [row.fee_pence for row in procedures] == [1550, 1650]
        assert all(row.tooth is None and row.surface is None and row.description == item["description"]
                   and row.procedure_code == "MISCELLANEOUS" for row in procedures)
        ledger = list(db.scalars(select(PatientLedgerEntry).where(PatientLedgerEntry.patient_id == pid).order_by(PatientLedgerEntry.id)))
        assert [row.amount_pence for row in ledger] == [1550, -1550, 1650]
        versions = list(db.scalars(select(TreatmentPlanItemRevision).where(TreatmentPlanItemRevision.item_id == item["id"]).order_by(TreatmentPlanItemRevision.revision)))
        assert [row.revision for row in versions] == [1, 2, 3, 4, 5, 6]
        assert all(row.snapshot["catalogue_snapshot"] == {"source": "custom"} for row in versions)


def test_explicit_zero_waiver_has_history_but_no_charge_or_adjustment(api_client, auth_headers):
    pid = custom_patient(api_client, auth_headers)
    response = custom(api_client, auth_headers, pid, fee_pence=0, fee_mode="waived", fee_reason="Synthetic courtesy waiver")
    assert response.status_code == 201
    item = change(api_client, auth_headers, pid, response.json(), status="accepted").json()
    completed = change(api_client, auth_headers, pid, item, status="completed", confirm_finance=True).json()
    corrected = undo(api_client, auth_headers, pid, completed)
    assert corrected.status_code == 200 and corrected.json()["status"] == "accepted"
    assert counts(pid) == (1, 0, 0, 0)
    assert corrected.json()["fee_mode"] == "waived" and corrected.json()["fee_reason"] == "Synthetic courtesy waiver"


def test_custom_replay_collision_concurrent_requests_and_missing_workspace(api_client, auth_headers):
    pid = _create_patient(api_client, auth_headers, f"custom-no-workspace-{uuid4().hex[:8]}")
    assert custom(api_client, auth_headers, pid).status_code == 409
    start(api_client, auth_headers, pid)
    key = f"custom-create-{uuid4().hex}"
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(lambda _: custom(api_client, auth_headers, pid, key=key), range(2)))
    assert [result.status_code for result in responses] == [201, 201]
    assert responses[0].json() == responses[1].json()
    item = responses[0].json()
    assert custom(api_client, auth_headers, pid, key=key, description="Different description").status_code == 409
    assert custom(api_client, auth_headers, pid, key=key, fee_pence=1260).status_code == 409
    collision = api_client.patch(f"/patients/{pid}/planning/items/{item['id']}", headers=headers(auth_headers, key),
        json={"expected_revision": 1, "status": "accepted"})
    assert collision.status_code == 409
    no_id = api_client.post(f"/patients/{pid}/planning/custom-items", headers=auth_headers,
        json={"description": "Synthetic", "fee_pence": 1, "fee_mode": "agreed"})
    assert no_id.status_code == 422
    with SessionLocal() as db:
        assert db.scalar(select(func.count(TreatmentPlanItem.id)).where(TreatmentPlanItem.patient_id == pid)) == 1
    assert counts(pid) == (0, 0, 0, 0)


def test_custom_capabilities_archived_patient_and_cross_patient(api_client, auth_headers):
    pid = custom_patient(api_client, auth_headers)
    user_id, restricted = _create_user_headers(api_client)
    for caps in (["clinical.view"], ["clinical.write"]):
        _set_capabilities(user_id, caps)
        assert custom(api_client, restricted, pid).status_code == 403
    _set_capabilities(user_id, ["clinical.view", "clinical.write"])
    response = custom(api_client, restricted, pid)
    assert response.status_code == 201
    item = response.json()
    assert change(api_client, restricted, pid, item, status="completed", confirm_finance=True).status_code == 403
    other_pid = custom_patient(api_client, auth_headers)
    assert change(api_client, auth_headers, other_pid, item, fee_mode="agreed", fee_pence=1400).status_code == 404
    completed = change(api_client, auth_headers, pid, item, status="completed", confirm_finance=True).json()
    assert undo(api_client, restricted, pid, completed).status_code == 403
    with SessionLocal() as db:
        db.get(Patient, pid).deleted_at = datetime.now(timezone.utc)
        db.commit()
    assert custom(api_client, auth_headers, pid).status_code == 404
    assert undo(api_client, auth_headers, pid, completed).status_code == 404
