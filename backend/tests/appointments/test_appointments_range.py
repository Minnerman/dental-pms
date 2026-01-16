from datetime import datetime, timezone


def test_range_excludes_end_boundary(api_client, auth_headers):
    patient_payload = {"first_name": "Range", "last_name": "Boundary"}
    patient_res = api_client.post("/patients", json=patient_payload, headers=auth_headers)
    assert patient_res.status_code == 201, patient_res.text
    patient_id = patient_res.json()["id"]

    def create_appt(start_dt: datetime, end_dt: datetime):
        payload = {
            "patient_id": patient_id,
            "starts_at": start_dt.isoformat(),
            "ends_at": end_dt.isoformat(),
            "status": "booked",
            "location_type": "clinic",
            "allow_outside_hours": True,
        }
        res = api_client.post("/appointments", json=payload, headers=auth_headers)
        assert res.status_code == 201, res.text
        return res.json()["id"]

    start_included = datetime(2026, 1, 10, 9, 0, tzinfo=timezone.utc)
    end_exclusive = datetime(2026, 1, 11, 9, 0, tzinfo=timezone.utc)

    included_id = create_appt(start_included, start_included.replace(hour=9, minute=30))
    excluded_id = create_appt(end_exclusive, end_exclusive.replace(hour=9, minute=30))

    res = api_client.get(
        "/appointments/range",
        params={"start": "2026-01-10", "end": "2026-01-11"},
        headers=auth_headers,
    )
    assert res.status_code == 200, res.text
    ids = {item["id"] for item in res.json()}

    assert included_id in ids
    assert excluded_id not in ids


def test_range_excludes_end_day_includes_late_start(api_client, auth_headers):
    patient_payload = {"first_name": "Late", "last_name": "Start"}
    patient_res = api_client.post("/patients", json=patient_payload, headers=auth_headers)
    assert patient_res.status_code == 201, patient_res.text
    patient_id = patient_res.json()["id"]

    def create_appt(start_dt: datetime, end_dt: datetime):
        payload = {
            "patient_id": patient_id,
            "starts_at": start_dt.isoformat(),
            "ends_at": end_dt.isoformat(),
            "status": "booked",
            "location_type": "clinic",
            "allow_outside_hours": True,
        }
        res = api_client.post("/appointments", json=payload, headers=auth_headers)
        assert res.status_code == 201, res.text
        return res.json()["id"]

    late_start = datetime(2026, 1, 19, 23, 59, 0, tzinfo=timezone.utc)
    late_end = datetime(2026, 1, 19, 23, 59, 59, tzinfo=timezone.utc)
    end_day_start = datetime(2026, 1, 20, 10, 0, tzinfo=timezone.utc)
    end_day_end = datetime(2026, 1, 20, 10, 30, tzinfo=timezone.utc)

    included_id = create_appt(late_start, late_end)
    excluded_id = create_appt(end_day_start, end_day_end)

    res = api_client.get(
        "/appointments/range",
        params={"start": "2026-01-15", "end": "2026-01-20"},
        headers=auth_headers,
    )
    assert res.status_code == 200, res.text
    ids = {item["id"] for item in res.json()}

    assert included_id in ids
    assert excluded_id not in ids
