from copy import deepcopy
from datetime import date, datetime, time, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.security import create_access_token
from app.core.settings import settings
from app.db.session import SessionLocal
from app.models.appointment import Appointment
from app.models.practice_schedule import PracticeClosure, PracticeHour, PracticeOverride
from app.models.user import Role, User
from app.services.capabilities import replace_user_capabilities
from app.services.schedule import get_practice_sessions, validate_appointment_window

DAY = date(2040, 6, 4)  # Monday, during British Summer Time.


def weekly(day=0, start="09:00", end="12:30", closed=False):
    return {"day_of_week": day, "start_time": None if closed else start,
        "end_time": None if closed else end, "is_closed": closed}


def split_schedule():
    return {"hours": [session for day in range(7) for session in (
        weekly(day), weekly(day, "14:00", "18:00"),
    )], "closures": [], "overrides": []}


def override(day=DAY.isoformat(), start="14:00", end="18:00", closed=False):
    return {"date": day, "start_time": None if closed else start,
        "end_time": None if closed else end, "is_closed": closed, "reason": "Synthetic closure"}


def hour(start, end, day=0):
    return PracticeHour(day_of_week=day, start_time=time.fromisoformat(start),
        end_time=time.fromisoformat(end), is_closed=False)


def date_override(start=None, end=None, closed=False):
    return PracticeOverride(date=DAY, start_time=time.fromisoformat(start) if start else None,
        end_time=time.fromisoformat(end) if end else None, is_closed=closed)


def test_split_sessions_cover_each_session_not_lunch_gap_and_merge_adjacent_sessions():
    hours = [hour("14:00", "18:00"), hour("09:00", "12:30")]
    assert get_practice_sessions(DAY, hours, [], []) == (
        [(time(9), time(12, 30)), (time(14), time(18))], None,
    )
    # Clock inputs in UTC resolve to the Monday's London summer time.
    for start, end, expected in (("08:00", "11:30", True), ("13:00", "17:00", True),
                                 ("11:00", "13:30", False), ("11:30", "12:00", False)):
        ok, _ = validate_appointment_window(datetime.fromisoformat(f"{DAY}T{start}:00+00:00"),
            datetime.fromisoformat(f"{DAY}T{end}:00+00:00"), hours, [], [])
        assert ok is expected
    assert get_practice_sessions(DAY, [hour("09:00", "12:00"), hour("12:00", "18:00")], [], []) == (
        [(time(9), time(18))], None,
    )


def test_date_overrides_replace_weekly_sessions_and_explicit_closed_has_highest_precedence():
    hours = [hour("09:00", "12:30"), hour("14:00", "18:00")]
    closures = [PracticeClosure(start_date=DAY, end_date=DAY, reason="Synthetic whole day")]
    assert get_practice_sessions(DAY, hours, closures, [date_override("14:00", "18:00")])[0] == [(time(14), time(18))]
    assert get_practice_sessions(DAY, hours, [], [date_override("09:00", "12:30")])[0] == [(time(9), time(12, 30))]
    assert get_practice_sessions(DAY, hours, closures, [date_override("10:00", "11:00"), date_override("15:00", "16:00")])[0] == [(time(10), time(11)), (time(15), time(16))]
    for rows in ([date_override("10:00", "11:00"), date_override(closed=True)],
                 [date_override(closed=True), date_override("10:00", "11:00")]):
        sessions, reason = get_practice_sessions(DAY, hours, closures, rows)
        assert sessions == [] and reason == "Practice closed (override)."
    assert get_practice_sessions(DAY, hours, closures, [])[0] == []
    assert get_practice_sessions(DAY, [], [], [])[0] == []


def test_malformed_legacy_override_never_falls_back_to_open_weekly_hours():
    hours = [hour("09:00", "18:00")]
    for rows in ([date_override("10:00")], [date_override("14:00", "12:00")],
                 [date_override("10:00", "14:00"), date_override("12:00", "16:00")]):
        sessions, reason = get_practice_sessions(DAY, hours, [], rows)
        assert sessions == [] and reason == "Practice hours not configured."


@pytest.fixture
def restore_schedule(api_client, auth_headers):
    response = api_client.get("/settings/schedule", headers=auth_headers)
    assert response.status_code == 200
    original = response.json()
    try:
        yield original
    finally:
        # The old GET shape, including row IDs, remains a valid PUT payload.
        restored = api_client.put("/settings/schedule", headers=auth_headers, json=original)
        assert restored.status_code == 200


def test_settings_persists_seven_day_split_sessions_and_half_day_overrides_without_touching_bookings(api_client, auth_headers, restore_schedule):
    patient = api_client.post("/patients", headers=auth_headers,
        json={"first_name": "Synthetic", "last_name": f"Schedule-{uuid4().hex[:8]}"})
    assert patient.status_code == 201
    created = api_client.post("/appointments", headers=auth_headers, json={
        "patient_id": patient.json()["id"], "starts_at": "2040-06-04T09:00:00+01:00",
        "ends_at": "2040-06-04T10:00:00+01:00", "status": "booked",
    })
    assert created.status_code == 201
    before = created.json()
    payload = split_schedule()
    payload["closures"] = [{"start_date": "2040-06-04", "end_date": "2040-06-10", "reason": "Synthetic leave"}]
    payload["overrides"] = [override(), override("2040-06-05", "09:00", "12:30"), override("2040-06-06", closed=True)]
    response = api_client.put("/settings/schedule", headers=auth_headers, json=payload)
    assert response.status_code == 200, response.text
    result = response.json()
    assert len(result["hours"]) == 14
    assert [row["day_of_week"] for row in result["hours"]] == [day for day in range(7) for _ in range(2)]
    assert len(result["overrides"]) == 3
    assert result["overrides"][0]["start_time"] == "14:00:00"
    assert result["overrides"][2]["is_closed"] is True
    assert api_client.get("/settings/schedule", headers=auth_headers).json() == result
    # Legacy clients round-tripping id fields must continue to work.
    assert api_client.put("/settings/schedule", headers=auth_headers, json=result).status_code == 200
    after = api_client.get(f"/appointments/{before['id']}", headers=auth_headers).json()
    assert after == before


