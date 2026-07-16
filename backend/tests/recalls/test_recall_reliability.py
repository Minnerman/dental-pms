from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import delete, func, select

from app.core.security import create_access_token
from app.core.settings import settings
from app.db.session import SessionLocal
from app.models.audit_log import AuditLog
from app.models.capability import Capability, UserCapability
from app.models.patient import Patient
from app.models.patient_document import PatientDocument
from app.models.patient_recall import PatientRecall
from app.models.patient_recall_communication import PatientRecallCommunication
from app.models.user import Role
from app.services import capabilities as capability_service
from app.services.capabilities import get_user_capabilities, replace_user_capabilities
from app.services.users import create_user


def _create_patient(api_client, headers, label: str) -> int:
    response = api_client.post(
        "/patients",
        headers=headers,
        json={"first_name": "Recall", "last_name": label},
    )
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


def _create_recall(
    api_client,
    headers,
    patient_id: int,
    *,
    due_date: str = "2035-06-15",
    kind: str = "exam",
    notes: str | None = None,
) -> dict:
    response = api_client.post(
        f"/patients/{patient_id}/recalls",
        headers=headers,
        json={"kind": kind, "due_date": due_date, "status": "due", "notes": notes},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_user_headers() -> tuple[int, str, dict[str, str]]:
    suffix = uuid4().hex[:10]
    email = f"recall-reliability-{suffix}@example.com"
    password = "RecallReliability123!"
    session = SessionLocal()
    try:
        user = create_user(
            session,
            email=email,
            password=password,
            role=Role.reception,
            full_name="Recall Reliability User",
        )
        user_id = int(user.id)
    finally:
        session.close()
    token = create_access_token(
        subject=str(user_id),
        secret=settings.secret_key,
        alg=settings.jwt_alg,
        expires_minutes=settings.access_token_expire_minutes,
        extra={"role": Role.reception.value, "email": email},
    )
    return user_id, email, {"Authorization": f"Bearer {token}"}


def _set_capabilities(user_id: int, codes: list[str]) -> None:
    session = SessionLocal()
    try:
        replace_user_capabilities(session, user_id, codes)
    finally:
        session.close()


def _patient_audits(patient_id: int) -> list[AuditLog]:
    session = SessionLocal()
    try:
        return list(
            session.scalars(
                select(AuditLog)
                .where(
                    AuditLog.entity_type == "patient",
                    AuditLog.entity_id == str(patient_id),
                )
                .order_by(AuditLog.id.asc())
            )
        )
    finally:
        session.close()


def _side_effect_counts(
    patient_id: int, recall_id: int
) -> tuple[int, int, int, int, int]:
    session = SessionLocal()
    try:
        return (
            int(
                session.scalar(
                    select(func.count(PatientRecall.id)).where(
                        PatientRecall.patient_id == patient_id
                    )
                )
                or 0
            ),
            int(
                session.scalar(
                    select(func.count(PatientRecallCommunication.id)).where(
                        PatientRecallCommunication.recall_id == recall_id
                    )
                )
                or 0
            ),
            int(
                session.scalar(
                    select(func.count(PatientDocument.id)).where(
                        PatientDocument.patient_id == patient_id
                    )
                )
                or 0
            ),
            int(
                session.scalar(
                    select(func.count(AuditLog.id)).where(
                        AuditLog.entity_type == "patient",
                        AuditLog.entity_id == str(patient_id),
                    )
                )
                or 0
            ),
            int(
                session.scalar(
                    select(func.count(AuditLog.id)).where(
                        AuditLog.entity_type == "recall_export"
                    )
                )
                or 0
            ),
        )
    finally:
        session.close()


def test_recall_capabilities_are_authoritative_and_denials_are_side_effect_free(
    api_client,
    auth_headers,
):
    patient_id = _create_patient(api_client, auth_headers, f"Permissions-{uuid4().hex[:8]}")
    recall = _create_recall(api_client, auth_headers, patient_id)
    recall_id = int(recall["id"])
    baseline = _side_effect_counts(patient_id, recall_id)
    user_id, _email, user_headers = _create_user_headers()
    _set_capabilities(user_id, [])

    denied = [
        api_client.get("/recalls", headers=user_headers),
        api_client.get("/recalls/kpis", headers=user_headers),
        api_client.get("/recalls/export_count", headers=user_headers),
        api_client.get("/recalls/export.csv", headers=user_headers),
        api_client.get("/recalls/letters.zip", headers=user_headers),
        api_client.get(f"/patients/{patient_id}/recalls", headers=user_headers),
        api_client.get(
            f"/patients/{patient_id}/recalls/{recall_id}/communications",
            headers=user_headers,
        ),
        api_client.get(
            f"/patients/{patient_id}/recalls/{recall_id}/letter.pdf",
            headers=user_headers,
        ),
        api_client.post(
            f"/patients/{patient_id}/recalls",
            headers=user_headers,
            json={"kind": "exam", "due_date": "2035-07-15"},
        ),
        api_client.patch(
            f"/patients/{patient_id}/recalls/{recall_id}",
            headers=user_headers,
            json={"status": "completed"},
        ),
        api_client.post(
            f"/recalls/{recall_id}/contact",
            headers=user_headers,
            json={"method": "phone"},
        ),
        api_client.post(
            f"/patients/{patient_id}/recalls/{recall_id}/communications",
            headers=user_headers,
            json={"channel": "phone"},
        ),
        api_client.post(
            f"/recalls/{patient_id}/generate-document",
            headers=user_headers,
            json={"template_id": 0},
        ),
    ]
    assert {response.status_code for response in denied} == {403}
    assert _side_effect_counts(patient_id, recall_id) == baseline

    _set_capabilities(user_id, ["recalls.view"])
    assert api_client.get("/recalls", headers=user_headers).status_code == 200
    assert api_client.get("/recalls/kpis", headers=user_headers).status_code == 200
    assert (
        api_client.get(f"/patients/{patient_id}/recalls", headers=user_headers).status_code
        == 200
    )
    assert (
        api_client.get(
            f"/patients/{patient_id}/recalls/{recall_id}/communications",
            headers=user_headers,
        ).status_code
        == 200
    )
    assert api_client.get("/recalls/export_count", headers=user_headers).status_code == 403
    assert (
        api_client.patch(
            f"/patients/{patient_id}/recalls/{recall_id}",
            headers=user_headers,
            json={"notes": "denied"},
        ).status_code
        == 403
    )
    assert _side_effect_counts(patient_id, recall_id) == baseline


def test_recall_lifecycle_partial_updates_audit_and_idempotency(
    api_client,
    auth_headers,
):
    patient_id = _create_patient(api_client, auth_headers, f"Lifecycle-{uuid4().hex[:8]}")
    private_note = "synthetic private recall note"
    created = _create_recall(
        api_client,
        auth_headers,
        patient_id,
        notes="initial synthetic note",
    )
    recall_id = int(created["id"])
    created_audits = _patient_audits(patient_id)
    assert created_audits[-1].action == "recall.created"
    assert created_audits[-1].actor_user_id is not None

    updated = api_client.patch(
        f"/patients/{patient_id}/recalls/{recall_id}",
        headers={**auth_headers, "request-id": "recall-reliability-update"},
        json={
            "kind": "hygiene",
            "due_date": "2035-08-20",
            "notes": private_note,
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["status"] == "due"
    assert updated.json()["kind"] == "hygiene"
    assert updated.json()["notes"] == private_note
    update_audits = _patient_audits(patient_id)
    update_actions = [entry.action for entry in update_audits]
    assert "recall.due_date_changed" in update_actions
    assert "recall.type_changed" in update_actions
    assert "recall.notes_changed" in update_actions
    relevant = update_audits[-3:]
    assert all(entry.request_id == "recall-reliability-update" for entry in relevant)
    assert private_note not in str(
        [(entry.before_json, entry.after_json) for entry in relevant]
    )

    audit_count = len(update_audits)
    duplicate = api_client.patch(
        f"/patients/{patient_id}/recalls/{recall_id}",
        headers=auth_headers,
        json={
            "kind": "hygiene",
            "due_date": "2035-08-20",
            "notes": private_note,
        },
    )
    assert duplicate.status_code == 200, duplicate.text
    assert len(_patient_audits(patient_id)) == audit_count

    completed = api_client.patch(
        f"/patients/{patient_id}/recalls/{recall_id}",
        headers=auth_headers,
        json={"status": "completed", "outcome": "attended"},
    )
    assert completed.status_code == 200, completed.text
    completed_at = completed.json()["completed_at"]
    assert completed_at
    completed_audit_count = len(_patient_audits(patient_id))

    repeated_completion = api_client.patch(
        f"/patients/{patient_id}/recalls/{recall_id}",
        headers=auth_headers,
        json={"status": "completed", "outcome": "attended"},
    )
    assert repeated_completion.status_code == 200, repeated_completion.text
    assert repeated_completion.json()["completed_at"] == completed_at
    assert len(_patient_audits(patient_id)) == completed_audit_count

    reopened = api_client.patch(
        f"/patients/{patient_id}/recalls/{recall_id}",
        headers=auth_headers,
        json={"status": "due"},
    )
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["completed_at"] is None
    assert reopened.json()["outcome"] is None
    reopened_actions = [entry.action for entry in _patient_audits(patient_id)[-2:]]
    assert "recall.reopened" in reopened_actions
    assert "recall.outcome_changed" in reopened_actions

    cancelled = api_client.patch(
        f"/patients/{patient_id}/recalls/{recall_id}",
        headers=auth_headers,
        json={"status": "cancelled", "outcome": "cancelled"},
    )
    assert cancelled.status_code == 200, cancelled.text
    cancelled_audit_count = len(_patient_audits(patient_id))
    repeated_cancel = api_client.patch(
        f"/patients/{patient_id}/recalls/{recall_id}",
        headers=auth_headers,
        json={"status": "cancelled", "outcome": "cancelled"},
    )
    assert repeated_cancel.status_code == 200, repeated_cancel.text
    assert len(_patient_audits(patient_id)) == cancelled_audit_count

    invalid = api_client.patch(
        f"/patients/{patient_id}/recalls/{recall_id}",
        headers=auth_headers,
        json={"status": "due", "completed_at": datetime.now(timezone.utc).isoformat()},
    )
    assert invalid.status_code == 422, invalid.text
    assert len(_patient_audits(patient_id)) == cancelled_audit_count


def test_recall_validation_ownership_archive_and_filters_are_atomic(
    api_client,
    auth_headers,
):
    patient_id = _create_patient(api_client, auth_headers, f"Validation-{uuid4().hex[:8]}")
    other_patient_id = _create_patient(
        api_client, auth_headers, f"Other-{uuid4().hex[:8]}"
    )
    recall = _create_recall(api_client, auth_headers, patient_id)
    recall_id = int(recall["id"])
    baseline = _side_effect_counts(patient_id, recall_id)

    invalid_requests = [
        api_client.post(
            f"/patients/{patient_id}/recalls",
            headers=auth_headers,
            json={"kind": "invalid", "due_date": "2035-06-15"},
        ),
        api_client.post(
            f"/patients/{patient_id}/recalls",
            headers=auth_headers,
            json={"kind": "exam", "due_date": "not-a-date"},
        ),
        api_client.patch(
            f"/patients/{patient_id}/recalls/{recall_id}",
            headers=auth_headers,
            json={"due_date": None},
        ),
        api_client.patch(
            f"/patients/{patient_id}/recalls/{recall_id}",
            headers=auth_headers,
            json={"notes": "x" * 2001},
        ),
        api_client.patch(
            f"/patients/{other_patient_id}/recalls/{recall_id}",
            headers=auth_headers,
            json={"notes": "wrong owner"},
        ),
        api_client.get(
            "/recalls",
            headers=auth_headers,
            params={"status": "invalid"},
        ),
        api_client.get(
            "/recalls/export_count",
            headers=auth_headers,
            params={"start": "2035-06-20", "end": "2035-06-10"},
        ),
    ]
    assert [response.status_code for response in invalid_requests] == [
        422,
        422,
        422,
        422,
        404,
        422,
        422,
    ]
    assert _side_effect_counts(patient_id, recall_id) == baseline

    appointment = api_client.post(
        "/appointments",
        headers=auth_headers,
        json={
            "patient_id": other_patient_id,
            "starts_at": "2035-06-20T10:00:00+00:00",
            "ends_at": "2035-06-20T10:30:00+00:00",
            "status": "booked",
            "location_type": "clinic",
            "location": "Synthetic room",
            "allow_outside_hours": True,
        },
    )
    assert appointment.status_code == 201, appointment.text
    wrong_appointment = api_client.patch(
        f"/patients/{patient_id}/recalls/{recall_id}",
        headers=auth_headers,
        json={"linked_appointment_id": appointment.json()["id"]},
    )
    assert wrong_appointment.status_code == 422, wrong_appointment.text
    assert _side_effect_counts(patient_id, recall_id) == baseline

    count_filters = {"start": "2035-06-15", "end": "2035-06-15"}
    count_before_archive = api_client.get(
        "/recalls/export_count", headers=auth_headers, params=count_filters
    )
    assert count_before_archive.status_code == 200, count_before_archive.text
    visible_count = int(count_before_archive.json()["count"])

    archived = api_client.post(f"/patients/{patient_id}/archive", headers=auth_headers)
    assert archived.status_code == 200, archived.text
    count_after_archive = api_client.get(
        "/recalls/export_count", headers=auth_headers, params=count_filters
    )
    assert count_after_archive.status_code == 200, count_after_archive.text
    assert int(count_after_archive.json()["count"]) == visible_count - 1
    archived_audit_count = len(_patient_audits(patient_id))
    assert (
        api_client.get(f"/patients/{patient_id}/recalls", headers=auth_headers).status_code
        == 404
    )
    assert (
        api_client.patch(
            f"/patients/{patient_id}/recalls/{recall_id}",
            headers=auth_headers,
            json={"notes": "blocked archive"},
        ).status_code
        == 404
    )
    assert len(_patient_audits(patient_id)) == archived_audit_count

    restored = api_client.post(f"/patients/{patient_id}/restore", headers=auth_headers)
    assert restored.status_code == 200, restored.text
    count_after_restore = api_client.get(
        "/recalls/export_count", headers=auth_headers, params=count_filters
    )
    assert count_after_restore.status_code == 200, count_after_restore.text
    assert int(count_after_restore.json()["count"]) == visible_count


def test_recall_communication_validation_duplicate_guard_and_audit(
    api_client,
    auth_headers,
):
    patient_id = _create_patient(api_client, auth_headers, f"Contact-{uuid4().hex[:8]}")
    recall_id = int(_create_recall(api_client, auth_headers, patient_id)["id"])
    baseline = _side_effect_counts(patient_id, recall_id)
    future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()

    rejected = [
        api_client.post(
            f"/patients/{patient_id}/recalls/{recall_id}/communications",
            headers=auth_headers,
            json={},
        ),
        api_client.post(
            f"/patients/{patient_id}/recalls/{recall_id}/communications",
            headers=auth_headers,
            json={"channel": "other"},
        ),
        api_client.post(
            f"/patients/{patient_id}/recalls/{recall_id}/communications",
            headers=auth_headers,
            json={"channel": "phone", "other_detail": "not allowed"},
        ),
        api_client.post(
            f"/patients/{patient_id}/recalls/{recall_id}/communications",
            headers=auth_headers,
            json={"channel": "phone", "contacted_at": future},
        ),
    ]
    assert {response.status_code for response in rejected} == {422}
    assert _side_effect_counts(patient_id, recall_id) == baseline

    payload = {
        "channel": "other",
        "other_detail": "Synthetic channel",
        "outcome": "Synthetic outcome",
        "notes": "Synthetic communication note",
        "contacted_at": "2020-05-01T10:30:00+00:00",
    }
    created = api_client.post(
        f"/patients/{patient_id}/recalls/{recall_id}/communications",
        headers=auth_headers,
        json=payload,
    )
    assert created.status_code == 201, created.text
    assert created.json()["contacted_at"].startswith("2020-05-01T10:30:00")
    duplicate = api_client.post(
        f"/patients/{patient_id}/recalls/{recall_id}/communications",
        headers=auth_headers,
        json=payload,
    )
    assert duplicate.status_code == 201, duplicate.text
    assert duplicate.json()["id"] == created.json()["id"]

    after = _side_effect_counts(patient_id, recall_id)
    assert after[1] == baseline[1] + 1
    communication_audits = [
        entry
        for entry in _patient_audits(patient_id)
        if entry.action == "recall.communication_logged"
    ]
    assert len(communication_audits) == 1
    audit_payload = str(communication_audits[0].after_json)
    assert payload["notes"] not in audit_payload
    assert payload["outcome"] not in audit_payload
    assert communication_audits[0].actor_user_id is not None


def test_recall_compatibility_grant_is_one_time_and_revocation_survives_startup(
    api_client,
):
    user_id, _email, user_headers = _create_user_headers()
    session = SessionLocal()
    try:
        original_codes = [cap.code for cap in get_user_capabilities(session, user_id)]
        assert "patients.write" in original_codes
        retained = [code for code in original_codes if code != "recalls.write"]
        replace_user_capabilities(session, user_id, retained)
    finally:
        session.close()

    from app.main import startup

    startup()
    session = SessionLocal()
    try:
        restarted = {cap.code for cap in get_user_capabilities(session, user_id)}
    finally:
        session.close()
    assert "patients.write" in restarted
    assert "recalls.write" not in restarted
    assert api_client.get("/recalls", headers=user_headers).status_code == 200

    temporary_code = f"test.recall.compat.{uuid4().hex}"
    original_capabilities = capability_service.CAPABILITIES
    original_grants = capability_service.DEFAULT_GRANT_FROM
    session = SessionLocal()
    try:
        source = session.scalar(
            select(Capability).where(Capability.code == "patients.view")
        )
        assert source is not None
        if not session.scalar(
            select(UserCapability).where(
                UserCapability.user_id == user_id,
                UserCapability.capability_id == source.id,
            )
        ):
            session.add(UserCapability(user_id=user_id, capability_id=source.id))
            session.commit()

        capability_service.CAPABILITIES = [
            ("patients.view", "View patients"),
            (temporary_code, "Temporary recall compatibility test"),
        ]
        capability_service.DEFAULT_GRANT_FROM = {temporary_code: "patients.view"}
        capability_service.ensure_capabilities(session)
        temporary = session.scalar(
            select(Capability).where(Capability.code == temporary_code)
        )
        assert temporary is not None
        assert session.scalar(
            select(UserCapability).where(
                UserCapability.user_id == user_id,
                UserCapability.capability_id == temporary.id,
            )
        )

        session.execute(
            delete(UserCapability).where(
                UserCapability.user_id == user_id,
                UserCapability.capability_id == temporary.id,
            )
        )
        session.commit()
        capability_service.ensure_capabilities(session)
        assert not session.scalar(
            select(UserCapability).where(
                UserCapability.user_id == user_id,
                UserCapability.capability_id == temporary.id,
            )
        )
    finally:
        capability_service.CAPABILITIES = original_capabilities
        capability_service.DEFAULT_GRANT_FROM = original_grants
        temporary = session.scalar(
            select(Capability).where(Capability.code == temporary_code)
        )
        if temporary is not None:
            session.execute(
                delete(UserCapability).where(
                    UserCapability.capability_id == temporary.id
                )
            )
            session.delete(temporary)
            session.commit()
        session.close()


def test_export_count_page_only_matches_pagination(api_client, auth_headers):
    filters = {"start": "2036-01-10", "end": "2036-01-12"}
    before = api_client.get(
        "/recalls/export_count", headers=auth_headers, params=filters
    )
    assert before.status_code == 200, before.text
    baseline_count = int(before.json()["count"])

    for index in range(3):
        patient_id = _create_patient(
            api_client, auth_headers, f"Page-{index}-{uuid4().hex[:6]}"
        )
        _create_recall(
            api_client,
            auth_headers,
            patient_id,
            due_date=date(2036, 1, index + 10).isoformat(),
        )

    total = api_client.get(
        "/recalls/export_count", headers=auth_headers, params=filters
    )
    assert total.status_code == 200, total.text
    total_count = int(total.json()["count"])
    assert total_count == baseline_count + 3
    page = api_client.get(
        "/recalls/export_count",
        headers=auth_headers,
        params={
            **filters,
            "page_only": True,
            "limit": 1,
            "offset": total_count - 1,
        },
    )
    assert page.status_code == 200, page.text
    assert page.json()["count"] == 1
