from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import func, select

from app.core.security import create_access_token
from app.core.settings import settings
from app.db.session import SessionLocal
from app.models.appointment import Appointment, AppointmentLocationType, AppointmentStatus
from app.models.audit_log import AuditLog
from app.models.clinical import Procedure, ToothNote, TreatmentPlanItem
from app.models.user import Role, User
from app.services.capabilities import get_user_capabilities, replace_user_capabilities
from app.services.users import create_user


def _create_patient(api_client, headers, label: str) -> int:
    response = api_client.post(
        "/patients",
        headers=headers,
        json={"first_name": "Clinical", "last_name": label},
    )
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


def _create_user_headers(api_client, *, active: bool = True) -> tuple[int, dict[str, str]]:
    del api_client
    suffix = uuid4().hex[:10]
    email = f"clinical-reliability-{suffix}@example.com"
    password = "ClinicalReliability123!"
    session = SessionLocal()
    try:
        user = create_user(
            session,
            email=email,
            password=password,
            role=Role.reception,
            full_name="Clinical Reliability User",
            is_active=active,
        )
        user_id = int(user.id)
    finally:
        session.close()
    if not active:
        return user_id, {}
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


def _clinical_audits(patient_id: int) -> list[AuditLog]:
    session = SessionLocal()
    try:
        return list(
            session.scalars(
                select(AuditLog)
                .where(
                    AuditLog.entity_type == "patient",
                    AuditLog.entity_id == str(patient_id),
                    AuditLog.action.like("clinical.%"),
                )
                .order_by(AuditLog.id)
            )
        )
    finally:
        session.close()


def _clinical_row_counts(patient_id: int) -> tuple[int, int, int]:
    session = SessionLocal()
    try:
        return (
            int(
                session.scalar(
                    select(func.count(ToothNote.id)).where(ToothNote.patient_id == patient_id)
                )
                or 0
            ),
            int(
                session.scalar(
                    select(func.count(Procedure.id)).where(Procedure.patient_id == patient_id)
                )
                or 0
            ),
            int(
                session.scalar(
                    select(func.count(TreatmentPlanItem.id)).where(
                        TreatmentPlanItem.patient_id == patient_id
                    )
                )
                or 0
            ),
        )
    finally:
        session.close()


def _create_active_appointment(api_client, headers, patient_id: int) -> int:
    del api_client, headers
    session = SessionLocal()
    try:
        actor = session.scalar(select(User).where(User.role == Role.superadmin))
        assert actor is not None
        appointment = Appointment(
            patient_id=patient_id,
            starts_at=datetime(2031, 6, 12, 9, 0, tzinfo=timezone.utc),
            ends_at=datetime(2031, 6, 12, 9, 30, tzinfo=timezone.utc),
            status=AppointmentStatus.booked,
            location_type=AppointmentLocationType.clinic,
            location=f"Clinical-{uuid4().hex[:6]}",
            created_by_user_id=actor.id,
            updated_by_user_id=actor.id,
        )
        session.add(appointment)
        session.commit()
        session.refresh(appointment)
        return int(appointment.id)
    finally:
        session.close()


