from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4


def _create_patient(api_client, auth_headers, label: str) -> int:
    response = api_client.post(
        "/patients",
        json={"first_name": "Appointment", "last_name": label},
        headers=auth_headers,
    )
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


def _set_capabilities(api_client, auth_headers, user_id: int, codes: list[str]) -> None:
    response = api_client.put(
        f"/users/{user_id}/capabilities",
        json={"capability_codes": codes},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text


def _create_user(api_client, auth_headers) -> tuple[int, str, dict[str, str]]:
    suffix = uuid4().hex[:10]
    email = f"appointment-reliability-{suffix}@example.com"
    password = "ChangeMe12345!"
    response = api_client.post(
        "/users",
        json={
            "email": email,
            "full_name": "Appointment Reliability User",
            "role": "reception",
            "temp_password": password,
        },
        headers=auth_headers,
    )
    assert response.status_code == 201, response.text
    user_id = int(response.json()["id"])
    login = api_client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    return user_id, email, {"Authorization": f"Bearer {token}"}


def _create_appointment(
    api_client,
    headers,
    patient_id: int,
    *,
    starts_at: datetime,
    ends_at: datetime,
    clinician_user_id: int | None = None,
    location: str = "Room 1",
    allow_outside_hours: bool = True,
    appointment_type: str | None = "Exam",
) -> dict:
    response = api_client.post(
        "/appointments",
        json={
            "patient_id": patient_id,
            "clinician_user_id": clinician_user_id,
            "starts_at": starts_at.isoformat(),
            "ends_at": ends_at.isoformat(),
            "status": "booked",
            "appointment_type": appointment_type,
            "location_type": "clinic",
            "location": location,
            "allow_outside_hours": allow_outside_hours,
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _audit(api_client, headers, appointment_id: int) -> list[dict]:
    response = api_client.get(
        f"/appointments/{appointment_id}/audit",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_appointment_capabilities_are_enforced_per_action(api_client, auth_headers):
    patient_id = _create_patient(api_client, auth_headers, "Permissions")
    user_id, email, user_headers = _create_user(api_client, auth_headers)
    _set_capabilities(api_client, auth_headers, user_id, [])

    denied_read = api_client.get(
        "/appointments/range",
        params={"start": "2030-01-15", "end": "2030-01-16"},
        headers=user_headers,
    )
    assert denied_read.status_code == 403

    create_payload = {
        "patient_id": patient_id,
        "starts_at": "2030-01-15T10:00:00+00:00",
        "ends_at": "2030-01-15T10:30:00+00:00",
        "status": "booked",
        "location_type": "clinic",
        "location": "Permissions Room",
    }
    denied_create = api_client.post(
        "/appointments",
        json=create_payload,
        headers=user_headers,
    )
    assert denied_create.status_code == 403

    _set_capabilities(api_client, auth_headers, user_id, ["appointments.view"])
    allowed_read = api_client.get(
        "/appointments/range",
        params={"start": "2030-01-15", "end": "2030-01-16"},
        headers=user_headers,
    )
    assert allowed_read.status_code == 200, allowed_read.text

    _set_capabilities(
        api_client,
        auth_headers,
        user_id,
        ["appointments.view", "appointments.write"],
    )
    created_response = api_client.post(
        "/appointments",
        json=create_payload,
        headers=user_headers,
    )
    assert created_response.status_code == 201, created_response.text
    appointment_id = int(created_response.json()["id"])

    _set_capabilities(api_client, auth_headers, user_id, ["appointments.view"])
    denied_edit = api_client.patch(
        f"/appointments/{appointment_id}",
        json={"appointment_type": "Blocked edit"},
        headers=user_headers,
    )
    assert denied_edit.status_code == 403

    _set_capabilities(
        api_client,
        auth_headers,
        user_id,
        ["appointments.view", "appointments.reschedule"],
    )
    moved = api_client.patch(
        f"/appointments/{appointment_id}",
        json={
            "starts_at": "2030-01-15T10:30:00+00:00",
            "ends_at": "2030-01-15T11:00:00+00:00",
        },
        headers=user_headers,
    )
    assert moved.status_code == 200, moved.text

    denied_general_edit = api_client.patch(
        f"/appointments/{appointment_id}",
        json={"appointment_type": "Still blocked"},
        headers=user_headers,
    )
    assert denied_general_edit.status_code == 403

    _set_capabilities(
        api_client,
        auth_headers,
        user_id,
        ["appointments.view", "appointments.cancel"],
    )
    cancelled = api_client.patch(
        f"/appointments/{appointment_id}",
        json={"status": "cancelled", "cancel_reason": "Patient unavailable"},
        headers=user_headers,
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["cancel_reason"] == "Patient unavailable"

    denied_archive = api_client.post(
        f"/appointments/{appointment_id}/archive",
        headers=user_headers,
    )
    assert denied_archive.status_code == 403

    audit_entries = _audit(api_client, user_headers, appointment_id)
    cancelled_entry = next(
        item for item in audit_entries if item["action"] == "appointment.cancelled"
    )
    assert cancelled_entry["actor_email"] == email

    _set_capabilities(
        api_client,
        auth_headers,
        user_id,
        ["appointments.view", "appointments.write"],
    )
    archived = api_client.post(
        f"/appointments/{appointment_id}/archive",
        headers=user_headers,
    )
    assert archived.status_code == 200, archived.text
    restored = api_client.post(
        f"/appointments/{appointment_id}/restore",
        headers=user_headers,
    )
    assert restored.status_code == 200, restored.text


def test_appointment_validation_lifecycle_and_audit_are_atomic(api_client, auth_headers):
    patient_id = _create_patient(api_client, auth_headers, "Validation")
    current_user = api_client.get("/me", headers=auth_headers)
    assert current_user.status_code == 200, current_user.text
    actor = current_user.json()

    invalid_create = api_client.post(
        "/appointments",
        json={
            "patient_id": patient_id,
            "starts_at": "2030-01-15T11:00:00+00:00",
            "ends_at": "2030-01-15T10:30:00+00:00",
            "status": "booked",
            "location_type": "clinic",
            "allow_outside_hours": True,
        },
        headers=auth_headers,
    )
    assert invalid_create.status_code == 400
    assert "after start" in invalid_create.json()["detail"]

    starts_at = datetime(2030, 1, 15, 10, 0, tzinfo=timezone.utc)
    ends_at = datetime(2030, 1, 15, 10, 30, tzinfo=timezone.utc)
    created = _create_appointment(
        api_client,
        auth_headers,
        patient_id,
        starts_at=starts_at,
        ends_at=ends_at,
        clinician_user_id=int(actor["id"]),
        location="Validation Room",
    )
    appointment_id = int(created["id"])
    audit_count = len(_audit(api_client, auth_headers, appointment_id))

    invalid_update = api_client.patch(
        f"/appointments/{appointment_id}",
        json={
            "starts_at": "2030-01-15T12:00:00+00:00",
            "ends_at": "2030-01-15T11:00:00+00:00",
            "allow_outside_hours": True,
        },
        headers=auth_headers,
    )
    assert invalid_update.status_code == 400
    assert len(_audit(api_client, auth_headers, appointment_id)) == audit_count

    missing_reason = api_client.patch(
        f"/appointments/{appointment_id}",
        json={"status": "cancelled"},
        headers=auth_headers,
    )
    assert missing_reason.status_code == 400
    assert missing_reason.json()["detail"] == "Cancellation reason is required."
    assert len(_audit(api_client, auth_headers, appointment_id)) == audit_count

    cleared = api_client.patch(
        f"/appointments/{appointment_id}",
        json={
            "appointment_type": None,
            "clinician_user_id": None,
            "location": None,
        },
        headers=auth_headers,
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["appointment_type"] is None
    assert cleared.json()["clinician_user_id"] is None
    assert cleared.json()["location"] is None

    cancelled = api_client.patch(
        f"/appointments/{appointment_id}",
        json={"status": "cancelled", "cancel_reason": "Patient requested"},
        headers=auth_headers,
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["cancelled_by_user_id"] == actor["id"]

    reopened = api_client.patch(
        f"/appointments/{appointment_id}",
        json={"status": "booked", "cancel_reason": None},
        headers=auth_headers,
    )
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["cancel_reason"] is None
    assert reopened.json()["cancelled_at"] is None
    assert reopened.json()["cancelled_by_user_id"] is None

    archived = api_client.post(
        f"/appointments/{appointment_id}/archive",
        headers=auth_headers,
    )
    assert archived.status_code == 200, archived.text
    restored = api_client.post(
        f"/appointments/{appointment_id}/restore",
        headers=auth_headers,
    )
    assert restored.status_code == 200, restored.text

    entries = _audit(api_client, auth_headers, appointment_id)
    actions = [entry["action"] for entry in entries]
    assert "appointment.created" in actions
    assert "appointment.rescheduled" in actions
    assert "appointment.cancelled" in actions
    assert "appointment.archived" in actions
    assert "appointment.restored" in actions
    cancellation_entry = next(
        entry for entry in entries if entry["action"] == "appointment.cancelled"
    )
    assert cancellation_entry["actor_email"] == actor["email"]
    assert cancellation_entry["before_json"]["status"] == "booked"
    assert cancellation_entry["after_json"]["status"] == "cancelled"
    assert cancellation_entry["after_json"]["cancel_reason"] == "Patient requested"

    archived_patient = api_client.post(
        f"/patients/{patient_id}/archive",
        headers=auth_headers,
    )
    assert archived_patient.status_code == 200, archived_patient.text
    rejected_archived_patient = api_client.post(
        "/appointments",
        json={
            "patient_id": patient_id,
            "starts_at": "2030-01-16T10:00:00+00:00",
            "ends_at": "2030-01-16T10:30:00+00:00",
            "status": "booked",
            "location_type": "clinic",
            "allow_outside_hours": True,
        },
        headers=auth_headers,
    )
    assert rejected_archived_patient.status_code == 404


def test_reschedule_conflicts_do_not_mutate_or_audit(api_client, auth_headers):
    patient_a = _create_patient(api_client, auth_headers, "Conflict A")
    patient_b = _create_patient(api_client, auth_headers, "Conflict B")
    user_id, _, _ = _create_user(api_client, auth_headers)
    current_user = api_client.get("/me", headers=auth_headers).json()
    room_suffix = uuid4().hex[:10]
    conflict_room = f"Conflict Room {room_suffix}"
    other_room = f"Other Room {room_suffix}"

    first = _create_appointment(
        api_client,
        auth_headers,
        patient_a,
        starts_at=datetime(2030, 1, 15, 9, 0, tzinfo=timezone.utc),
        ends_at=datetime(2030, 1, 15, 9, 30, tzinfo=timezone.utc),
        clinician_user_id=int(current_user["id"]),
        location=conflict_room,
    )
    second = _create_appointment(
        api_client,
        auth_headers,
        patient_b,
        starts_at=datetime(2030, 1, 15, 10, 0, tzinfo=timezone.utc),
        ends_at=datetime(2030, 1, 15, 10, 30, tzinfo=timezone.utc),
        clinician_user_id=user_id,
        location=other_room,
    )
    second_id = int(second["id"])
    audit_count = len(_audit(api_client, auth_headers, second_id))

    location_conflict = api_client.patch(
        f"/appointments/{second_id}",
        json={
            "starts_at": "2030-01-15T09:15:00+00:00",
            "ends_at": "2030-01-15T09:45:00+00:00",
            "location": conflict_room,
            "allow_outside_hours": True,
        },
        headers=auth_headers,
    )
    assert location_conflict.status_code == 409, location_conflict.text

    clinician_conflict = api_client.patch(
        f"/appointments/{second_id}",
        json={
            "starts_at": "2030-01-15T09:15:00+00:00",
            "ends_at": "2030-01-15T09:45:00+00:00",
            "clinician_user_id": current_user["id"],
            "allow_outside_hours": True,
        },
        headers=auth_headers,
    )
    assert clinician_conflict.status_code == 409, clinician_conflict.text

    unchanged = api_client.get(f"/appointments/{second_id}", headers=auth_headers)
    assert unchanged.status_code == 200, unchanged.text
    assert unchanged.json()["starts_at"] == second["starts_at"]
    assert unchanged.json()["location"] == other_room
    assert len(_audit(api_client, auth_headers, second_id)) == audit_count

    moved = api_client.patch(
        f"/appointments/{second_id}",
        json={
            "starts_at": "2030-01-15T11:00:00+00:00",
            "ends_at": "2030-01-15T11:30:00+00:00",
            "location": conflict_room,
            "allow_outside_hours": True,
        },
        headers=auth_headers,
    )
    assert moved.status_code == 200, moved.text
    entries = _audit(api_client, auth_headers, second_id)
    assert entries[0]["action"] == "appointment.rescheduled"

    overlapping_create = _create_appointment(
        api_client,
        auth_headers,
        patient_a,
        starts_at=datetime(2030, 1, 15, 11, 15, tzinfo=timezone.utc),
        ends_at=datetime(2030, 1, 15, 11, 45, tzinfo=timezone.utc),
        clinician_user_id=user_id,
        location=conflict_room,
    )
    assert overlapping_create["id"] != first["id"]