@pytest.mark.parametrize("invalid", [
    {"hours": []},
    {"hours": [weekly(7)]},
    {"hours": [weekly(True)]},
    {"hours": [weekly(), weekly()]},
    {"hours": [weekly(), weekly(start="12:00", end="15:00")]},
    {"hours": [weekly(closed=True), weekly()]},
    {"hours": [weekly(closed=True), weekly(closed=True)]},
    {"hours": [weekly(start="12:00", end="09:00")]},
    {"hours": [weekly(start="09:00", end=None)]},
    {"hours": [weekly(start="09:00Z", end="12:00Z")]},
    {"hours": [weekly(start=32400)]},
    {"hours": [{**weekly(), "is_closed": True}]},
    {"hours": [{**weekly(), "unknown_session_field": True}]},
    {"overrides": [override(), override()]},
    {"overrides": [override(end=None)]},
    {"overrides": [override(closed=True), override()]},
    {"overrides": [override(start="18:00", end="14:00")]},
    {"closures": [{"start_date": "2040-06-05", "end_date": "2040-06-04"}]},
    {"closures": [{"start_date": "2040-06-04", "end_date": "2040-06-06"},
                  {"start_date": "2040-06-06", "end_date": "2040-06-08"}]},
    {"closures": [{"start_date": "2040-06-04", "end_date": "2040-06-06", "reason": "x" * 256}]},
])
def test_settings_rejects_invalid_session_changes_before_any_write(api_client, auth_headers, invalid):
    before = api_client.get("/settings/schedule", headers=auth_headers).json()
    payload = split_schedule()
    payload.update(deepcopy(invalid))
    result = api_client.put("/settings/schedule", headers=auth_headers, json=payload)
    assert result.status_code in (400, 422)
    assert api_client.get("/settings/schedule", headers=auth_headers).json() == before


def _user_headers(codes):
    with SessionLocal() as db:
        user = User(email=f"schedule-permission-{uuid4().hex}@example.com", full_name="Synthetic Reception",
            hashed_password="synthetic-not-a-login-hash", role=Role.reception)
        db.add(user)
        db.flush()
        user_id = user.id
        replace_user_capabilities(db, user_id, codes)
        token = create_access_token(subject=str(user_id), secret=settings.secret_key,
            alg=settings.jwt_alg, expires_minutes=5)
    return user_id, {"Authorization": f"Bearer {token}"}


def test_outside_hours_is_advisory_for_authorized_booking_and_rescheduling_with_audit(api_client, auth_headers, restore_schedule):
    closed = {"hours": [weekly(day, closed=True) for day in range(7)], "closures": [], "overrides": []}
    assert api_client.put("/settings/schedule", headers=auth_headers, json=closed).status_code == 200
    patient = api_client.post("/patients", headers=auth_headers,
        json={"first_name": "Synthetic", "last_name": f"OutOfHours-{uuid4().hex[:8]}"})
    assert patient.status_code == 201
    user_id, headers = _user_headers(["appointments.write"])
    payload = {"patient_id": patient.json()["id"], "starts_at": "2040-06-04T18:00:00+01:00",
        "ends_at": "2040-06-04T22:00:00+01:00", "status": "booked", "allow_outside_hours": False}
    created = api_client.post("/appointments", headers=headers, json=payload)
    assert created.status_code == 201, created.text
    appointment_id = created.json()["id"]
    assert api_client.put("/settings/schedule", headers=headers, json=closed).status_code == 403
    # No new capability is granted by permitting out-of-hours appointments.
    update = {"starts_at": "2040-06-04T17:00:00+01:00", "ends_at": "2040-06-04T21:00:00+01:00"}
    assert api_client.patch(f"/appointments/{appointment_id}", headers=headers, json=update).status_code == 403
    with SessionLocal() as db:
        replace_user_capabilities(db, user_id, ["appointments.reschedule"])
    moved = api_client.patch(f"/appointments/{appointment_id}", headers=headers, json=update)
    assert moved.status_code == 200, moved.text
    assert api_client.post("/appointments", headers=headers, json=payload).status_code == 403
    audit = api_client.get(f"/appointments/{appointment_id}/audit", headers=auth_headers)
    assert audit.status_code == 200
    assert [row["action"] for row in audit.json()][:2] == ["appointment.rescheduled", "appointment.created"]
    for invalid in (
        {"starts_at": "2040-06-04T21:00:00+01:00", "ends_at": "2040-06-04T17:00:00+01:00"},
        {"starts_at": "2040-06-04T21:00:00+01:00", "ends_at": "2040-06-05T01:00:00+01:00"},
        {"starts_at": "2040-06-04T17:00:00", "ends_at": "2040-06-04T21:00:00"},
    ):
        assert api_client.patch(f"/appointments/{appointment_id}", headers=headers,
            json={**invalid, "allow_outside_hours": True}).status_code == 400
    assert api_client.get(f"/appointments/{appointment_id}/audit", headers=auth_headers).json() == audit.json()
    with SessionLocal() as db:
        stored = db.scalar(select(Appointment).where(Appointment.id == appointment_id))
        assert stored.starts_at == datetime(2040, 6, 4, 16, tzinfo=timezone.utc)
        assert stored.ends_at == datetime(2040, 6, 4, 20, tzinfo=timezone.utc)