def test_clinical_capabilities_are_authoritative_and_denials_are_side_effect_free(
    api_client,
    auth_headers,
):
    patient_id = _create_patient(api_client, auth_headers, uuid4().hex[:8])
    user_id, user_headers = _create_user_headers(api_client)
    _set_capabilities(user_id, [])
    baseline = _clinical_row_counts(patient_id)

    assert (
        api_client.get(f"/patients/{patient_id}/clinical/summary", headers=user_headers).status_code
        == 403
    )
    assert (
        api_client.get(
            f"/patients/{patient_id}/tooth-history",
            params={"tooth": "UR1"},
            headers=user_headers,
        ).status_code
        == 403
    )
    denied_writes = [
        api_client.post(
            f"/patients/{patient_id}/clinical/bpe",
            headers=user_headers,
            json={"scores": ["0", "1", "2", "3", "4", "*"]},
        ),
        api_client.post(
            f"/patients/{patient_id}/tooth-notes",
            headers=user_headers,
            json={"tooth": "UR1", "surface": "I", "note": "denied"},
        ),
        api_client.post(
            f"/patients/{patient_id}/procedures",
            headers=user_headers,
            json={"tooth": "UR1", "surface": "I", "procedure_code": "DENY", "description": "denied"},
        ),
        api_client.post(
            f"/patients/{patient_id}/treatment-plan",
            headers=user_headers,
            json={"tooth": "UR1", "surface": "I", "procedure_code": "DENY", "description": "denied"},
        ),
    ]
    assert {response.status_code for response in denied_writes} == {403}
    assert _clinical_row_counts(patient_id) == baseline
    assert _clinical_audits(patient_id) == []

    _set_capabilities(user_id, ["clinical.view"])
    assert (
        api_client.get(f"/patients/{patient_id}/clinical/summary", headers=user_headers).status_code
        == 200
    )
    assert (
        api_client.get(
            f"/patients/{patient_id}/tooth-history",
            params={"tooth": "UR1"},
            headers=user_headers,
        ).status_code
        == 200
    )
    assert denied_writes[0].status_code == 403
    denied = api_client.post(
        f"/patients/{patient_id}/tooth-notes",
        headers=user_headers,
        json={"tooth": "UR1", "surface": "I", "note": "still denied"},
    )
    assert denied.status_code == 403
    assert _clinical_row_counts(patient_id) == baseline
    assert _clinical_audits(patient_id) == []

    _set_capabilities(user_id, ["clinical.view", "clinical.write"])
    allowed = api_client.post(
        f"/patients/{patient_id}/tooth-notes",
        headers=user_headers,
        json={"tooth": "ur1", "surface": "i", "note": "  permitted  "},
    )
    assert allowed.status_code == 201, allowed.text
    assert allowed.json()["tooth"] == "UR1"
    assert allowed.json()["surface"] == "I"
    assert allowed.json()["note"] == "permitted"

    disabled_user_id, disabled_headers = _create_user_headers(api_client)
    session = SessionLocal()
    try:
        disabled_user = session.get(User, disabled_user_id)
        assert disabled_user is not None
        disabled_user.is_active = False
        session.add(disabled_user)
        session.commit()
    finally:
        session.close()
    assert (
        api_client.get(
            f"/patients/{patient_id}/clinical/summary", headers=disabled_headers
        ).status_code
        == 401
    )
    assert (
        api_client.post(
            f"/patients/{patient_id}/clinical/bpe",
            headers=disabled_headers,
            json={"scores": ["0", "0", "0", "0", "0", "0"]},
        ).status_code
        == 401
    )


def test_clinical_validation_ownership_and_archived_patient_guards_are_atomic(
    api_client,
    auth_headers,
):
    patient_id = _create_patient(api_client, auth_headers, uuid4().hex[:8])
    other_patient_id = _create_patient(api_client, auth_headers, uuid4().hex[:8])
    other_appointment_id = _create_active_appointment(
        api_client, auth_headers, other_patient_id
    )
    appointment_id = _create_active_appointment(api_client, auth_headers, patient_id)
    baseline = _clinical_row_counts(patient_id)

    invalid_notes = [
        {"tooth": "11", "note": "invalid tooth"},
        {"tooth": "UR1", "surface": "O", "note": "invalid anterior surface"},
        {"tooth": "UR4", "surface": "I", "note": "invalid posterior surface"},
        {"tooth": "UR1", "surface": "X", "note": "invalid surface"},
        {"tooth": "UR1", "surface": "I", "note": "   "},
        {"tooth": "UR1", "surface": "I", "note": "x" * 2_001},
    ]
    for payload in invalid_notes:
        response = api_client.post(
            f"/patients/{patient_id}/tooth-notes", headers=auth_headers, json=payload
        )
        assert response.status_code == 422, response.text

    invalid_procedures = [
        {"procedure_code": " ", "description": "description"},
        {"procedure_code": "CODE", "description": " "},
        {"procedure_code": "CODE", "description": "description", "fee_pence": -1},
        {
            "procedure_code": "CODE",
            "description": "description",
            "fee_pence": 100_000_001,
        },
        {
            "appointment_id": other_appointment_id,
            "procedure_code": "CODE",
            "description": "description",
        },
    ]
    for payload in invalid_procedures:
        response = api_client.post(
            f"/patients/{patient_id}/procedures", headers=auth_headers, json=payload
        )
        assert response.status_code in {400, 422}, response.text

    invalid_bpe = [
        ["0", "1"],
        ["0", "1", "2", "3", "4", "5"],
        ["0", "1", "2", "3", "4", "**"],
    ]
    for scores in invalid_bpe:
        response = api_client.post(
            f"/patients/{patient_id}/clinical/bpe",
            headers=auth_headers,
            json={"scores": scores},
        )
        assert response.status_code == 422, response.text

    session = SessionLocal()
    try:
        cancelled = session.get(Appointment, appointment_id)
        assert cancelled is not None
        cancelled.status = AppointmentStatus.cancelled
        session.add(cancelled)
        session.commit()
    finally:
        session.close()
    inactive = api_client.post(
        f"/patients/{patient_id}/procedures",
        headers=auth_headers,
        json={
            "appointment_id": appointment_id,
            "procedure_code": "CODE",
            "description": "description",
        },
    )
    assert inactive.status_code == 400, inactive.text
    assert _clinical_row_counts(patient_id) == baseline
    assert _clinical_audits(patient_id) == []

    archived = api_client.post(f"/patients/{patient_id}/archive", headers=auth_headers)
    assert archived.status_code == 200, archived.text
    assert (
        api_client.get(f"/patients/{patient_id}/clinical/summary", headers=auth_headers).status_code
        == 404
    )
    rejected = api_client.post(
        f"/patients/{patient_id}/tooth-notes",
        headers=auth_headers,
        json={"tooth": "UR1", "surface": "I", "note": "must not persist"},
    )
    assert rejected.status_code == 404
    assert _clinical_row_counts(patient_id) == baseline
    assert _clinical_audits(patient_id) == []


