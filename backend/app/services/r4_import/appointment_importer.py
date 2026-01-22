from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.r4_appointment import R4Appointment
from app.services.r4_import.source import R4Source
from app.services.r4_import.types import R4AppointmentRecord


@dataclass
class R4AppointmentImportStats:
    appointments_created: int = 0
    appointments_updated: int = 0
    appointments_skipped: int = 0
    appointments_patient_null: int = 0
    appointments_min_start: datetime | None = None
    appointments_max_start: datetime | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "appointments_created": self.appointments_created,
            "appointments_updated": self.appointments_updated,
            "appointments_skipped": self.appointments_skipped,
            "appointments_patient_null": self.appointments_patient_null,
            "appointments_date_range": {
                "min": self._format_dt(self.appointments_min_start),
                "max": self._format_dt(self.appointments_max_start),
            },
        }

    @staticmethod
    def _format_dt(value: datetime | None) -> str | None:
        if value is None:
            return None
        return value.isoformat()


def import_r4_appointments(
    session: Session,
    source: R4Source,
    actor_id: int,
    legacy_source: str = "r4",
    date_from=None,
    date_to=None,
    limit: int | None = None,
) -> R4AppointmentImportStats:
    stats = R4AppointmentImportStats()
    for appt in source.stream_appointments(date_from=date_from, date_to=date_to, limit=limit):
        _track_stats(stats, appt)
        _upsert_appointment(session, appt, actor_id, legacy_source, stats)
    return stats


def _track_stats(stats: R4AppointmentImportStats, appt: R4AppointmentRecord) -> None:
    if appt.patient_code is None:
        stats.appointments_patient_null += 1
    if stats.appointments_min_start is None or appt.starts_at < stats.appointments_min_start:
        stats.appointments_min_start = appt.starts_at
    if stats.appointments_max_start is None or appt.starts_at > stats.appointments_max_start:
        stats.appointments_max_start = appt.starts_at


def _upsert_appointment(
    session: Session,
    appt: R4AppointmentRecord,
    actor_id: int,
    legacy_source: str,
    stats: R4AppointmentImportStats,
) -> None:
    existing = session.scalar(
        select(R4Appointment).where(
            R4Appointment.legacy_source == legacy_source,
            R4Appointment.legacy_appointment_id == appt.appointment_id,
        )
    )
    updates = {
        "legacy_appointment_id": appt.appointment_id,
        "patient_code": appt.patient_code,
        "starts_at": appt.starts_at,
        "ends_at": appt.ends_at,
        "duration_minutes": appt.duration_minutes,
        "clinician_code": appt.clinician_code,
        "status": _clean_text(appt.status),
        "cancelled": appt.cancelled,
        "clinic_code": appt.clinic_code,
        "treatment_code": appt.treatment_code,
        "appointment_type": _clean_text(appt.appointment_type),
        "notes": _clean_text(appt.notes),
        "appt_flag": appt.appt_flag,
        "updated_by_user_id": actor_id,
    }
    if existing:
        updated = _apply_updates(existing, updates)
        if updated:
            stats.appointments_updated += 1
        else:
            stats.appointments_skipped += 1
        return

    row = R4Appointment(
        legacy_source=legacy_source,
        created_by_user_id=actor_id,
        **updates,
    )
    session.add(row)
    stats.appointments_created += 1


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _apply_updates(model, updates: dict[str, object]) -> bool:
    changed = False
    for field, value in updates.items():
        if getattr(model, field) != value:
            setattr(model, field, value)
            changed = True
    return changed
