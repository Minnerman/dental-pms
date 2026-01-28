from uuid import uuid4

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.patient import Patient
from app.models.user import Role, User
from app.services.users import create_user


def _seed_patient(session) -> int:
    actor = session.scalar(select(User).order_by(User.id.asc()).limit(1))
    assert actor is not None
    patient = Patient(
        legacy_source=None,
        legacy_id=None,
        first_name="Manual",
        last_name="Mapping",
        created_by_user_id=actor.id,
        updated_by_user_id=actor.id,
    )
    session.add(patient)
    session.flush()
    return int(patient.id)


def test_manual_mappings_requires_admin(api_client):
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

    res = api_client.get("/admin/r4/manual-mappings", headers=headers)
    assert res.status_code == 403, res.text


def test_manual_mapping_create_and_list(api_client, auth_headers):
    session = SessionLocal()
    try:
        patient_id = _seed_patient(session)
        session.commit()
    finally:
        session.close()

    legacy_code = 9300000 + int(uuid4().hex[:6], 16)
    payload = {
        "legacy_patient_code": legacy_code,
        "target_patient_id": patient_id,
        "note": "manual override",
    }
    res = api_client.post("/admin/r4/manual-mappings", headers=auth_headers, json=payload)
    assert res.status_code == 200, res.text
    created = res.json()
    assert created["legacy_patient_code"] == legacy_code
    assert created["target_patient_id"] == patient_id

    res = api_client.get(
        "/admin/r4/manual-mappings",
        headers=auth_headers,
        params={"legacy_patient_code": legacy_code},
    )
    assert res.status_code == 200, res.text
    items = res.json()
    assert items
    assert items[0]["legacy_patient_code"] == legacy_code
    assert items[0]["target_patient_id"] == patient_id


def test_manual_mapping_duplicate(api_client, auth_headers):
    session = SessionLocal()
    try:
        patient_id = _seed_patient(session)
        session.commit()
    finally:
        session.close()

    legacy_code = 9400000 + int(uuid4().hex[:6], 16)
    payload = {"legacy_patient_code": legacy_code, "target_patient_id": patient_id}
    res = api_client.post("/admin/r4/manual-mappings", headers=auth_headers, json=payload)
    assert res.status_code == 200, res.text

    res = api_client.post("/admin/r4/manual-mappings", headers=auth_headers, json=payload)
    assert res.status_code == 409, res.text


def test_manual_mapping_invalid_patient(api_client, auth_headers):
    legacy_code = 9500000 + int(uuid4().hex[:6], 16)
    payload = {"legacy_patient_code": legacy_code, "target_patient_id": 99999999}
    res = api_client.post("/admin/r4/manual-mappings", headers=auth_headers, json=payload)
    assert res.status_code == 404, res.text
