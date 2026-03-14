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


def test_update_appointment_note_via_appointment_route(api_client, auth_headers):
    patient_id = _create_patient(
        api_client,
        auth_headers,
        first_name="Appt",
        last_name="UpdateNote",
    )
    appointment_id = _create_appointment(
        api_client,
        auth_headers,
        patient_id=patient_id,
        starts_at=datetime(2026, 1, 22, 9, 0, tzinfo=timezone.utc),
        ends_at=datetime(2026, 1, 22, 9, 30, tzinfo=timezone.utc),
        location="Update Route Room",
    )

    create_response = api_client.post(
        f"/appointments/{appointment_id}/notes",
        json={"body": "Needs update", "note_type": "clinical"},
        headers=auth_headers,
    )
    assert create_response.status_code == 201, create_response.text
    note_id = int(create_response.json()["id"])

    update_response = api_client.patch(
        f"/appointments/{appointment_id}/notes/{note_id}",
        json={"body": "Updated via appointment route", "note_type": "admin"},
        headers=auth_headers,
    )
    assert update_response.status_code == 200, update_response.text
    payload = update_response.json()

    assert payload["id"] == note_id
    assert payload["appointment_id"] == appointment_id
    assert payload["body"] == "Updated via appointment route"
    assert payload["note_type"] == "admin"


def test_update_appointment_note_rejects_note_from_other_appointment(api_client, auth_headers):
    patient_id = _create_patient(
        api_client,
        auth_headers,
        first_name="Appt",
        last_name="WrongUpdate",
    )
    appointment_a = _create_appointment(
        api_client,
        auth_headers,
        patient_id=patient_id,
        starts_at=datetime(2026, 1, 23, 9, 0, tzinfo=timezone.utc),
        ends_at=datetime(2026, 1, 23, 9, 30, tzinfo=timezone.utc),
        location="Wrong Update A",
    )
    appointment_b = _create_appointment(
        api_client,
        auth_headers,
        patient_id=patient_id,
        starts_at=datetime(2026, 1, 23, 10, 0, tzinfo=timezone.utc),
        ends_at=datetime(2026, 1, 23, 10, 30, tzinfo=timezone.utc),
        location="Wrong Update B",
    )

    create_response = api_client.post(
        f"/appointments/{appointment_a}/notes",
        json={"body": "Appointment A note", "note_type": "clinical"},
        headers=auth_headers,
    )
    assert create_response.status_code == 201, create_response.text
    note_id = int(create_response.json()["id"])

    update_response = api_client.patch(
        f"/appointments/{appointment_b}/notes/{note_id}",
        json={"body": "Should not update", "note_type": "admin"},
        headers=auth_headers,
    )
    assert update_response.status_code == 404, update_response.text
    assert update_response.json()["detail"] == "Note not found"


def test_archive_and_restore_appointment_note_via_appointment_routes(api_client, auth_headers):
    patient_id = _create_patient(
        api_client,
        auth_headers,
        first_name="Appt",
        last_name="ArchiveRestore",
    )
    appointment_id = _create_appointment(
        api_client,
        auth_headers,
        patient_id=patient_id,
        starts_at=datetime(2026, 1, 24, 9, 0, tzinfo=timezone.utc),
        ends_at=datetime(2026, 1, 24, 9, 30, tzinfo=timezone.utc),
        location="Archive Restore Room",
    )

    create_response = api_client.post(
        f"/appointments/{appointment_id}/notes",
        json={"body": "Appointment note to archive", "note_type": "clinical"},
        headers=auth_headers,
    )
    assert create_response.status_code == 201, create_response.text
    note_id = int(create_response.json()["id"])

    archive_response = api_client.post(
        f"/appointments/{appointment_id}/notes/{note_id}/archive",
        headers=auth_headers,
    )
    assert archive_response.status_code == 200, archive_response.text
    assert archive_response.json()["deleted_at"] is not None

    default_list = api_client.get(
        f"/appointments/{appointment_id}/notes",
        headers=auth_headers,
    )
    assert default_list.status_code == 200, default_list.text
    assert default_list.json() == []

    archived_list = api_client.get(
        f"/appointments/{appointment_id}/notes",
        params={"include_deleted": "true"},
        headers=auth_headers,
    )
    assert archived_list.status_code == 200, archived_list.text
    assert [item["id"] for item in archived_list.json()] == [note_id]

    restore_response = api_client.post(
        f"/appointments/{appointment_id}/notes/{note_id}/restore",
        headers=auth_headers,
    )
    assert restore_response.status_code == 200, restore_response.text
    assert restore_response.json()["deleted_at"] is None

    restored_list = api_client.get(
        f"/appointments/{appointment_id}/notes",
        headers=auth_headers,
    )
    assert restored_list.status_code == 200, restored_list.text
    assert [item["id"] for item in restored_list.json()] == [note_id]
