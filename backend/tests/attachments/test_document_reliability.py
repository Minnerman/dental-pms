from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import func, select

from app.core.security import create_access_token
from app.core.settings import settings
from app.db.session import SessionLocal
from app.models.attachment import Attachment
from app.models.audit_log import AuditLog
from app.models.patient import Patient
from app.models.patient_document import PatientDocument
from app.models.user import Role
from app.routers import attachments as attachment_routes
from app.routers import patient_documents as document_routes
from app.services import capabilities as capability_service
from app.services import storage
from app.services.capabilities import get_user_capabilities, replace_user_capabilities
from app.services.users import create_user


def _create_patient(api_client, headers, label: str) -> int:
    response = api_client.post(
        "/patients",
        headers=headers,
        json={"first_name": "Document", "last_name": label},
    )
    assert response.status_code == 201
    return int(response.json()["id"])


def _create_template(api_client, headers, *, active: bool = True) -> int:
    response = api_client.post(
        "/document-templates",
        headers=headers,
        json={
            "name": f"Synthetic document template {uuid4().hex[:8]}",
            "kind": "letter",
            "content": "Synthetic document for {{patient.full_name}}",
            "is_active": active,
        },
    )
    assert response.status_code == 201
    return int(response.json()["id"])


def _create_user_headers(*, active: bool = True) -> tuple[int, dict[str, str]]:
    suffix = uuid4().hex[:10]
    email = f"document-reliability-{suffix}@example.com"
    session = SessionLocal()
    try:
        user = create_user(
            session,
            email=email,
            password="DocumentReliability123!",
            role=Role.reception,
            full_name="Document Reliability User",
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


def _count(model, *criteria) -> int:
    session = SessionLocal()
    try:
        return int(session.scalar(select(func.count(model.id)).where(*criteria)) or 0)
    finally:
        session.close()


def _audit_count(*, action: str, entity_id: int | None = None) -> int:
    criteria = [AuditLog.action == action]
    if entity_id is not None:
        criteria.append(AuditLog.entity_id == str(entity_id))
    return _count(AuditLog, *criteria)


def _audit_payloads(*actions: str) -> list[tuple[dict | None, dict | None]]:
    session = SessionLocal()
    try:
        entries = list(
            session.scalars(select(AuditLog).where(AuditLog.action.in_(actions)))
        )
        return [(entry.before_json, entry.after_json) for entry in entries]
    finally:
        session.close()


def _archive_patient(patient_id: int) -> None:
    session = SessionLocal()
    try:
        patient = session.get(Patient, patient_id)
        assert patient is not None
        patient.deleted_at = datetime.now(timezone.utc)
        session.add(patient)
        session.commit()
    finally:
        session.close()


def test_document_capabilities_are_authoritative_and_composable(
    api_client,
    auth_headers,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(storage, "ATTACHMENTS_DIR", tmp_path)
    patient_id = _create_patient(api_client, auth_headers, uuid4().hex[:8])
    template_id = _create_template(api_client, auth_headers)
    attachment = api_client.post(
        f"/patients/{patient_id}/attachments",
        headers=auth_headers,
        files={"file": ("synthetic.pdf", b"synthetic", "application/pdf")},
    )
    assert attachment.status_code == 201
    attachment_id = int(attachment.json()["id"])
    document = api_client.post(
        f"/patients/{patient_id}/documents",
        headers=auth_headers,
        json={"template_id": template_id, "title": "Synthetic capability document"},
    )
    assert document.status_code == 201
    document_id = int(document.json()["id"])

    user_id, headers = _create_user_headers()
    _set_capabilities(user_id, [])
    baseline_attachment_count = _count(Attachment, Attachment.patient_id == patient_id)
    baseline_document_count = _count(PatientDocument, PatientDocument.patient_id == patient_id)
    baseline_audit_count = _count(AuditLog, AuditLog.actor_user_id == user_id)
    denied = [
        api_client.get(f"/patients/{patient_id}/attachments", headers=headers),
        api_client.get(f"/attachments/{attachment_id}/download", headers=headers),
        api_client.get(f"/patients/{patient_id}/documents", headers=headers),
        api_client.get(f"/patient-documents/{document_id}", headers=headers),
        api_client.get("/document-templates", headers=headers),
        api_client.get(f"/document-templates/{template_id}", headers=headers),
        api_client.post(
            f"/patients/{patient_id}/attachments",
            headers=headers,
            files={"file": ("denied.pdf", b"synthetic", "application/pdf")},
        ),
        api_client.post(
            f"/patients/{patient_id}/documents",
            headers=headers,
            json={"template_id": template_id},
        ),
        api_client.post(f"/patient-documents/{document_id}/attach-pdf", headers=headers),
        api_client.delete(f"/attachments/{attachment_id}", headers=headers),
        api_client.delete(f"/patient-documents/{document_id}", headers=headers),
    ]
    assert {response.status_code for response in denied} == {403}
    assert _count(Attachment, Attachment.patient_id == patient_id) == baseline_attachment_count
    assert _count(PatientDocument, PatientDocument.patient_id == patient_id) == baseline_document_count
    assert _count(AuditLog, AuditLog.actor_user_id == user_id) == baseline_audit_count

    _set_capabilities(user_id, ["documents.upload", "documents.delete"])
    assert api_client.post(
        f"/patients/{patient_id}/documents",
        headers=headers,
        json={"template_id": template_id},
    ).status_code == 403
    assert api_client.delete(f"/attachments/{attachment_id}", headers=headers).status_code == 403

    _set_capabilities(user_id, ["documents.download"])
    assert api_client.get(f"/patients/{patient_id}/attachments", headers=headers).status_code == 200
    assert api_client.get(f"/patients/{patient_id}/documents", headers=headers).status_code == 200
    assert api_client.get(f"/patient-documents/{document_id}", headers=headers).status_code == 200
    assert api_client.get("/document-templates", headers=headers).status_code == 200
    assert api_client.get(f"/document-templates/{template_id}", headers=headers).status_code == 200
    assert api_client.post(
        f"/patients/{patient_id}/documents",
        headers=headers,
        json={"template_id": template_id},
    ).status_code == 403

    _set_capabilities(user_id, ["documents.download", "documents.upload"])
    assert api_client.post(
        f"/patients/{patient_id}/documents/preview",
        headers=headers,
        json={"template_id": template_id},
    ).status_code == 200
    created = api_client.post(
        f"/patients/{patient_id}/documents",
        headers=headers,
        json={"template_id": template_id, "title": "Synthetic permitted document"},
    )
    assert created.status_code == 201
    assert api_client.delete(f"/patient-documents/{created.json()['id']}", headers=headers).status_code == 403

    _set_capabilities(user_id, ["documents.download", "documents.delete"])
    assert api_client.delete(f"/attachments/{attachment_id}", headers=headers).status_code == 200
    assert api_client.delete(f"/patient-documents/{document_id}", headers=headers).status_code == 200


def test_archived_patient_blocks_nested_and_global_document_routes(
    api_client,
    auth_headers,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(storage, "ATTACHMENTS_DIR", tmp_path)
    patient_id = _create_patient(api_client, auth_headers, uuid4().hex[:8])
    template_id = _create_template(api_client, auth_headers)
    attachment = api_client.post(
        f"/patients/{patient_id}/attachments",
        headers=auth_headers,
        files={"file": ("archived.pdf", b"synthetic", "application/pdf")},
    )
    document = api_client.post(
        f"/patients/{patient_id}/documents",
        headers=auth_headers,
        json={"template_id": template_id, "title": "Synthetic archived document"},
    )
    assert attachment.status_code == 201 and document.status_code == 201
    attachment_id = int(attachment.json()["id"])
    document_id = int(document.json()["id"])
    baseline_audits = _count(
        AuditLog,
        AuditLog.entity_id.in_([str(attachment_id), str(document_id)]),
    )
    _archive_patient(patient_id)

    responses = [
        api_client.get(f"/patients/{patient_id}/attachments", headers=auth_headers),
        api_client.post(
            f"/patients/{patient_id}/attachments",
            headers=auth_headers,
            files={"file": ("blocked.pdf", b"synthetic", "application/pdf")},
        ),
        api_client.get(f"/attachments/{attachment_id}/download", headers=auth_headers),
        api_client.get(f"/attachments/{attachment_id}/preview", headers=auth_headers),
        api_client.delete(f"/attachments/{attachment_id}", headers=auth_headers),
        api_client.get(f"/patients/{patient_id}/documents", headers=auth_headers),
        api_client.post(
            f"/patients/{patient_id}/documents/preview",
            headers=auth_headers,
            json={"template_id": template_id},
        ),
        api_client.post(
            f"/patients/{patient_id}/documents",
            headers=auth_headers,
            json={"template_id": template_id},
        ),
        api_client.get(f"/patient-documents/{document_id}", headers=auth_headers),
        api_client.get(f"/patient-documents/{document_id}/download", headers=auth_headers),
        api_client.post(f"/patient-documents/{document_id}/attach-pdf", headers=auth_headers),
        api_client.delete(f"/patient-documents/{document_id}", headers=auth_headers),
    ]
    assert {response.status_code for response in responses} == {404}
    assert _count(
        AuditLog,
        AuditLog.entity_id.in_([str(attachment_id), str(document_id)]),
    ) == baseline_audits


def test_upload_validation_and_storage_compensation(
    api_client,
    auth_headers,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(storage, "ATTACHMENTS_DIR", tmp_path)
    patient_id = _create_patient(api_client, auth_headers, uuid4().hex[:8])
    invalid_uploads = [
        ("   ", b"synthetic", "application/pdf"),
        ("x" * 256, b"synthetic", "application/pdf"),
        ("empty.pdf", b"", "application/pdf"),
        ("invalid.pdf", b"synthetic", "invalid content type"),
    ]
    for upload in invalid_uploads:
        response = api_client.post(
            f"/patients/{patient_id}/attachments",
            headers=auth_headers,
            files={"file": upload},
        )
        assert response.status_code in {400, 422}
    assert _count(Attachment, Attachment.patient_id == patient_id) == 0
    assert list(tmp_path.iterdir()) == []

    original_limit = attachment_routes.MAX_ATTACHMENT_BYTES
    monkeypatch.setattr(attachment_routes, "MAX_ATTACHMENT_BYTES", 4)
    oversized = api_client.post(
        f"/patients/{patient_id}/attachments",
        headers=auth_headers,
        files={"file": ("oversized.pdf", b"12345", "application/pdf")},
    )
    assert oversized.status_code == 413
    assert list(tmp_path.iterdir()) == []
    monkeypatch.setattr(attachment_routes, "MAX_ATTACHMENT_BYTES", original_limit)

    original_log_event = attachment_routes.log_event

    def fail_audit(*args, **kwargs):
        raise RuntimeError("synthetic audit failure")

    monkeypatch.setattr(attachment_routes, "log_event", fail_audit)
    response = api_client.post(
        f"/patients/{patient_id}/attachments",
        headers=auth_headers,
        files={"file": ("compensated.pdf", b"synthetic", "application/pdf")},
    )
    assert response.status_code == 500
    assert _count(Attachment, Attachment.patient_id == patient_id) == 0
    assert list(tmp_path.iterdir()) == []
    monkeypatch.setattr(attachment_routes, "log_event", original_log_event)


def test_failed_attachment_delete_restores_file_and_database_row(
    api_client,
    auth_headers,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(storage, "ATTACHMENTS_DIR", tmp_path)
    patient_id = _create_patient(api_client, auth_headers, uuid4().hex[:8])
    created = api_client.post(
        f"/patients/{patient_id}/attachments",
        headers=auth_headers,
        files={"file": ("delete-compensation.pdf", b"synthetic", "application/pdf")},
    )
    assert created.status_code == 201
    attachment_id = int(created.json()["id"])
    session = SessionLocal()
    try:
        attachment = session.get(Attachment, attachment_id)
        assert attachment is not None
        storage_key = attachment.storage_key
    finally:
        session.close()

    def fail_audit(*args, **kwargs):
        raise RuntimeError("synthetic audit failure")

    monkeypatch.setattr(attachment_routes, "log_event", fail_audit)
    deleted = api_client.delete(f"/attachments/{attachment_id}", headers=auth_headers)
    assert deleted.status_code == 500
    assert _count(Attachment, Attachment.id == attachment_id) == 1
    assert storage.file_exists(storage_key)


def test_duplicate_requests_and_pdf_attachment_are_idempotent(
    api_client,
    auth_headers,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(storage, "ATTACHMENTS_DIR", tmp_path)
    patient_id = _create_patient(api_client, auth_headers, uuid4().hex[:8])
    template_id = _create_template(api_client, auth_headers)

    upload_headers = {**auth_headers, "Request-Id": f"upload-{uuid4().hex}"}
    first_upload = api_client.post(
        f"/patients/{patient_id}/attachments",
        headers=upload_headers,
        files={"file": ("idempotent.pdf", b"synthetic", "application/pdf")},
    )
    second_upload = api_client.post(
        f"/patients/{patient_id}/attachments",
        headers=upload_headers,
        files={"file": ("idempotent.pdf", b"synthetic", "application/pdf")},
    )
    assert first_upload.status_code == second_upload.status_code == 201
    assert first_upload.json()["id"] == second_upload.json()["id"]
    attachment_id = int(first_upload.json()["id"])
    assert _audit_count(action="attachment.uploaded", entity_id=attachment_id) == 1

    create_headers = {**auth_headers, "Request-Id": f"document-{uuid4().hex}"}
    payload = {"template_id": template_id, "title": "Synthetic idempotent document"}
    first_document = api_client.post(
        f"/patients/{patient_id}/documents",
        headers=create_headers,
        json=payload,
    )
    second_document = api_client.post(
        f"/patients/{patient_id}/documents",
        headers=create_headers,
        json=payload,
    )
    assert first_document.status_code == second_document.status_code == 201
    assert first_document.json()["id"] == second_document.json()["id"]
    document_id = int(first_document.json()["id"])
    assert _audit_count(action="patient_document.created", entity_id=document_id) == 1

    first_attach = api_client.post(
        f"/patient-documents/{document_id}/attach-pdf",
        headers=auth_headers,
    )
    second_attach = api_client.post(
        f"/patient-documents/{document_id}/attach-pdf",
        headers=auth_headers,
    )
    assert first_attach.status_code == second_attach.status_code == 200
    assert first_attach.json()["id"] == second_attach.json()["id"]
    generated_attachment_id = int(first_attach.json()["id"])
    assert _audit_count(action="attachment.uploaded", entity_id=generated_attachment_id) == 1
    assert _audit_count(action="patient_document.pdf_attached", entity_id=document_id) == 1
    assert "Synthetic document for" not in repr(
        _audit_payloads(
            "attachment.uploaded",
            "patient_document.created",
            "patient_document.pdf_attached",
        )
    )


def test_failed_generated_pdf_attach_cleans_storage_and_preserves_document(
    api_client,
    auth_headers,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(storage, "ATTACHMENTS_DIR", tmp_path)
    patient_id = _create_patient(api_client, auth_headers, uuid4().hex[:8])
    template_id = _create_template(api_client, auth_headers)
    created = api_client.post(
        f"/patients/{patient_id}/documents",
        headers=auth_headers,
        json={"template_id": template_id, "title": "Synthetic compensated PDF"},
    )
    assert created.status_code == 201
    document_id = int(created.json()["id"])

    def fail_audit(*args, **kwargs):
        raise RuntimeError("synthetic audit failure")

    monkeypatch.setattr(document_routes, "log_event", fail_audit)
    response = api_client.post(
        f"/patient-documents/{document_id}/attach-pdf",
        headers=auth_headers,
    )
    assert response.status_code == 500
    session = SessionLocal()
    try:
        document = session.get(PatientDocument, document_id)
        assert document is not None and document.attachment_id is None
    finally:
        session.close()
    assert _count(Attachment, Attachment.patient_id == patient_id) == 0
    assert list(tmp_path.iterdir()) == []


def test_missing_files_and_invalid_templates_fail_without_success_audit(
    api_client,
    auth_headers,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(storage, "ATTACHMENTS_DIR", tmp_path)
    patient_id = _create_patient(api_client, auth_headers, uuid4().hex[:8])
    inactive_template_id = _create_template(api_client, auth_headers, active=False)
    active_template_id = _create_template(api_client, auth_headers)
    assert api_client.post(
        f"/patients/{patient_id}/documents/preview",
        headers=auth_headers,
        json={"template_id": inactive_template_id},
    ).status_code == 404
    assert api_client.post(
        f"/patients/{patient_id}/documents",
        headers=auth_headers,
        json={"template_id": inactive_template_id},
    ).status_code == 404
    assert api_client.post(
        f"/patients/{patient_id}/documents",
        headers=auth_headers,
        json={"template_id": active_template_id, "title": "   "},
    ).status_code == 422
    assert api_client.post(
        f"/patients/{patient_id}/documents",
        headers=auth_headers,
        json={"template_id": active_template_id, "title": "x" * 201},
    ).status_code == 422
    assert _count(
        PatientDocument,
        PatientDocument.patient_id == patient_id,
        PatientDocument.template_id == inactive_template_id,
    ) == 0

    created = api_client.post(
        f"/patients/{patient_id}/attachments",
        headers=auth_headers,
        files={"file": ("missing.pdf", b"synthetic", "application/pdf")},
    )
    assert created.status_code == 201
    attachment_id = int(created.json()["id"])
    session = SessionLocal()
    try:
        attachment = session.get(Attachment, attachment_id)
        assert attachment is not None
        storage.delete_file(attachment.storage_key)
    finally:
        session.close()
    baseline_download_audits = _audit_count(
        action="attachment.downloaded",
        entity_id=attachment_id,
    )
    missing = api_client.get(f"/attachments/{attachment_id}/download", headers=auth_headers)
    assert missing.status_code == 404
    assert _audit_count(action="attachment.downloaded", entity_id=attachment_id) == baseline_download_audits


def test_disabled_user_cannot_read_document_metadata(api_client, auth_headers):
    patient_id = _create_patient(api_client, auth_headers, uuid4().hex[:8])
    user_id, headers = _create_user_headers(active=False)
    _set_capabilities(user_id, ["documents.download", "documents.upload", "documents.delete"])
    response = api_client.get(f"/patients/{patient_id}/documents", headers=headers)
    assert response.status_code == 401


def test_capability_startup_preserves_explicit_document_revocations():
    user_id, _headers = _create_user_headers()
    _set_capabilities(user_id, ["patients.view"])
    session = SessionLocal()
    try:
        capability_service.ensure_capabilities(session)
        effective = [item.code for item in get_user_capabilities(session, user_id)]
    finally:
        session.close()
    assert effective == ["patients.view"]
