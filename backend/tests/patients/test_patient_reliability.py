from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models.audit_log import AuditLog
from app.models.patient import Patient
from app.models.user import Role
from app.services.capabilities import get_user_capabilities, replace_user_capabilities
from app.services.users import create_user


def _create_user_headers(api_client) -> tuple[int, str, dict[str, str]]:
    suffix = uuid4().hex[:10]
    email = f"patient-reliability-{suffix}@example.com"
    password = "PatientReliability123!"
    session = SessionLocal()
    try:
        user = create_user(
            session,
            email=email,
            password=password,
            role=Role.reception,
            full_name="Patient Reliability User",
        )
        user_id = int(user.id)
    finally:
        session.close()

    login = api_client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    return user_id, email, {"Authorization": f"Bearer {login.json()['access_token']}"}


def _set_capabilities(user_id: int, codes: list[str]) -> None:
    session = SessionLocal()
    try:
        replace_user_capabilities(session, user_id, codes)
    finally:
        session.close()


def _patient_audit_count(patient_id: int) -> int:
    session = SessionLocal()
    try:
        return int(
            session.scalar(
                select(func.count(AuditLog.id)).where(
                    AuditLog.entity_type == "patient",
                    AuditLog.entity_id == str(patient_id),
                )
            )
            or 0
        )
    finally:
        session.close()


def _patient_count() -> int:
    session = SessionLocal()
    try:
        return int(session.scalar(select(func.count(Patient.id))) or 0)
    finally:
        session.close()


