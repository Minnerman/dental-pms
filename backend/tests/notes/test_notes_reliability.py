from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import delete, func, select

from app.core.security import create_access_token
from app.core.settings import settings
from app.db.session import SessionLocal
from app.models.appointment import Appointment, AppointmentLocationType, AppointmentStatus
from app.models.audit_log import AuditLog
from app.models.capability import Capability, UserCapability
from app.models.note import Note
from app.models.patient import Patient
from app.models.user import Role, User
from app.schemas.note import MAX_NOTE_BODY_LENGTH
from app.services import capabilities as capability_service
from app.services.capabilities import get_user_capabilities, replace_user_capabilities
from app.services.users import create_user


def _create_patient(api_client, headers, label: str) -> int:
    response = api_client.post(
        "/patients",
        headers=headers,
        json={"first_name": "Notes", "last_name": label},
    )
    assert response.status_code == 201
    return int(response.json()["id"])


def _create_appointment(patient_id: int, *, label: str) -> int:
    session = SessionLocal()
    try:
        actor = session.scalar(select(User).where(User.role == Role.superadmin))
        assert actor is not None
        appointment = Appointment(
            patient_id=patient_id,
            starts_at=datetime(2032, 4, 10, 9, 0, tzinfo=timezone.utc),
            ends_at=datetime(2032, 4, 10, 9, 30, tzinfo=timezone.utc),
            status=AppointmentStatus.booked,
            location_type=AppointmentLocationType.clinic,
            location=label,
            created_by_user_id=actor.id,
            updated_by_user_id=actor.id,
        )
        session.add(appointment)
        session.commit()
        session.refresh(appointment)
        return int(appointment.id)
    finally:
        session.close()


