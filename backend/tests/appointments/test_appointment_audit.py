from datetime import datetime, timezone


def test_appointment_audit_log_entries(api_client, auth_headers):
    patient_payload = {"first_name": "Audit", "last_name": "Trail"}
    patient_res = api_client.post("/patients", json=patient_payload, headers=auth_headers)
    assert patient_res.status_code == 201, patient_res.text
    patient_id = patient_res.json()["id"]

    start = datetime(2026, 1, 15, 9, 0, tzinfo=timezone.utc)
    end = datetime(2026, 1, 15, 9, 30, tzinfo=timezone.utc)
    create_payload = {
        "patient_id": patient_id,
        "starts_at": start.isoformat(),
        "ends_at": end.isoformat(),
        "status": "booked",
        "location_type": "clinic",
        "allow_outside_hours": True,
    }
    create_res = api_client.post("/appointments", json=create_payload, headers=auth_headers)
    assert create_res.status_code == 201, create_res.text
    appointment_id = create_res.json()["id"]

    update_res = api_client.patch(
        f"/appointments/{appointment_id}",
        json={"appointment_type": "Exam", "allow_outside_hours": True},
        headers=auth_headers,
    )
    assert update_res.status_code == 200, update_res.text

    audit_res = api_client.get(
        f"/audit/appointments/{appointment_id}",
        params={"limit": 10},
        headers=auth_headers,
    )
    assert audit_res.status_code == 200, audit_res.text
    actions = [entry["action"] for entry in audit_res.json()]
    assert "appointment.created" in actions
    assert "appointment.updated" in actions
