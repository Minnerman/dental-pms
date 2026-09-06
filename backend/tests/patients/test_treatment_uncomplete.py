"""Native, synthetic correction cycles: history survives; no refunds are made."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from uuid import uuid4
import subprocess

import pytest
from sqlalchemy import func, select, text

from app.db.session import SessionLocal
from app.models.audit_log import AuditLog
from app.models.clinical import Procedure, ProcedureStatus, TreatmentPlanItem, TreatmentPlanStatus
from app.models.invoice import Invoice
from app.models.ledger import LedgerEntryType, PatientLedgerEntry
from app.models.patient import Patient
from app.models.treatment_planning import TreatmentPlanCompletion, TreatmentPlanCompletionReversal
from app.models.user import User
from app.services.treatment_planning import item_out, save_revision
from tests.patients.test_treatment_planning import setup_case, start, add, headers, counts
from tests.patients.test_clinical_reliability import _create_user_headers, _set_capabilities


def change(client, auth, pid, item, **patch):
    return client.patch(f"/patients/{pid}/planning/items/{item['id']}", headers=headers(auth),
        json={"expected_revision": item["revision"], **patch})


def completed_case(client, auth, *, accepted=False, price=8200, legacy=False):
    pid, quote = setup_case(client, auth, price=price)
    snapshot = start(client, auth, pid)["plan"]["snapshot"]
    item = add(client, auth, pid, quote)
    if accepted:
        response = change(client, auth, pid, item, status="accepted")
        assert response.status_code == 200
        item = response.json()
    if legacy:
        # Reproduce the exact 0059 completion shape, before cycle tables existed.
        # No deletion of newly recorded history is used to manufacture a fixture.
        with SessionLocal() as db:
            row = db.get(TreatmentPlanItem, item["id"])
            actor = db.get(User, row.created_by_user_id)
            proc = Procedure(patient_id=pid, appointment_id=row.appointment_id, tooth=row.tooth,
                surface=row.surface, procedure_code=row.procedure_code, description=row.description,
                fee_pence=row.fee_pence, status=ProcedureStatus.completed,
                performed_at=datetime.now(timezone.utc), created_by_user_id=actor.id)
            db.add(proc)
            db.flush()
            if price:
                db.add(PatientLedgerEntry(patient_id=pid, entry_type=LedgerEntryType.charge,
                    amount_pence=price, reference=f"TREATMENT-PLAN:{row.id}",
                    created_by_user_id=actor.id, updated_by_user_id=actor.id))
            row.status = TreatmentPlanStatus.completed
            row.completed_procedure_id = proc.id
            row.revision += 1
            row.updated_by_user_id = actor.id
            save_revision(db, row, actor)
            db.commit()
            item = item_out(row).model_dump(mode="json")
    else:
        response = change(client, auth, pid, item, status="completed", confirm_finance=True)
        assert response.status_code == 200, response.text
        item = response.json()
    return pid, item, snapshot


def undo(client, auth, pid, item, *, key=None, **patch):
    return client.post(f"/patients/{pid}/planning/items/{item['id']}/uncomplete", headers=headers(auth, key),
        json={"expected_revision": item["revision"], "reason": "Synthetic mistaken completion", "confirm_finance": True, **patch})


@pytest.mark.parametrize("accepted,legacy,price", [(False, False, 8200), (True, False, 8200),
    (False, True, 8200), (True, True, 8200), (False, False, 0), (True, True, 0)])
def test_complete_correct_recomplete_preserves_every_source(api_client, auth_headers, accepted, legacy, price):
    pid, item, snapshot = completed_case(api_client, auth_headers, accepted=accepted, legacy=legacy, price=price)
    baseline = api_client.get(f"/patients/{pid}/clinical/tooth-conditions", headers=auth_headers).json()
    with SessionLocal() as db:
        proc = db.get(Procedure, item["completed_procedure_id"])
        original = {key: getattr(proc, key) for key in ("patient_id", "tooth", "surface", "description",
            "procedure_code", "fee_pence", "performed_at", "created_by_user_id")}
        charge = db.scalar(select(PatientLedgerEntry).where(PatientLedgerEntry.patient_id == pid))
        saved_charge = (charge.id, charge.amount_pence, charge.reference, charge.created_at) if charge else None
        # An unallocated payment is not refunded or reassigned by Uncomplete.
        actor = proc.created_by_user_id
        payment = PatientLedgerEntry(patient_id=pid, entry_type=LedgerEntryType.payment, amount_pence=-1000,
            reference=f"SYNTHETIC-PAYMENT-{uuid4().hex}", created_by_user_id=actor, updated_by_user_id=actor)
        db.add(payment)
        db.commit()
        payment_id = payment.id
    result = undo(api_client, auth_headers, pid, item)
    assert result.status_code == 200, result.text
    restored = result.json()
    assert restored["status"] == ("accepted" if accepted else "proposed")
    assert restored["revision"] == item["revision"] + 1 and restored["completed_procedure_id"] is None
    with SessionLocal() as db:
        proc = db.get(Procedure, item["completed_procedure_id"])
        assert proc.status == ProcedureStatus.voided
        assert {key: getattr(proc, key) for key in original} == original
        assert db.get(PatientLedgerEntry, payment_id).amount_pence == -1000
        if saved_charge:
            charge = db.get(PatientLedgerEntry, saved_charge[0])
            assert (charge.id, charge.amount_pence, charge.reference, charge.created_at) == saved_charge
        reversal = db.scalar(select(PatientLedgerEntry).where(PatientLedgerEntry.reference == f"TREATMENT-PLAN:{item['id']}:C1:REVERSAL"))
        assert (reversal.amount_pence if reversal else 0) == -price
        assert db.scalar(select(func.sum(PatientLedgerEntry.amount_pence)).where(PatientLedgerEntry.patient_id == pid)) == -1000
        assert db.scalar(select(func.count(Invoice.id)).where(Invoice.patient_id == pid)) == 0
        audit = db.scalar(select(AuditLog).where(AuditLog.entity_id == str(pid), AuditLog.action == "clinical.planning.item.uncompleted"))
        assert audit.before_json["status"] == "completed" and audit.after_json["status"] == restored["status"]
    assert api_client.get(f"/patients/{pid}/clinical/summary", headers=auth_headers).json()["recent_procedures"] == []
    assert api_client.get(f"/patients/{pid}/tooth-history", params={"tooth": "UR4"}, headers=auth_headers).json()["procedures"] == []
    journal = api_client.get(f"/patients/{pid}/clinical-journal", headers=auth_headers).json()
    entry = next(row for row in journal["items"] if row["source_kind"] == "procedure")
    assert entry["title"] == "Voided procedure" and entry["details"]["status"] == "voided"
    assert entry["details"]["completion_correction"]["reason"] == "Synthetic mistaken completion"
    assert entry["body"] == original["description"]
    history = api_client.get(f"/patients/{pid}/planning/items/{item['id']}/history", headers=auth_headers).json()["items"]
    assert history[0]["snapshot"]["completion_correction"]["voided_procedure_id"] == item["completed_procedure_id"]
    response = change(api_client, auth_headers, pid, restored, status="completed", confirm_finance=True)
    assert response.status_code == 200, response.text
    assert response.json()["completed_procedure_id"] != item["completed_procedure_id"]
    with SessionLocal() as db:
        cycles = list(db.scalars(select(TreatmentPlanCompletion).where(TreatmentPlanCompletion.item_id == item["id"]).order_by(TreatmentPlanCompletion.cycle)))
        assert [cycle.cycle for cycle in cycles] == [1, 2]
        assert db.scalar(select(func.sum(PatientLedgerEntry.amount_pence)).where(PatientLedgerEntry.patient_id == pid)) == price - 1000
        if price:
            assert db.scalar(select(PatientLedgerEntry.amount_pence).where(PatientLedgerEntry.reference == f"TREATMENT-PLAN:{item['id']}:C2")) == price
    assert api_client.get(f"/patients/{pid}/planning", headers=auth_headers).json()["plan"]["snapshot"] == snapshot
    assert api_client.get(f"/patients/{pid}/clinical/tooth-conditions", headers=auth_headers).json() == baseline


def test_replay_collision_stale_and_concurrent_corrections(api_client, auth_headers):
    pid, item, _ = completed_case(api_client, auth_headers)
    key = f"undo-{uuid4().hex}"
    first = undo(api_client, auth_headers, pid, item, key=key)
    assert first.status_code == 200
    assert undo(api_client, auth_headers, pid, item, key=key).json() == first.json()
    assert undo(api_client, auth_headers, pid, item, key=key, reason="Different request").status_code == 409
    assert undo(api_client, auth_headers, pid, item).status_code == 409
    cross = api_client.patch(f"/patients/{pid}/planning/items/{item['id']}", headers=headers(auth_headers, key),
        json={"expected_revision": first.json()["revision"], "status": "completed", "confirm_finance": True})
    assert cross.status_code == 409
    again = change(api_client, auth_headers, pid, first.json(), status="completed", confirm_finance=True).json()
    # Replaying the old correction after another completion cannot undo cycle 2.
    before_retry = counts(pid)
    old_retry = undo(api_client, auth_headers, pid, item, key=key)
    assert old_retry.status_code == 200 and old_retry.json()["status"] == "completed"
    assert old_retry.json()["revision"] == again["revision"] and counts(pid) == before_retry
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(lambda _: undo(api_client, auth_headers, pid, again), range(2)))
    assert sorted(response.status_code for response in responses) == [200, 409]
    restored = next(response.json() for response in responses if response.status_code == 200)
    with ThreadPoolExecutor(max_workers=2) as executor:
        completing = executor.submit(change, api_client, auth_headers, pid, restored, status="completed", confirm_finance=True)
        stale_undo = executor.submit(undo, api_client, auth_headers, pid, again)
        assert completing.result().status_code == 200
        assert stale_undo.result().status_code == 409
    with SessionLocal() as db:
        assert db.scalar(select(func.count(TreatmentPlanCompletionReversal.id)).join(TreatmentPlanCompletion)
            .where(TreatmentPlanCompletion.item_id == item["id"])) == 2
        assert db.scalar(select(func.sum(PatientLedgerEntry.amount_pence)).where(PatientLedgerEntry.patient_id == pid)) == 8200


@pytest.mark.parametrize("patch", [{"reason": ""}, {"reason": "  "}, {"reason": "x" * 501},
    {"confirm_finance": False}, {"confirm_finance": "true"}, {"expected_revision": True}, {"status": "proposed"}])
def test_invalid_request_never_partially_corrects(api_client, auth_headers, patch):
    pid, item, _ = completed_case(api_client, auth_headers)
    before = counts(pid)
    assert undo(api_client, auth_headers, pid, item, **patch).status_code == 422
    assert counts(pid) == before
    with SessionLocal() as db:
        assert db.get(Procedure, item["completed_procedure_id"]).status == ProcedureStatus.completed


@pytest.mark.parametrize("fault", ["invoice", "duplicate", "amount", "wrong_patient", "preexisting_reversal", "procedure"])
def test_ambiguous_financial_or_procedure_dependencies_reject_atomically(api_client, auth_headers, fault):
    pid, item, _ = completed_case(api_client, auth_headers)
    other_pid = setup_case(api_client, auth_headers)[0] if fault == "wrong_patient" else None
    with SessionLocal() as db:
        charge = db.scalar(select(PatientLedgerEntry).where(PatientLedgerEntry.patient_id == pid))
        if fault == "invoice":
            invoice = Invoice(patient_id=pid, invoice_number=f"SYN-{uuid4().hex[:20]}",
                created_by_user_id=charge.created_by_user_id, updated_by_user_id=charge.updated_by_user_id)
            db.add(invoice)
            db.flush()
            charge.related_invoice_id = invoice.id
        elif fault == "amount":
            charge.amount_pence += 1
        elif fault == "wrong_patient":
            charge.patient_id = other_pid
        elif fault == "procedure":
            db.get(Procedure, item["completed_procedure_id"]).description = "Synthetic conflicting source"
        else:
            db.add(PatientLedgerEntry(patient_id=pid, entry_type=LedgerEntryType.adjustment, amount_pence=-8200,
                reference=charge.reference if fault == "duplicate" else f"TREATMENT-PLAN:{item['id']}:C1:REVERSAL",
                created_by_user_id=charge.created_by_user_id, updated_by_user_id=charge.updated_by_user_id))
        db.commit()
    before = counts(pid)
    assert undo(api_client, auth_headers, pid, item).status_code == 422
    assert counts(pid) == before
    with SessionLocal() as db:
        assert db.get(TreatmentPlanItem, item["id"]).revision == item["revision"]
        assert db.get(Procedure, item["completed_procedure_id"]).status == ProcedureStatus.completed


def test_permissions_archive_cross_patient_and_finance_redaction(api_client, auth_headers):
    pid, item, _ = completed_case(api_client, auth_headers)
    user_id, restricted = _create_user_headers(api_client)
    for capabilities in (["clinical.write", "billing.payments.write"], ["clinical.view", "billing.payments.write"], ["clinical.view", "clinical.write"]):
        _set_capabilities(user_id, capabilities)
        assert undo(api_client, restricted, pid, item).status_code == 403
    other_pid = setup_case(api_client, auth_headers)[0]
    assert undo(api_client, auth_headers, other_pid, item).status_code == 404
    with SessionLocal() as db:
        db.get(Patient, pid).deleted_at = datetime.now(timezone.utc)
        db.commit()
    assert undo(api_client, auth_headers, pid, item).status_code == 404
    with SessionLocal() as db:
        db.get(Patient, pid).deleted_at = None
        db.commit()
    assert undo(api_client, auth_headers, pid, item).status_code == 200
    _set_capabilities(user_id, ["patients.view", "clinical.view"])
    response = api_client.get(f"/patients/{pid}/clinical-journal", headers=restricted)
    assert response.status_code == 200
    entry = next(row for row in response.json()["items"] if row["source_kind"] == "procedure")
    assert "fee_pence" not in entry["details"]
    assert "original_charge_id" not in entry["details"]["completion_correction"]
    assert "adjustment_id" not in entry["details"]["completion_correction"]


def test_legacy_missing_adjacent_history_is_not_guessed(api_client, auth_headers):
    pid, item, _ = completed_case(api_client, auth_headers, legacy=True)
    # An unrecorded revision gap is ambiguous; never fabricate a former status.
    with SessionLocal() as db:
        db.get(TreatmentPlanItem, item["id"]).revision += 1
        db.commit()
    item["revision"] += 1
    assert undo(api_client, auth_headers, pid, item).status_code == 422
    with SessionLocal() as db:
        assert db.scalar(select(func.count(TreatmentPlanCompletion.id)).where(TreatmentPlanCompletion.item_id == item["id"])) == 0
        assert db.get(Procedure, item["completed_procedure_id"]).status == ProcedureStatus.completed


def test_populated_correction_migration_refuses_downgrade(api_client, auth_headers):
    pid, item, _ = completed_case(api_client, auth_headers)
    assert undo(api_client, auth_headers, pid, item).status_code == 200
    result = subprocess.run(["alembic", "downgrade", "0059_frozen_treatment_planning"], capture_output=True, text=True)
    assert result.returncode != 0 and "Cannot downgrade: treatment completion cycles" in result.stderr
    with SessionLocal() as db:
        assert db.execute(text("SELECT version_num FROM alembic_version")).scalar() == "0060_treatment_completion_reversals"
        assert db.get(Procedure, item["completed_procedure_id"]).status == ProcedureStatus.voided
