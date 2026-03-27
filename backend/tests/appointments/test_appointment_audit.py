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


def test_appointment_audit_captures_reschedule_and_cancel_details(api_client, auth_headers):
    patient_res = api_client.post(
        "/patients",
        json={"first_name": "Reschedule", "last_name": "Audit"},
        headers=auth_headers,
    )
    assert patient_res.status_code == 201, patient_res.text
    patient_id = patient_res.json()["id"]

    start = datetime(2026, 1, 16, 9, 0, tzinfo=timezone.utc)
    end = datetime(2026, 1, 16, 9, 30, tzinfo=timezone.utc)
    create_res = api_client.post(
        "/appointments",
        json={
            "patient_id": patient_id,
            "starts_at": start.isoformat(),
            "ends_at": end.isoformat(),
            "status": "booked",
            "location_type": "clinic",
            "allow_outside_hours": True,
        },
        headers=auth_headers,
    )
    assert create_res.status_code == 201, create_res.text
    appointment_id = create_res.json()["id"]

    moved_start = datetime(2026, 1, 16, 10, 0, tzinfo=timezone.utc)
    moved_end = datetime(2026, 1, 16, 10, 30, tzinfo=timezone.utc)
    reschedule_res = api_client.patch(
        f"/appointments/{appointment_id}",
        json={
            "starts_at": moved_start.isoformat(),
            "ends_at": moved_end.isoformat(),
            "allow_outside_hours": True,
        },
        headers=auth_headers,
    )
    assert reschedule_res.status_code == 200, reschedule_res.text

    cancel_reason = "Patient cancelled due to illness"
    cancel_res = api_client.patch(
        f"/appointments/{appointment_id}",
        json={
            "status": "cancelled",
            "cancel_reason": cancel_reason,
            "allow_outside_hours": True,
        },
        headers=auth_headers,
    )
    assert cancel_res.status_code == 200, cancel_res.text

    audit_res = api_client.get(
        f"/audit/appointments/{appointment_id}",
        params={"limit": 10},
        headers=auth_headers,
    )
    assert audit_res.status_code == 200, audit_res.text
    entries = audit_res.json()

    actions = [entry["action"] for entry in entries]
    assert actions.count("appointment.updated") >= 2

    reschedule_entry = next(
        entry
        for entry in entries
        if entry["action"] == "appointment.updated"
        and entry.get("before_json", {}).get("starts_at") == start.isoformat()
        and entry.get("after_json", {}).get("starts_at") == moved_start.isoformat()
    )
    assert reschedule_entry["after_json"]["ends_at"] == moved_end.isoformat()

    cancel_entry = next(
        entry
        for entry in entries
        if entry["action"] == "appointment.updated"
        and entry.get("after_json", {}).get("status") == "cancelled"
    )
    assert cancel_entry["after_json"]["cancel_reason"] == cancel_reason
    assert cancel_entry["after_json"]["cancelled_at"] is not None
