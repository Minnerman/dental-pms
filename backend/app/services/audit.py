from __future__ import annotations

from typing import Any

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.user import User


def snapshot_model(obj: Any | None) -> dict | None:
    if obj is None:
        return None
    data: dict[str, Any] = {}
    mapper = inspect(obj).mapper
    for column in mapper.columns:
        key = column.key
        value = getattr(obj, key)
        if hasattr(value, "value"):
            value = value.value
        data[key] = value
    return data


def log_event(
    db: Session,
    *,
    actor: User | None,
    action: str,
    entity_type: str,
    entity_id: str,
    before_obj: Any | None = None,
    after_obj: Any | None = None,
    before_data: dict | None = None,
    after_data: dict | None = None,
    request_id: str | None = None,
    ip_address: str | None = None,
) -> AuditLog:
    entry = AuditLog(
        actor_user_id=actor.id if actor else None,
        actor_email=actor.email if actor else None,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        request_id=request_id,
        ip_address=ip_address,
        before_json=before_data if before_data is not None else snapshot_model(before_obj),
        after_json=after_data if after_data is not None else snapshot_model(after_obj),
    )
    db.add(entry)
    return entry
