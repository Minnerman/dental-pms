from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.patient import Patient
from app.services.r4_import.source import R4Source
from app.services.r4_import.types import R4Patient


@dataclass
class PatientImportStats:
    patients_created: int = 0
    patients_updated: int = 0
    patients_skipped: int = 0

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


def import_r4_patients(
    session: Session,
    source: R4Source,
    actor_id: int,
    legacy_source: str = "r4",
    patients_from: int | None = None,
    patients_to: int | None = None,
    limit: int | None = None,
) -> PatientImportStats:
    stats = PatientImportStats()
    for patient in source.stream_patients(
        patients_from=patients_from,
        patients_to=patients_to,
        limit=limit,
    ):
        _upsert_patient(session, patient, actor_id, legacy_source, stats)
    return stats


def _upsert_patient(
    session: Session,
    patient: R4Patient,
    actor_id: int,
    legacy_source: str,
    stats: PatientImportStats,
) -> Patient:
    legacy_id = str(patient.patient_code)
    existing = session.scalar(
        select(Patient).where(
            Patient.legacy_source == legacy_source,
            Patient.legacy_id == legacy_id,
        )
    )
    updates = {
        "first_name": _normalize_string(patient.first_name) or "",
        "last_name": _normalize_string(patient.last_name) or "",
        "date_of_birth": _normalize_date(patient.date_of_birth),
        "updated_by_user_id": actor_id,
    }
    if existing:
        updated = _apply_updates(existing, updates)
        if updated:
            stats.patients_updated += 1
        else:
            stats.patients_skipped += 1
        return existing

    row = Patient(
        legacy_source=legacy_source,
        legacy_id=legacy_id,
        created_by_user_id=actor_id,
        **updates,
    )
    session.add(row)
    stats.patients_created += 1
    return row


def _normalize_string(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.rstrip()
    return cleaned if cleaned else ""


def _normalize_date(value: date | datetime | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    return value


def _apply_updates(model, updates: dict) -> bool:
    changed = False
    for field, value in updates.items():
        if getattr(model, field) != value:
            setattr(model, field, value)
            changed = True
    return changed
