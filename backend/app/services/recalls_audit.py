from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy.orm import Session
from starlette.requests import Request

from app.models.user import User
from app.services.audit import log_event


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