def _audit(api_client, headers, patient_id: int) -> list[dict]:
    response = api_client.get(f"/patients/{patient_id}/audit", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_patient_capabilities_are_authoritative_and_denials_have_no_side_effects(
    api_client,
    auth_headers,
):
    suffix = uuid4().hex[:10]
    created = api_client.post(
        "/patients",
        headers=auth_headers,
        json={"first_name": "Permission", "last_name": suffix},
    )
    assert created.status_code == 201, created.text
    patient_id = int(created.json()["id"])
    baseline_audits = _patient_audit_count(patient_id)
    baseline_patients = _patient_count()

    user_id, email, user_headers = _create_user_headers(api_client)
    _set_capabilities(user_id, [])

    denied_requests = [
        api_client.get("/patients", headers=user_headers),
        api_client.get("/patients/search", params={"q": suffix}, headers=user_headers),
        api_client.get(f"/patients/{patient_id}", headers=user_headers),
        api_client.get(f"/patients/{patient_id}/audit", headers=user_headers),
        api_client.post(
            "/patients",
            headers=user_headers,
            json={"first_name": "Denied", "last_name": suffix},
        ),
        api_client.patch(
            f"/patients/{patient_id}",
            headers=user_headers,
            json={"last_name": "Denied update"},
        ),
        api_client.post(f"/patients/{patient_id}/archive", headers=user_headers),
        api_client.post(f"/patients/{patient_id}/restore", headers=user_headers),
    ]
    assert {response.status_code for response in denied_requests} == {403}
    assert _patient_count() == baseline_patients
    assert _patient_audit_count(patient_id) == baseline_audits

    _set_capabilities(user_id, ["patients.view"])
    assert api_client.get("/patients", headers=user_headers).status_code == 200
    assert api_client.get(f"/patients/{patient_id}", headers=user_headers).status_code == 200
    assert api_client.get(f"/patients/{patient_id}/audit", headers=user_headers).status_code == 200
    assert (
        api_client.get("/patients/search", params={"q": suffix}, headers=user_headers).status_code
        == 200
    )
    assert (
        api_client.patch(
            f"/patients/{patient_id}",
            headers=user_headers,
            json={"last_name": "Still denied"},
        ).status_code
        == 403
    )
    assert _patient_audit_count(patient_id) == baseline_audits

    _set_capabilities(user_id, ["patients.view", "patients.write"])
    updated = api_client.patch(
        f"/patients/{patient_id}",
        headers=user_headers,
        json={"last_name": f"Updated-{suffix}"},
    )
    assert updated.status_code == 200, updated.text
    archived = api_client.post(f"/patients/{patient_id}/archive", headers=user_headers)
    assert archived.status_code == 200, archived.text
    restored = api_client.post(f"/patients/{patient_id}/restore", headers=user_headers)
    assert restored.status_code == 200, restored.text
    actions = _audit(api_client, user_headers, patient_id)
    assert actions[0]["action"] == "restore"
    assert actions[1]["action"] == "archive"
    assert actions[2]["action"] == "update"
    assert actions[2]["actor_email"] == email


def test_revoked_patient_write_capability_remains_revoked_after_startup(
    api_client,
):
    user_id, _email, user_headers = _create_user_headers(api_client)
    session = SessionLocal()
    try:
        retained = [
            capability.code
            for capability in get_user_capabilities(session, user_id)
            if capability.code != "patients.write"
        ]
        replace_user_capabilities(session, user_id, retained)
    finally:
        session.close()

    from app.main import startup

    startup()

    session = SessionLocal()
    try:
        restarted_codes = {
            capability.code for capability in get_user_capabilities(session, user_id)
        }
    finally:
        session.close()
    assert "patients.view" in restarted_codes
    assert "patients.write" not in restarted_codes
    assert api_client.get("/patients", headers=user_headers).status_code == 200
    denied = api_client.post(
        "/patients",
        headers=user_headers,
        json={"first_name": "Restart", "last_name": "Denied"},
    )
    assert denied.status_code == 403


def test_patient_validation_lifecycle_search_and_audit_are_atomic(
    api_client,
    auth_headers,
):
    suffix = uuid4().hex[:10]
    baseline_patients = _patient_count()
    future_dob = (date.today() + timedelta(days=1)).isoformat()
    invalid_payloads = [
        {"first_name": "   ", "last_name": "Blank"},
        {"first_name": "Future", "last_name": "DOB", "date_of_birth": future_dob},
        {"first_name": "Invalid", "last_name": "Email", "email": "not-an-email"},
        {"first_name": "x" * 121, "last_name": "Oversized"},
    ]
    for payload in invalid_payloads:
        response = api_client.post("/patients", headers=auth_headers, json=payload)
        assert response.status_code == 422, response.text
    assert _patient_count() == baseline_patients

    created = api_client.post(
        "/patients",
        headers=auth_headers,
        json={
            "first_name": "  Atomic  ",
            "last_name": f"Patient-{suffix}",
            "phone": "02070000000",
            "email": f"atomic-{suffix}@example.com",
            "date_of_birth": "1990-04-15",
        },
    )
    assert created.status_code == 201, created.text
    patient = created.json()
    patient_id = int(patient["id"])
    assert patient["first_name"] == "Atomic"
    assert _patient_audit_count(patient_id) == 1

    invalid_updates = [
        {"first_name": None},
        {"last_name": "   "},
        {"patient_category": None},
        {"care_setting": None},
        {"date_of_birth": future_dob},
    ]
    for payload in invalid_updates:
        response = api_client.patch(
            f"/patients/{patient_id}",
            headers=auth_headers,
            json=payload,
        )
        assert response.status_code == 422, response.text
    assert _patient_audit_count(patient_id) == 1

    updated = api_client.patch(
        f"/patients/{patient_id}",
        headers=auth_headers,
        json={"last_name": f"Renamed-{suffix}"},
    )
    assert updated.status_code == 200, updated.text
    updated_patient = updated.json()
    assert updated_patient["first_name"] == "Atomic"
    assert updated_patient["last_name"] == f"Renamed-{suffix}"
    assert updated_patient["phone"] == "02070000000"
    update_audit = _audit(api_client, auth_headers, patient_id)[0]
    assert update_audit["action"] == "update"
    assert update_audit["before_json"]["last_name"] == f"Patient-{suffix}"
    assert update_audit["after_json"]["last_name"] == f"Renamed-{suffix}"
    assert update_audit["before_json"]["first_name"] == "Atomic"
    assert update_audit["after_json"]["first_name"] == "Atomic"

    audit_count = _patient_audit_count(patient_id)
    unchanged_updated_at = updated_patient["updated_at"]
    duplicate = api_client.patch(
        f"/patients/{patient_id}",
        headers=auth_headers,
        json={"last_name": f"Renamed-{suffix}"},
    )
    assert duplicate.status_code == 200, duplicate.text
    assert duplicate.json()["updated_at"] == unchanged_updated_at
    assert _patient_audit_count(patient_id) == audit_count

    listed = api_client.get(
        "/patients",
        params={"query": f"Renamed-{suffix}"},
        headers=auth_headers,
    )
    searched = api_client.get(
        "/patients/search",
        params={"q": f"Renamed-{suffix}"},
        headers=auth_headers,
    )
    assert patient_id in {item["id"] for item in listed.json()}
    assert patient_id in {item["id"] for item in searched.json()}

    archived = api_client.post(f"/patients/{patient_id}/archive", headers=auth_headers)
    assert archived.status_code == 200, archived.text
    archive_audit_count = _patient_audit_count(patient_id)
    assert _audit(api_client, auth_headers, patient_id)[0]["action"] == "archive"
    repeated_archive = api_client.post(
        f"/patients/{patient_id}/archive", headers=auth_headers
    )
    assert repeated_archive.status_code == 200
    assert _patient_audit_count(patient_id) == archive_audit_count
    assert api_client.get(f"/patients/{patient_id}", headers=auth_headers).status_code == 404
    assert (
        api_client.patch(
            f"/patients/{patient_id}",
            headers=auth_headers,
            json={"last_name": "Must not apply"},
        ).status_code
        == 404
    )
    assert _patient_audit_count(patient_id) == archive_audit_count
    active_list = api_client.get("/patients", headers=auth_headers).json()
    active_search = api_client.get(
        "/patients/search", params={"q": f"Renamed-{suffix}"}, headers=auth_headers
    ).json()
    assert patient_id not in {item["id"] for item in active_list}
    assert patient_id not in {item["id"] for item in active_search}
    archived_list = api_client.get(
        "/patients", params={"include_deleted": True}, headers=auth_headers
    ).json()
    assert patient_id in {item["id"] for item in archived_list}

    restored = api_client.post(f"/patients/{patient_id}/restore", headers=auth_headers)
    assert restored.status_code == 200, restored.text
    restore_audit_count = _patient_audit_count(patient_id)
    assert _audit(api_client, auth_headers, patient_id)[0]["action"] == "restore"
    repeated_restore = api_client.post(
        f"/patients/{patient_id}/restore", headers=auth_headers
    )
    assert repeated_restore.status_code == 200
    assert _patient_audit_count(patient_id) == restore_audit_count
    restored_search = api_client.get(
        "/patients/search", params={"q": f"Renamed-{suffix}"}, headers=auth_headers
    ).json()
    assert patient_id in {item["id"] for item in restored_search}

    missing_id = 2_000_000_000
    assert api_client.get(f"/patients/{missing_id}", headers=auth_headers).status_code == 404
    assert (
        api_client.patch(
            f"/patients/{missing_id}", headers=auth_headers, json={"last_name": "Missing"}
        ).status_code
        == 404
    )
    assert api_client.post(f"/patients/{missing_id}/archive", headers=auth_headers).status_code == 404
    assert api_client.post(f"/patients/{missing_id}/restore", headers=auth_headers).status_code == 404
    assert api_client.get(f"/patients/{missing_id}/audit", headers=auth_headers).status_code == 404
