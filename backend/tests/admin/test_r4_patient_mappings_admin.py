from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.legacy_resolution_event import LegacyResolutionEvent
from app.models.patient import Patient
from app.models.r4_patient_mapping import R4PatientMapping
from app.models.r4_treatment_plan import R4TreatmentPlan
from app.models.user import Role, User
from app.services.users import create_user


def seed_r4_plan(session, actor_id: int, patient_code: int, tp_number: int) -> R4TreatmentPlan:
    plan = R4TreatmentPlan(
        legacy_source="r4",
        legacy_patient_code=patient_code,
        legacy_tp_number=tp_number,
        plan_index=1,
        is_master=False,
        is_current=True,
        is_accepted=False,
        creation_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
        created_by_user_id=actor_id,
        updated_by_user_id=actor_id,
    )
    session.add(plan)
    session.flush()
    return plan


def test_r4_patient_mapping_requires_admin(api_client):
    session = SessionLocal()
    try:
        email = f"external-{uuid4().hex[:8]}@example.com"
        password = "ChangeMe123!000"
        create_user(session, email=email, password=password, role=Role.external)
    finally:
        session.close()

    res = api_client.post("/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    token = res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    res = api_client.get("/admin/r4/patient-mappings/unmapped-plans", headers=headers)
    assert res.status_code == 403, res.text


def test_r4_unmapped_patient_codes(api_client, auth_headers):
    session = SessionLocal()
    try:
        actor = session.scalar(select(User).order_by(User.id.asc()).limit(1))
        assert actor is not None
        seed = int(uuid4().hex[:6], 16)
        code_a = 7000000 + seed
        code_b = code_a + 1
        seed_r4_plan(session, actor.id, code_a, tp_number=1)
        seed_r4_plan(session, actor.id, code_a, tp_number=2)
        seed_r4_plan(session, actor.id, code_b, tp_number=1)
        session.commit()
    finally:
        session.close()

    res = api_client.get(
        "/admin/r4/patient-mappings/unmapped-plans",
        headers=auth_headers,
        params={"limit": 10, "legacy_patient_code": code_a},
    )
    assert res.status_code == 200, res.text
    payload = res.json()
    assert payload
    assert payload[0]["legacy_patient_code"] == code_a
    assert payload[0]["plan_count"] >= 2


def test_r4_patient_mapping_create(api_client, auth_headers):
    session = SessionLocal()
    try:
        actor = session.scalar(select(User).order_by(User.id.asc()).limit(1))
        assert actor is not None
        seed = int(uuid4().hex[:6], 16)
        code = 7100000 + seed
        patient = Patient(
            legacy_source=None,
            legacy_id=None,
            first_name="Test",
            last_name="Mapping",
            created_by_user_id=actor.id,
            updated_by_user_id=actor.id,
        )
        session.add(patient)
        seed_r4_plan(session, actor.id, code, tp_number=1)
        session.commit()
        patient_id = patient.id
    finally:
        session.close()


def test_r4_patient_mapping_backfill_requires_auth(api_client):
    res = api_client.post("/admin/r4/patient-mappings/backfill-patient-ids", json={})
    assert res.status_code == 401, res.text


def test_r4_patient_mapping_backfill_chunked(api_client, auth_headers):
    session = SessionLocal()
    try:
        actor = session.scalar(select(User).order_by(User.id.asc()).limit(1))
        assert actor is not None
        seed = int(uuid4().hex[:6], 16)
        mapped_code = 7200000 + seed
        unmapped_code = mapped_code + 1
        patient = Patient(
            legacy_source=None,
            legacy_id=None,
            first_name="Backfill",
            last_name="Target",
            created_by_user_id=actor.id,
            updated_by_user_id=actor.id,
        )
        session.add(patient)
        session.flush()
        patient_id = patient.id
        mapping = R4PatientMapping(
            legacy_source="r4",
            legacy_patient_code=mapped_code,
            patient_id=patient.id,
            created_by_user_id=actor.id,
            updated_by_user_id=actor.id,
        )
        session.add(mapping)
        plan_one = seed_r4_plan(session, actor.id, mapped_code, tp_number=1)
        plan_two = seed_r4_plan(session, actor.id, mapped_code, tp_number=2)
        plan_three = seed_r4_plan(session, actor.id, unmapped_code, tp_number=1)
        plan_one_id = plan_one.id
        plan_two_id = plan_two.id
        plan_three_id = plan_three.id
        session.commit()
    finally:
        session.close()

    res = api_client.post(
        "/admin/r4/patient-mappings/backfill-patient-ids",
        headers=auth_headers,
        json={"limit": 1, "dry_run": True},
    )
    assert res.status_code == 200, res.text
    payload = res.json()
    assert payload["dry_run"] is True
    assert payload["processed"] == 1
    assert payload["updated"] == 0
    assert payload["remaining_estimate"] >= 1

    res = api_client.post(
        "/admin/r4/patient-mappings/backfill-patient-ids",
        headers=auth_headers,
        json={"limit": 10, "dry_run": False},
    )
    assert res.status_code == 200, res.text
    payload = res.json()
    assert payload["dry_run"] is False
    assert payload["processed"] == 2
    assert payload["updated"] == 2

    session = SessionLocal()
    try:
        refreshed_one = session.get(R4TreatmentPlan, plan_one_id)
        refreshed_two = session.get(R4TreatmentPlan, plan_two_id)
        refreshed_three = session.get(R4TreatmentPlan, plan_three_id)
        assert refreshed_one is not None
        assert refreshed_two is not None
        assert refreshed_three is not None
        assert refreshed_one.patient_id == patient_id
        assert refreshed_two.patient_id == patient_id
        assert refreshed_three.patient_id is None
    finally:
        session.close()

    res = api_client.post(
        "/admin/r4/patient-mappings/backfill-patient-ids",
        headers=auth_headers,
        json={"limit": 10, "dry_run": False},
    )
    assert res.status_code == 200, res.text
    payload = res.json()
    assert payload["processed"] == 0
    assert payload["updated"] == 0

    res = api_client.post(
        "/admin/r4/patient-mappings",
        headers=auth_headers,
        json={"legacy_patient_code": code, "patient_id": patient_id, "notes": "linked"},
    )
    assert res.status_code == 200, res.text
    payload = res.json()
    assert payload["legacy_patient_code"] == code
    assert payload["patient_id"] == patient_id

    session = SessionLocal()
    try:
        mapping = session.scalar(
            select(R4PatientMapping).where(
                R4PatientMapping.legacy_patient_code == code,
                R4PatientMapping.patient_id == patient_id,
            )
        )
        assert mapping is not None
        event = session.scalar(
            select(LegacyResolutionEvent).where(
                LegacyResolutionEvent.entity_type == "r4_patient_mapping",
                LegacyResolutionEvent.legacy_id == str(code),
            )
        )
        assert event is not None
    finally:
        session.close()