def test_clinical_mutations_are_audited_idempotent_and_refreshable(
    api_client,
    auth_headers,
):
    patient_id = _create_patient(api_client, auth_headers, uuid4().hex[:8])

    bpe_headers = {**auth_headers, "Request-Id": f"bpe-{uuid4().hex}"}
    bpe = api_client.post(
        f"/patients/{patient_id}/clinical/bpe",
        headers=bpe_headers,
        json={"scores": ["0", "1", "2", "3", "4*", "*"]},
    )
    assert bpe.status_code == 200, bpe.text
    duplicate_bpe = api_client.post(
        f"/patients/{patient_id}/clinical/bpe",
        headers=bpe_headers,
        json={"scores": ["4", "4", "4", "4", "4", "4"]},
    )
    assert duplicate_bpe.status_code == 200
    no_op_bpe = api_client.post(
        f"/patients/{patient_id}/clinical/bpe",
        headers=auth_headers,
        json={"scores": ["0", "1", "2", "3", "4*", "*"]},
    )
    assert no_op_bpe.status_code == 200

    note_headers = {**auth_headers, "Request-Id": f"note-{uuid4().hex}"}
    note_payload = {
        "tooth": "UL1",
        "surface": "I",
        "note": "sensitive synthetic tooth note",
    }
    note = api_client.post(
        f"/patients/{patient_id}/tooth-notes",
        headers=note_headers,
        json=note_payload,
    )
    assert note.status_code == 201, note.text
    duplicate_note = api_client.post(
        f"/patients/{patient_id}/tooth-notes",
        headers=note_headers,
        json={**note_payload, "note": "must not replace original"},
    )
    assert duplicate_note.status_code == 201
    assert duplicate_note.json()["id"] == note.json()["id"]

    procedure_headers = {**auth_headers, "Request-Id": f"procedure-{uuid4().hex}"}
    procedure = api_client.post(
        f"/patients/{patient_id}/procedures",
        headers=procedure_headers,
        json={
            "tooth": "UL4",
            "surface": "O",
            "procedure_code": "REST",
            "description": "sensitive synthetic completed procedure",
            "fee_pence": 12_500,
            "performed_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert procedure.status_code == 201, procedure.text
    duplicate_procedure = api_client.post(
        f"/patients/{patient_id}/procedures",
        headers=procedure_headers,
        json={
            "tooth": "UL5",
            "surface": "O",
            "procedure_code": "OTHER",
            "description": "must not create another procedure",
        },
    )
    assert duplicate_procedure.status_code == 201
    assert duplicate_procedure.json()["id"] == procedure.json()["id"]

    plan_headers = {**auth_headers, "Request-Id": f"plan-{uuid4().hex}"}
    plan = api_client.post(
        f"/patients/{patient_id}/treatment-plan",
        headers=plan_headers,
        json={
            "tooth": "LR4",
            "surface": "O",
            "procedure_code": "PLAN",
            "description": "sensitive synthetic planned treatment",
            "fee_pence": 22_000,
        },
    )
    assert plan.status_code == 201, plan.text
    duplicate_plan = api_client.post(
        f"/patients/{patient_id}/treatment-plan",
        headers=plan_headers,
        json={
            "tooth": "LR5",
            "surface": "O",
            "procedure_code": "OTHER",
            "description": "must not create another item",
        },
    )
    assert duplicate_plan.status_code == 201
    assert duplicate_plan.json()["id"] == plan.json()["id"]
    item_id = int(plan.json()["id"])

    updated = api_client.patch(
        f"/treatment-plan/{item_id}",
        headers={**auth_headers, "Request-Id": f"plan-update-{uuid4().hex}"},
        json={"description": "replacement sensitive plan text", "fee_pence": 23_000},
    )
    assert updated.status_code == 200, updated.text
    for required_field in ("procedure_code", "description", "status"):
        rejected_null = api_client.patch(
            f"/treatment-plan/{item_id}",
            headers=auth_headers,
            json={required_field: None},
        )
        assert rejected_null.status_code == 422, rejected_null.text
    no_op_audit_count = len(_clinical_audits(patient_id))
    unchanged_updated_at = updated.json()["updated_at"]
    no_op = api_client.patch(
        f"/treatment-plan/{item_id}",
        headers=auth_headers,
        json={"description": "replacement sensitive plan text", "fee_pence": 23_000},
    )
    assert no_op.status_code == 200, no_op.text
    assert no_op.json()["updated_at"] == unchanged_updated_at
    assert len(_clinical_audits(patient_id)) == no_op_audit_count

    accepted = api_client.patch(
        f"/treatment-plan/{item_id}", headers=auth_headers, json={"status": "accepted"}
    )
    assert accepted.status_code == 200, accepted.text
    accepted_audit_count = len(_clinical_audits(patient_id))
    repeated = api_client.patch(
        f"/treatment-plan/{item_id}", headers=auth_headers, json={"status": "accepted"}
    )
    assert repeated.status_code == 200
    assert len(_clinical_audits(patient_id)) == accepted_audit_count
    invalid_transition = api_client.patch(
        f"/treatment-plan/{item_id}", headers=auth_headers, json={"status": "proposed"}
    )
    assert invalid_transition.status_code == 409
    assert len(_clinical_audits(patient_id)) == accepted_audit_count

    summary = api_client.get(
        f"/patients/{patient_id}/clinical/summary", headers=auth_headers
    )
    history = api_client.get(
        f"/patients/{patient_id}/tooth-history",
        params={"tooth": "UL4"},
        headers=auth_headers,
    )
    assert summary.status_code == 200, summary.text
    assert history.status_code == 200, history.text
    assert any(item["id"] == procedure.json()["id"] for item in history.json()["procedures"])
    assert any(item["id"] == item_id for item in summary.json()["treatment_plan_items"])
    assert summary.json()["bpe_scores"] == ["0", "1", "2", "3", "4*", "*"]

    audits = _clinical_audits(patient_id)
    actions = [audit.action for audit in audits]
    assert actions == [
        "clinical.bpe.recorded",
        "clinical.tooth_note.created",
        "clinical.procedure.completed",
        "clinical.treatment_plan.item.created",
        "clinical.treatment_plan.item.updated",
        "clinical.treatment_plan.status.changed",
    ]
    assert all(audit.actor_user_id is not None and audit.actor_email for audit in audits)
    audit_payloads = " ".join(
        f"{audit.before_json!r} {audit.after_json!r}" for audit in audits
    )
    assert "sensitive synthetic tooth note" not in audit_payloads
    assert "sensitive synthetic completed procedure" not in audit_payloads
    assert "sensitive synthetic planned treatment" not in audit_payloads
    assert "replacement sensitive plan text" not in audit_payloads
    plan_update_audit = next(
        audit for audit in audits if audit.action == "clinical.treatment_plan.item.updated"
    )
    assert plan_update_audit.after_json["changed_fields"] == ["description", "fee_pence"]
    assert _clinical_row_counts(patient_id) == (1, 1, 1)


def test_revoked_clinical_capability_remains_revoked_after_startup(api_client):
    writer_user_id, writer_headers = _create_user_headers(api_client)
    viewer_user_id, viewer_headers = _create_user_headers(api_client)
    session = SessionLocal()
    try:
        writer_retained = [
            capability.code
            for capability in get_user_capabilities(session, writer_user_id)
            if capability.code != "clinical.write"
        ]
        viewer_retained = [
            capability.code
            for capability in get_user_capabilities(session, viewer_user_id)
            if capability.code != "clinical.view"
        ]
        replace_user_capabilities(session, writer_user_id, writer_retained)
        replace_user_capabilities(session, viewer_user_id, viewer_retained)
    finally:
        session.close()

    from app.main import startup

    startup()

    session = SessionLocal()
    try:
        writer_restarted_codes = {
            capability.code
            for capability in get_user_capabilities(session, writer_user_id)
        }
        viewer_restarted_codes = {
            capability.code
            for capability in get_user_capabilities(session, viewer_user_id)
        }
    finally:
        session.close()
    assert "clinical.view" in writer_restarted_codes
    assert "clinical.write" not in writer_restarted_codes
    assert "clinical.view" not in viewer_restarted_codes
    assert "clinical.write" in viewer_restarted_codes

    denied_write = api_client.post(
        "/patients/2000000000/tooth-notes",
        headers=writer_headers,
        json={"tooth": "UR1", "surface": "I", "note": "denied before lookup"},
    )
    denied_view = api_client.get(
        "/patients/2000000000/clinical/summary",
        headers=viewer_headers,
    )
    assert denied_write.status_code == 403
    assert denied_view.status_code == 403
