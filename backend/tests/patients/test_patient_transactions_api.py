from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import delete, select

from app.db.session import SessionLocal
from app.models.patient import Patient
from app.models.r4_treatment_transaction import R4TreatmentTransaction
from app.models.r4_user import R4User
from app.models.user import User


def _seed_patient_with_transactions():
    session = SessionLocal()
    seed = int(uuid4().hex[:6], 16)
    patient_code = 8000000 + seed
    tx_base = 500000 + seed * 10
    recorded_code = 9000000 + seed
    entry_code = recorded_code + 1
    try:
        actor = session.scalar(select(User).order_by(User.id.asc()).limit(1))
        assert actor is not None
        patient = Patient(
            legacy_source="r4",
            legacy_id=str(patient_code),
            first_name="Tx",
            last_name="Patient",
            created_by_user_id=actor.id,
            updated_by_user_id=actor.id,
        )
        session.add(patient)
        session.flush()

        users = [
            R4User(
                legacy_source="r4",
                legacy_user_code=recorded_code,
                full_name="Dr Ada Lovelace",
                title="Dr",
                forename="Ada",
                surname="Lovelace",
                initials="AL",
                display_name="Dr Ada Lovelace",
                is_current=True,
                created_by_user_id=actor.id,
                updated_by_user_id=actor.id,
            ),
            R4User(
                legacy_source="r4",
                legacy_user_code=entry_code,
                full_name="Sam Clerk",
                title="Mr",
                forename="Sam",
                surname="Clerk",
                initials="SC",
                display_name="Mr Sam Clerk",
                is_current=True,
                created_by_user_id=actor.id,
                updated_by_user_id=actor.id,
            ),
        ]
        session.add_all(users)

        txs = [
            R4TreatmentTransaction(
                legacy_source="r4",
                legacy_transaction_id=tx_base + 1,
                patient_code=patient_code,
                performed_at=datetime(2024, 1, 2, 10, 0, tzinfo=timezone.utc),
                treatment_code=None,
                trans_code=1,
                patient_cost=0,
                dpb_cost=0,
                recorded_by=recorded_code,
                user_code=entry_code,
                created_by_user_id=actor.id,
                updated_by_user_id=actor.id,
            ),
            R4TreatmentTransaction(
                legacy_source="r4",
                legacy_transaction_id=tx_base + 2,
                patient_code=patient_code,
                performed_at=datetime(2024, 1, 2, 10, 0, tzinfo=timezone.utc),
                treatment_code=None,
                trans_code=2,
                patient_cost=0,
                dpb_cost=0,
                recorded_by=recorded_code,
                user_code=entry_code,
                created_by_user_id=actor.id,
                updated_by_user_id=actor.id,
            ),
            R4TreatmentTransaction(
                legacy_source="r4",
                legacy_transaction_id=tx_base + 3,
                patient_code=patient_code,
                performed_at=datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc),
                treatment_code=None,
                trans_code=3,
                patient_cost=0,
                dpb_cost=5,
                created_by_user_id=actor.id,
                updated_by_user_id=actor.id,
            ),
            R4TreatmentTransaction(
                legacy_source="r4",
                legacy_transaction_id=tx_base + 4,
                patient_code=patient_code,
                performed_at=datetime(2023, 12, 31, 9, 0, tzinfo=timezone.utc),
                treatment_code=None,
                trans_code=4,
                patient_cost=10,
                dpb_cost=0,
                created_by_user_id=actor.id,
                updated_by_user_id=actor.id,
            ),
        ]
        session.add_all(txs)
        session.commit()
        return {
            "patient_id": patient.id,
            "patient_code": patient_code,
            "tx_ids": [tx.legacy_transaction_id for tx in txs],
            "user_codes": [recorded_code, entry_code],
        }
    finally:
        session.close()


def _cleanup_patient_transactions(
    patient_id: int, tx_ids: list[int], user_codes: list[int]
) -> None:
    session = SessionLocal()
    try:
        session.execute(
            delete(R4TreatmentTransaction).where(
                R4TreatmentTransaction.legacy_transaction_id.in_(tx_ids)
            )
        )
        session.execute(
            delete(R4User).where(R4User.legacy_user_code.in_(user_codes))
        )
        session.execute(delete(Patient).where(Patient.id == patient_id))
        session.commit()
    finally:
        session.close()


def test_patient_transactions_order_and_pagination(api_client, auth_headers):
    seed = _seed_patient_with_transactions()
    patient_id = seed["patient_id"]
    tx_ids = seed["tx_ids"]
    user_codes = seed["user_codes"]
    try:
        res = api_client.get(
            f"/patients/{patient_id}/treatment-transactions",
            headers=auth_headers,
            params={"limit": 2},
        )
        assert res.status_code == 200, res.text
        payload = res.json()
        assert len(payload["items"]) == 2
        assert payload["items"][0]["legacy_transaction_id"] == tx_ids[1]
        assert payload["items"][1]["legacy_transaction_id"] == tx_ids[0]
        assert payload["items"][0]["recorded_by_name"] == "Dr Ada Lovelace"
        assert payload["items"][0]["user_name"] == "Mr Sam Clerk"
        assert payload["next_cursor"]

        res_next = api_client.get(
            f"/patients/{patient_id}/treatment-transactions",
            headers=auth_headers,
            params={"limit": 2, "cursor": payload["next_cursor"]},
        )
        assert res_next.status_code == 200, res_next.text
        payload_next = res_next.json()
        assert [item["legacy_transaction_id"] for item in payload_next["items"]] == [
            tx_ids[2],
            tx_ids[3],
        ]
    finally:
        _cleanup_patient_transactions(patient_id, tx_ids, user_codes)


def test_patient_transactions_filters(api_client, auth_headers):
    seed = _seed_patient_with_transactions()
    patient_id = seed["patient_id"]
    tx_ids = seed["tx_ids"]
    user_codes = seed["user_codes"]
    try:
        res = api_client.get(
            f"/patients/{patient_id}/treatment-transactions",
            headers=auth_headers,
            params={"from": "2024-01-02", "to": "2024-01-02"},
        )
        assert res.status_code == 200, res.text
        payload = res.json()
        assert [item["legacy_transaction_id"] for item in payload["items"]] == [
            tx_ids[1],
            tx_ids[0],
        ]

        res_cost = api_client.get(
            f"/patients/{patient_id}/treatment-transactions",
            headers=auth_headers,
            params={"cost_only": "true"},
        )
        assert res_cost.status_code == 200, res_cost.text
        payload_cost = res_cost.json()
        assert [item["legacy_transaction_id"] for item in payload_cost["items"]] == [
            tx_ids[2],
            tx_ids[3],
        ]
    finally:
        _cleanup_patient_transactions(patient_id, tx_ids, user_codes)
