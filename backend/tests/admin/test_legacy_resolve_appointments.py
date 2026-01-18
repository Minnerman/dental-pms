from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.appointment import Appointment, AppointmentLocationType, AppointmentStatus
from app.models.legacy_resolution_event import LegacyResolutionEvent
from app.models.patient import Patient
from app.models.user import Role, User
from app.services.users import create_user


def seed_patient(session, actor_id: int) -> Patient:
    patient = Patient(
        first_name="Resolve",
        last_name="Target",
        created_by_user_id=actor_id,
        updated_by_user_id=actor_id,
    )
    session.add(patient)
    session.commit()
    session.refresh(patient)
    return patient


def seed_unmapped_appt(session, actor_id: int) -> Appointment:
    suffix = uuid4().hex[:8]
    start = datetime(2030, 2, 1, 10, 0, tzinfo=timezone.utc)
    appt = Appointment(
        patient_id=None,
        starts_at=start,
        ends_at=start + timedelta(minutes=30),
        status=AppointmentStatus.booked,
        location_type=AppointmentLocationType.clinic,
        is_domiciliary=False,
        legacy_source="r4",
        legacy_id=f"UNMAPPED-{suffix}",
        legacy_patient_code="9999",
        created_by_user_id=actor_id,
        updated_by_user_id=actor_id,
    )
    session.add(appt)
    session.commit()
    session.refresh(appt)
    return appt


def seed_linked_appt(session, actor_id: int, patient_id: int) -> Appointment:
    suffix = uuid4().hex[:8]
    start = datetime(2030, 2, 2, 10, 0, tzinfo=timezone.utc)
    appt = Appointment(
        patient_id=patient_id,
        starts_at=start,
        ends_at=start + timedelta(minutes=30),
        status=AppointmentStatus.booked,
        location_type=AppointmentLocationType.clinic,
        is_domiciliary=False,
        legacy_source="r4",
        legacy_id=f"LINKED-{suffix}",
        legacy_patient_code="1001",
        created_by_user_id=actor_id,
        updated_by_user_id=actor_id,
    )
    session.add(appt)
    session.commit()
    session.refresh(appt)
    return appt


def test_resolve_requires_admin(api_client):
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

    res = api_client.post(
        "/admin/legacy/unmapped-appointments/1/resolve",
        headers=headers,
        json={"patient_id": 1},
    )
    assert res.status_code == 403, res.text


def test_resolve_validates_state(api_client, auth_headers):
    session = SessionLocal()
    try:
        actor = session.scalar(select(User).order_by(User.id.asc()).limit(1))
        assert actor is not None
        patient = seed_patient(session, actor.id)
        patient_id = patient.id
        linked = seed_linked_appt(session, actor.id, patient_id)
        linked_id = linked.id
        unmapped = seed_unmapped_appt(session, actor.id)
        unmapped_id = unmapped.id
    finally:
        session.close()

    res = api_client.post(
        f"/admin/legacy/unmapped-appointments/{linked_id}/resolve",
        headers=auth_headers,
        json={"patient_id": patient_id},
    )
    assert res.status_code == 409, res.text

    res = api_client.post(
        f"/admin/legacy/unmapped-appointments/{unmapped_id}/resolve",
        headers=auth_headers,
        json={"patient_id": 9999999},
    )
    assert res.status_code == 404, res.text


def test_resolve_success_creates_event(api_client, auth_headers):
    session = SessionLocal()
    try:
        actor = session.scalar(select(User).order_by(User.id.asc()).limit(1))
        assert actor is not None
        patient = seed_patient(session, actor.id)
        patient_id = patient.id
        unmapped = seed_unmapped_appt(session, actor.id)
        unmapped_id = unmapped.id
    finally:
        session.close()

    res = api_client.post(
        f"/admin/legacy/unmapped-appointments/{unmapped_id}/resolve",
        headers=auth_headers,
        json={"patient_id": patient_id, "notes": "Matched by legacy code"},
    )
    assert res.status_code == 200, res.text
    payload = res.json()
    assert payload["patient_id"] == patient_id

    session = SessionLocal()
    try:
        updated = session.get(Appointment, unmapped_id)
        assert updated is not None
        assert updated.patient_id == patient_id
        event = session.scalar(
            select(LegacyResolutionEvent).where(
                LegacyResolutionEvent.entity_type == "appointment",
                LegacyResolutionEvent.entity_id == str(unmapped_id),
                LegacyResolutionEvent.action == "link_patient",
            )
        )
        assert event is not None
        assert event.to_patient_id == patient_id
        assert event.notes == "Matched by legacy code"
    finally:
        session.close()
