from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy.orm import Session
from starlette.requests import Request

from app.models.patient import Patient
from app.models.patient_recall import PatientRecall, PatientRecallStatus
from app.models.user import User
from app.services.audit import log_event


def _audit_value(value: Any) -> Any:
    if hasattr(value, "value"):
        return value.value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def build_recall_snapshot(recall: PatientRecall) -> dict[str, Any]:
    return {
        "recall_id": recall.id,
        "patient_id": recall.patient_id,
        "kind": recall.kind.value,
        "due_date": recall.due_date.isoformat(),
        "status": recall.status.value,
        "notes_present": bool((recall.notes or "").strip()),
        "completed_at": recall.completed_at.isoformat() if recall.completed_at else None,
        "outcome": recall.outcome.value if recall.outcome else None,
        "linked_appointment_id": recall.linked_appointment_id,
    }


def build_patient_recall_settings_snapshot(patient: Patient) -> dict[str, Any]:
    return {
        "patient_id": patient.id,
        "interval_months": patient.recall_interval_months,
        "due_date": patient.recall_due_date.isoformat() if patient.recall_due_date else None,
        "status": patient.recall_status.value if patient.recall_status else None,
        "type": patient.recall_type,
        "notes_present": bool((patient.recall_notes or "").strip()),
        "last_contacted_at": (
            patient.recall_last_contacted_at.isoformat()
            if patient.recall_last_contacted_at
            else None
        ),
    }


def _recall_status_action(before: Any, after: Any) -> str:
    if after == PatientRecallStatus.completed.value:
        return "recall.completed"
    if after == PatientRecallStatus.cancelled.value:
        return "recall.cancelled"
    if before in {
        PatientRecallStatus.completed.value,
        PatientRecallStatus.cancelled.value,
    }:
        return "recall.reopened"
    return "recall.status_changed"


def log_recall_created(
    db: Session,
    *,
    user: User,
    recall: PatientRecall,
    request_id: str | None,
    ip_address: str | None,
) -> None:
    log_event(
        db,
        actor=user,
        action="recall.created",
        entity_type="patient",
        entity_id=str(recall.patient_id),
        after_data=build_recall_snapshot(recall),
        request_id=request_id,
        ip_address=ip_address,
    )


def log_recall_changes(
    db: Session,
    *,
    user: User,
    patient_id: int,
    before: dict[str, Any],
    after: dict[str, Any],
    notes_changed: bool | None = None,
    request_id: str | None,
    ip_address: str | None,
) -> list[str]:
    action_fields: list[tuple[str, tuple[str, ...]]] = []
    if before.get("status") != after.get("status"):
        action_fields.append(
            (
                _recall_status_action(before.get("status"), after.get("status")),
                ("status", "completed_at"),
            )
        )
    elif before.get("completed_at") != after.get("completed_at"):
        action_fields.append(
            ("recall.completion_time_changed", ("completed_at",))
        )
    if before.get("due_date") != after.get("due_date"):
        action_fields.append(("recall.due_date_changed", ("due_date",)))
    if before.get("kind") != after.get("kind"):
        action_fields.append(("recall.type_changed", ("kind",)))
    if notes_changed is True or (
        notes_changed is None
        and before.get("notes_present") != after.get("notes_present")
    ):
        action_fields.append(("recall.notes_changed", ("notes_present",)))
    if before.get("outcome") != after.get("outcome"):
        action_fields.append(("recall.outcome_changed", ("outcome",)))
    if before.get("linked_appointment_id") != after.get("linked_appointment_id"):
        action_fields.append(
            ("recall.appointment_link_changed", ("linked_appointment_id",))
        )

    recall_id = after.get("recall_id") or before.get("recall_id")
    actions: list[str] = []
    for action, fields in action_fields:
        before_data = {"recall_id": recall_id}
        after_data = {"recall_id": recall_id}
        for field in fields:
            before_data[field] = before.get(field)
            after_data[field] = after.get(field)
        log_event(
            db,
            actor=user,
            action=action,
            entity_type="patient",
            entity_id=str(patient_id),
            before_data=before_data,
            after_data=after_data,
            request_id=request_id,
            ip_address=ip_address,
        )
        actions.append(action)
    return actions


def log_patient_recall_settings_changes(
    db: Session,
    *,
    user: User,
    patient_id: int,
    before: dict[str, Any],
    after: dict[str, Any],
    notes_changed: bool | None = None,
    request_id: str | None,
    ip_address: str | None,
) -> list[str]:
    action_by_field = {
        "interval_months": "recall.interval_changed",
        "due_date": "recall.due_date_changed",
        "type": "recall.type_changed",
        "notes_present": "recall.notes_changed",
        "last_contacted_at": "recall.contact_changed",
    }
    actions: list[str] = []
    if before.get("status") != after.get("status"):
        action_by_field["status"] = "recall.status_changed"
    for field, action in action_by_field.items():
        if field == "notes_present" and notes_changed is not None:
            if not notes_changed:
                continue
        elif before.get(field) == after.get(field):
            continue
        log_event(
            db,
            actor=user,
            action=action,
            entity_type="patient",
            entity_id=str(patient_id),
            before_data={field: before.get(field)},
            after_data={field: after.get(field)},
            request_id=request_id,
            ip_address=ip_address,
        )
        actions.append(action)
    return actions


def log_recall_activity(
    db: Session,
    *,
    user: User,
    patient_id: int,
    recall_id: int,
    action: str,
    metadata: dict[str, Any],
    request_id: str | None,
    ip_address: str | None,
) -> None:
    safe_metadata = {
        key: _audit_value(value)
        for key, value in metadata.items()
    }
    log_event(
        db,
        actor=user,
        action=action,
        entity_type="patient",
        entity_id=str(patient_id),
        after_data={"recall_id": recall_id, **safe_metadata},
        request_id=request_id,
        ip_address=ip_address,
    )


def build_export_filters(
    *,
    start: date | None,
    end: date | None,
    status: str | None,
    recall_type: str | None,
    contact_state: str | None,
    last_contact: str | None,
    method: str | None,
    contacted: str | None,
    contacted_within_days: int | None,
    contact_channel: str | None,
) -> dict[str, Any]:
    return {
        "start": start.isoformat() if start else None,
        "end": end.isoformat() if end else None,
        "status": status,
        "type": recall_type,
        "contact_state": contact_state,
        "last_contact": last_contact,
        "method": method,
        "contacted": contacted,
        "contacted_within_days": contacted_within_days,
        "contact_channel": contact_channel,
    }


def log_recall_export(
    db: Session,
    *,
    user: User,
    request: Request,
    export_type: str,
    filters: dict[str, Any],
    page_only: bool,
    limit: int,
    offset: int,
    total: int,
    exported_rows: int,
    filename: str,
) -> None:
    action = {
        "csv": "recalls.export_csv",
        "letters_zip": "recalls.export_letters_zip",
    }.get(export_type, f"recalls.export_{export_type}")
    log_event(
        db,
        actor=user,
        action=action,
        entity_type="recall_export",
        entity_id=export_type,
        after_data={
            "export_type": export_type,
            "filters": filters,
            "page_only": page_only,
            "limit": limit,
            "offset": offset,
            "total": total,
            "exported_rows": exported_rows,
            "filename": filename,
        },
        request_id=request.headers.get("x-request-id"),
        ip_address=request.client.host if request.client else None,
    )
