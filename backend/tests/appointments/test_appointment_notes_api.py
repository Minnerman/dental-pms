from datetime import datetime, timezone


def _create_patient(api_client, auth_headers, *, first_name: str, last_name: str) -> int:
    response = api_client.post(
        "/patients",
        json={"first_name": first_name, "last_name": last_name},
        headers=auth_headers,
    )
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


def _create_appointment(
    api_client,
    auth_headers,
    *,
    patient_id: int,
    starts_at: datetime,
    ends_at: datetime,
    location: str,
) -> int:
    response = api_client.post(
        "/appointments",
        json={
            "patient_id": patient_id,
            "starts_at": starts_at.isoformat(),
            "ends_at": ends_at.isoformat(),
            "status": "booked",
            "location_type": "clinic",
            "location": location,
            "allow_outside_hours": True,
        },
        headers=auth_headers,
    )
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


def test_create_appointment_note_via_appointment_route(api_client, auth_headers):
    patient_id = _create_patient(
        api_client,
        auth_headers,
        first_name="Appt",
        last_name="ScopedNote",
    )
    appointment_id = _create_appointment(
        api_client,
        auth_headers,
        patient_id=patient_id,
        starts_at=datetime(2026, 1, 20, 9, 0, tzinfo=timezone.utc),
        ends_at=datetime(2026, 1, 20, 9, 30, tzinfo=timezone.utc),
        location="Note Route Room",
    )

    create_response = api_client.post(
        f"/appointments/{appointment_id}/notes",
        json={"body": "Appointment-scoped create", "note_type": "clinical"},
        headers=auth_headers,
    )
    assert create_response.status_code == 201, create_response.text
    payload = create_response.json()

    assert payload["patient_id"] == patient_id
    assert payload["appointment_id"] == appointment_id
    assert payload["body"] == "Appointment-scoped create"
    assert payload["note_type"] == "clinical"

    list_response = api_client.get(
        f"/appointments/{appointment_id}/notes",
        headers=auth_headers,
    )
    assert list_response.status_code == 200, list_response.text
    notes = list_response.json()
    assert [item["id"] for item in notes] == [payload["id"]]


def test_create_appointment_note_rejects_missing_appointment(api_client, auth_headers):
    response = api_client.post(
        "/appointments/999999/notes",
        json={"body": "Missing appointment", "note_type": "clinical"},
        headers=auth_headers,
    )

    assert response.status_code == 404, response.text
    assert response.json()["detail"] == "Appointment not found"


def test_global_note_create_rejects_mismatched_appointment_patient(api_client, auth_headers):
    patient_a = _create_patient(
        api_client,
        auth_headers,
        first_name="Mismatch",
        last_name="Owner",
    )
    patient_b = _create_patient(
        api_client,
        auth_headers,
        first_name="Mismatch",
        last_name="Other",
    )
    appointment_id = _create_appointment(
        api_client,
        auth_headers,
        patient_id=patient_a,
        starts_at=datetime(2026, 1, 21, 11, 0, tzinfo=timezone.utc),
        ends_at=datetime(2026, 1, 21, 11, 30, tzinfo=timezone.utc),
        location="Mismatch Room",
    )

    response = api_client.post(
        "/notes",
        json={
            "patient_id": patient_b,
            "appointment_id": appointment_id,
            "body": "This should not link across patients",
            "note_type": "clinical",
        },
        headers=auth_headers,
    )

    assert response.status_code == 400, response.text
    assert response.json()["detail"] == "appointment_id does not belong to patient_id"
