from __future__ import annotations

from datetime import datetime

from sqlalchemy import Integer, cast, func, select
from sqlalchemy.orm import Session

from app.models.patient import Patient


def _format_dt(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def verify_patients_window(
    session: Session,
    patients_from: int | None = None,
    patients_to: int | None = None,
) -> dict[str, object]:
    code_expr = cast(Patient.legacy_id, Integer)
    conditions = [
        Patient.legacy_source == "r4",
        Patient.legacy_id.is_not(None),
        Patient.legacy_id.op("~")("^[0-9]+$"),
    ]
    if patients_from is not None:
        conditions.append(code_expr >= patients_from)
    if patients_to is not None:
        conditions.append(code_expr <= patients_to)

    count = session.scalar(
        select(func.count()).select_from(Patient).where(*conditions)
    )
    min_code, max_code = session.execute(
        select(func.min(code_expr), func.max(code_expr)).where(*conditions)
    ).one()
    last_created_at = session.scalar(
        select(func.max(Patient.created_at)).where(*conditions)
    )
    last_updated_at = session.scalar(
        select(func.max(Patient.updated_at)).where(*conditions)
    )

    return {
        "entity": "patients",
        "window": {
            "patients_from": patients_from,
            "patients_to": patients_to,
        },
        "postgres_count_in_window": int(count or 0),
        "min_patient_code": int(min_code) if min_code is not None else None,
        "max_patient_code": int(max_code) if max_code is not None else None,
        "last_created_at": _format_dt(last_created_at),
        "last_updated_at": _format_dt(last_updated_at),
    }
