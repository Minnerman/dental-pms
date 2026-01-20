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