def _create_user_headers(*, active: bool = True) -> tuple[int, dict[str, str]]:
    suffix = uuid4().hex[:10]
    email = f"notes-reliability-{suffix}@example.com"
    session = SessionLocal()
    try:
        user = create_user(
            session,
            email=email,
            password="NotesReliability123!",
            role=Role.reception,
            full_name="Notes Reliability User",
            is_active=active,
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
    return user_id, {"Authorization": f"Bearer {token}"}


def _set_capabilities(user_id: int, codes: list[str]) -> None:
    session = SessionLocal()
    try:
        replace_user_capabilities(session, user_id, codes)
    finally:
        session.close()


def _note_count(patient_id: int) -> int:
    session = SessionLocal()
    try:
        return int(
            session.scalar(select(func.count(Note.id)).where(Note.patient_id == patient_id)) or 0
        )
    finally:
        session.close()


def _note_audits(note_id: int) -> list[AuditLog]:
    session = SessionLocal()
    try:
        return list(
            session.scalars(
                select(AuditLog)
                .where(AuditLog.entity_type == "note", AuditLog.entity_id == str(note_id))
                .order_by(AuditLog.id)
            )
        )
    finally:
        session.close()


def _archive_model(model: type[Patient] | type[Appointment], object_id: int) -> None:
    session = SessionLocal()
    try:
        row = session.get(model, object_id)
        actor = session.scalar(select(User).where(User.role == Role.superadmin))
        assert row is not None and actor is not None
        row.deleted_at = datetime.now(timezone.utc)
        row.deleted_by_user_id = actor.id
        session.add(row)
        session.commit()
    finally:
        session.close()


def _restore_model(model: type[Patient] | type[Appointment], object_id: int) -> None:
    session = SessionLocal()
    try:
        row = session.get(model, object_id)
        assert row is not None
        row.deleted_at = None
        row.deleted_by_user_id = None
        session.add(row)
        session.commit()
    finally:
        session.close()


def test_note_capabilities_are_authoritative_and_denials_are_side_effect_free(
    api_client,
    auth_headers,
):
    patient_id = _create_patient(api_client, auth_headers, uuid4().hex[:8])
    appointment_id = _create_appointment(patient_id, label=f"Note-{uuid4().hex[:6]}")
    created = api_client.post(
        f"/appointments/{appointment_id}/notes",
        headers=auth_headers,
        json={"body": "Synthetic existing note", "note_type": "clinical"},
    )
    assert created.status_code == 201
    note_id = int(created.json()["id"])
    baseline_count = _note_count(patient_id)
    baseline_audits = len(_note_audits(note_id))

    user_id, user_headers = _create_user_headers()
    _set_capabilities(user_id, [])
    denied_reads = [
        api_client.get(f"/patients/{patient_id}/notes", headers=user_headers),
        api_client.get(f"/appointments/{appointment_id}/notes", headers=user_headers),
        api_client.get("/notes", headers=user_headers),
        api_client.get(f"/notes/{note_id}/audit", headers=user_headers),
    ]
    denied_writes = [
        api_client.post(
            f"/patients/{patient_id}/notes",
            headers=user_headers,
            json={"body": "Synthetic denied patient note"},
        ),
        api_client.post(
            f"/appointments/{appointment_id}/notes",
            headers=user_headers,
            json={"body": "Synthetic denied appointment note"},
        ),
        api_client.patch(
            f"/notes/{note_id}",
            headers=user_headers,
            json={"body": "Synthetic denied update"},
        ),
        api_client.post(f"/notes/{note_id}/archive", headers=user_headers),
    ]
    assert {response.status_code for response in denied_reads + denied_writes} == {403}
    assert _note_count(patient_id) == baseline_count
    assert len(_note_audits(note_id)) == baseline_audits

    _set_capabilities(user_id, ["notes.write"])
    write_only_responses = [
        api_client.post(
            f"/patients/{patient_id}/notes",
            headers=user_headers,
            json={"body": "Synthetic write-only patient note"},
        ),
        api_client.post(
            f"/appointments/{appointment_id}/notes",
            headers=user_headers,
            json={"body": "Synthetic write-only appointment note"},
        ),
        api_client.post(
            "/notes",
            headers=user_headers,
            json={"patient_id": patient_id, "body": "Synthetic write-only global note"},
        ),
        api_client.patch(f"/notes/{note_id}", headers=user_headers, json={}),
        api_client.post(f"/notes/{note_id}/archive", headers=user_headers),
        api_client.post(f"/notes/{note_id}/restore", headers=user_headers),
        api_client.patch(
            f"/appointments/{appointment_id}/notes/{note_id}",
            headers=user_headers,
            json={},
        ),
        api_client.post(
            f"/appointments/{appointment_id}/notes/{note_id}/archive",
            headers=user_headers,
        ),
        api_client.post(
            f"/appointments/{appointment_id}/notes/{note_id}/restore",
            headers=user_headers,
        ),
        api_client.post(
            f"/patients/{patient_id}/notes/{note_id}/archive",
            headers=user_headers,
        ),
        api_client.post(
            f"/patients/{patient_id}/notes/{note_id}/restore",
            headers=user_headers,
        ),
    ]
    assert {response.status_code for response in write_only_responses} == {403}
    assert all("Synthetic existing note" not in response.text for response in write_only_responses)
    assert _note_count(patient_id) == baseline_count
    assert len(_note_audits(note_id)) == baseline_audits

    _set_capabilities(user_id, ["notes.view"])
    assert all(
        response.status_code == 200
        for response in (
            api_client.get(f"/patients/{patient_id}/notes", headers=user_headers),
            api_client.get(f"/appointments/{appointment_id}/notes", headers=user_headers),
            api_client.get("/notes", headers=user_headers),
            api_client.get(f"/notes/{note_id}/audit", headers=user_headers),
        )
    )
    assert (
        api_client.patch(
            f"/notes/{note_id}",
            headers=user_headers,
            json={"body": "Synthetic still denied"},
        ).status_code
        == 403
    )
    assert _note_count(patient_id) == baseline_count
    assert len(_note_audits(note_id)) == baseline_audits

    disabled_user_id, disabled_headers = _create_user_headers(active=False)
    _set_capabilities(disabled_user_id, ["notes.view", "notes.write"])
    assert api_client.get("/notes", headers=disabled_headers).status_code == 401
    assert (
        api_client.post(
            f"/patients/{patient_id}/notes",
            headers=disabled_headers,
            json={"body": "Synthetic disabled denial"},
        ).status_code
        == 401
    )
    assert _note_count(patient_id) == baseline_count


def test_note_validation_idempotency_noop_lifecycle_and_safe_audit(
    api_client,
    auth_headers,
):
    patient_id = _create_patient(api_client, auth_headers, uuid4().hex[:8])
    appointment_id = _create_appointment(patient_id, label=f"Validation-{uuid4().hex[:6]}")
    invalid_payloads = [
        {"body": "   ", "note_type": "clinical"},
        {"body": "x" * (MAX_NOTE_BODY_LENGTH + 1), "note_type": "clinical"},
        {"body": None, "note_type": "clinical"},
        {"body": "Synthetic invalid type", "note_type": "unsupported"},
    ]
    for payload in invalid_payloads:
        response = api_client.post(
            f"/appointments/{appointment_id}/notes",
            headers=auth_headers,
            json=payload,
        )
        assert response.status_code == 422
    assert _note_count(patient_id) == 0

    request_headers = {**auth_headers, "Request-Id": f"note-{uuid4().hex}"}
    create_payload = {"body": "  Synthetic idempotent note  ", "note_type": "clinical"}
    first = api_client.post(
        f"/appointments/{appointment_id}/notes",
        headers=request_headers,
        json=create_payload,
    )
    duplicate = api_client.post(
        f"/appointments/{appointment_id}/notes",
        headers=request_headers,
        json=create_payload,
    )
    assert first.status_code == 201
    assert duplicate.status_code == 201
    assert duplicate.json()["id"] == first.json()["id"]
    assert first.json()["body"] == "Synthetic idempotent note"
    assert _note_count(patient_id) == 1
    note_id = int(first.json()["id"])
    audits = _note_audits(note_id)
    assert [audit.action for audit in audits] == ["note.created"]
    assert audits[0].actor_user_id is not None
    assert audits[0].after_json["patient_id"] == patient_id
    assert audits[0].after_json["appointment_id"] == appointment_id
    assert "body" not in audits[0].after_json

    before_updated_at = first.json()["updated_at"]
    before_updated_by = first.json()["updated_by"]
    noop = api_client.patch(
        f"/appointments/{appointment_id}/notes/{note_id}",
        headers=auth_headers,
        json={"body": "  Synthetic idempotent note  ", "note_type": "clinical"},
    )
    assert noop.status_code == 200
    assert noop.json()["updated_at"] == before_updated_at
    assert noop.json()["updated_by"] == before_updated_by
    assert len(_note_audits(note_id)) == 1

    for payload in (
        {"body": None},
        {"note_type": None},
        {"body": "  "},
        {"body": "x" * (MAX_NOTE_BODY_LENGTH + 1)},
    ):
        rejected = api_client.patch(
            f"/notes/{note_id}", headers=auth_headers, json=payload
        )
        assert rejected.status_code == 422
    assert len(_note_audits(note_id)) == 1

    updated = api_client.patch(
        f"/notes/{note_id}",
        headers=auth_headers,
        json={"body": "Synthetic changed note", "note_type": "admin"},
    )
    assert updated.status_code == 200
    assert updated.json()["body"] == "Synthetic changed note"
    assert updated.json()["note_type"] == "admin"
    update_audit = _note_audits(note_id)[-1]
    assert update_audit.action == "note.updated"
    assert update_audit.before_json["changed_fields"] == ["body", "note_type"]
    assert update_audit.after_json["changed_fields"] == ["body", "note_type"]
    assert update_audit.after_json["body_changed"] is True
    assert "body" not in update_audit.before_json
    assert "body" not in update_audit.after_json

    archived = api_client.post(f"/notes/{note_id}/archive", headers=auth_headers)
    archived_again = api_client.post(f"/notes/{note_id}/archive", headers=auth_headers)
    assert archived.status_code == 200
    assert archived_again.status_code == 200
    assert archived.json()["deleted_at"] is not None
    assert archived.json()["deleted_by"] is not None
    assert (
        api_client.patch(
            f"/notes/{note_id}",
            headers=auth_headers,
            json={"body": "Synthetic archived edit denial"},
        ).status_code
        == 404
    )
    restored = api_client.post(f"/notes/{note_id}/restore", headers=auth_headers)
    restored_again = api_client.post(f"/notes/{note_id}/restore", headers=auth_headers)
    assert restored.status_code == 200
    assert restored_again.status_code == 200
    assert restored.json()["deleted_at"] is None
    actions = [audit.action for audit in _note_audits(note_id)]
    assert actions == ["note.created", "note.updated", "note.archived", "note.restored"]


def test_note_ownership_and_parent_lifecycle_apply_to_global_routes(
    api_client,
    auth_headers,
):
    patient_a = _create_patient(api_client, auth_headers, uuid4().hex[:8])
    patient_b = _create_patient(api_client, auth_headers, uuid4().hex[:8])
    appointment_a = _create_appointment(patient_a, label=f"Owner-A-{uuid4().hex[:6]}")
    appointment_b = _create_appointment(patient_b, label=f"Owner-B-{uuid4().hex[:6]}")

    mismatch = api_client.post(
        f"/patients/{patient_b}/notes",
        headers=auth_headers,
        json={
            "appointment_id": appointment_a,
            "body": "Synthetic ownership mismatch",
            "note_type": "clinical",
        },
    )
    assert mismatch.status_code == 400
    created = api_client.post(
        "/notes",
        headers=auth_headers,
        json={
            "patient_id": patient_a,
            "appointment_id": appointment_a,
            "body": "Synthetic scoped note",
            "note_type": "clinical",
        },
    )
    assert created.status_code == 201
    note_id = int(created.json()["id"])

    wrong_scope = [
        api_client.patch(
            f"/appointments/{appointment_b}/notes/{note_id}",
            headers=auth_headers,
            json={"body": "Synthetic cross-appointment update"},
        ),
        api_client.post(
            f"/appointments/{appointment_b}/notes/{note_id}/archive",
            headers=auth_headers,
        ),
        api_client.post(
            f"/appointments/{appointment_b}/notes/{note_id}/restore",
            headers=auth_headers,
        ),
    ]
    assert {response.status_code for response in wrong_scope} == {404}

    _archive_model(Appointment, appointment_a)
    assert (
        api_client.get(f"/appointments/{appointment_a}/notes", headers=auth_headers).status_code
        == 404
    )
    patient_notes = api_client.get(
        f"/patients/{patient_a}/notes",
        headers=auth_headers,
        params={"include_deleted": "true"},
    )
    assert patient_notes.status_code == 200
    assert patient_notes.json() == []
    assert all(item["id"] != note_id for item in api_client.get("/notes", headers=auth_headers).json())
    assert api_client.get(f"/notes/{note_id}/audit", headers=auth_headers).status_code == 404
    assert api_client.post(f"/notes/{note_id}/archive", headers=auth_headers).status_code == 404

    _restore_model(Appointment, appointment_a)
    assert api_client.get(f"/notes/{note_id}/audit", headers=auth_headers).status_code == 200
    _archive_model(Patient, patient_a)
    for response in (
        api_client.get(
            f"/patients/{patient_a}/notes",
            headers=auth_headers,
            params={"include_deleted": "true"},
        ),
        api_client.get(f"/appointments/{appointment_a}/notes", headers=auth_headers),
        api_client.get(f"/notes/{note_id}/audit", headers=auth_headers),
        api_client.patch(
            f"/notes/{note_id}",
            headers=auth_headers,
            json={"body": "Synthetic archived-patient denial"},
        ),
    ):
        assert response.status_code == 404
    assert all(item["id"] != note_id for item in api_client.get("/notes", headers=auth_headers).json())


def test_notes_view_compatibility_grant_is_one_time_and_revocation_survives_startup(
    api_client,
):
    user_id, user_headers = _create_user_headers()
    session = SessionLocal()
    try:
        initial_codes = {cap.code for cap in get_user_capabilities(session, user_id)}
        assert "patients.view" in initial_codes
        assert "notes.view" in initial_codes
        assert "notes.write" in initial_codes
        replace_user_capabilities(
            session,
            user_id,
            sorted(initial_codes - {"notes.view"}),
        )
    finally:
        session.close()

    from app.main import startup

    startup()

    session = SessionLocal()
    try:
        restarted_codes = {cap.code for cap in get_user_capabilities(session, user_id)}
    finally:
        session.close()
    assert "patients.view" in restarted_codes
    assert "notes.view" not in restarted_codes
    assert "notes.write" in restarted_codes
    assert api_client.get("/notes", headers=user_headers).status_code == 403

    temporary_code = f"test.notes.compat.{uuid4().hex}"
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
            (temporary_code, "Temporary notes compatibility test"),
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
