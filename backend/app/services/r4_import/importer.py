from __future__ import annotations

from dataclasses import asdict, dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.appointment import Appointment, AppointmentLocationType, AppointmentStatus
from app.models.patient import Patient
from app.services.r4_import.source import R4Source
from app.services.r4_import.types import R4Appointment, R4Patient


@dataclass
class ImportStats:
    patients_created: int = 0
    patients_updated: int = 0
    patients_skipped: int = 0
    appts_created: int = 0
    appts_updated: int = 0
    appts_skipped: int = 0
    appts_unmapped_patient_refs: int = 0
    appts_patient_conflicts: int = 0

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


def import_r4(
    session: Session,
    source: R4Source,
    actor_id: int,
    legacy_source: str = "r4",
) -> ImportStats:
    stats = ImportStats()
    patients_by_code: dict[int, Patient] = {}

    for patient in source.list_patients():
        row = _upsert_patient(session, patient, actor_id, legacy_source, stats)
        patients_by_code[patient.patient_code] = row

    session.flush()

    for appt in source.list_appts():
        _upsert_appt(session, appt, actor_id, legacy_source, patients_by_code, stats)

    return stats


def _upsert_patient(
    session: Session,
    patient: R4Patient,
    actor_id: int,
    legacy_source: str,
    stats: ImportStats,
) -> Patient:
    legacy_id = str(patient.patient_code)
    existing = session.scalar(
        select(Patient).where(
            Patient.legacy_source == legacy_source,
            Patient.legacy_id == legacy_id,
        )
    )
    if existing:
        updated = _apply_updates(
            existing,
            {
                "first_name": patient.first_name,
                "last_name": patient.last_name,
                "date_of_birth": patient.date_of_birth,
                "updated_by_user_id": actor_id,
            },
        )
        if updated:
            stats.patients_updated += 1
        else:
            stats.patients_skipped += 1
        return existing

    row = Patient(
        legacy_source=legacy_source,
        legacy_id=legacy_id,
        first_name=patient.first_name,
        last_name=patient.last_name,
        date_of_birth=patient.date_of_birth,
        created_by_user_id=actor_id,
        updated_by_user_id=actor_id,
    )
    session.add(row)
    stats.patients_created += 1
    return row


def _upsert_appt(
    session: Session,
    appt: R4Appointment,
    actor_id: int,
    legacy_source: str,
    patients_by_code: dict[int, Patient],
    stats: ImportStats,
) -> Appointment:
    legacy_id = appt.appointment_id or _build_appointment_legacy_id(appt)
    existing = session.scalar(
        select(Appointment).where(
            Appointment.legacy_source == legacy_source,
            Appointment.legacy_id == legacy_id,
        )
    )
    patient = None
    if appt.patient_code is not None:
        patient = patients_by_code.get(appt.patient_code)
        if patient is None:
            patient = session.scalar(
                select(Patient).where(
                    Patient.legacy_source == legacy_source,
                    Patient.legacy_id == str(appt.patient_code),
                )
            )
    mapped_patient_id = patient.id if patient else None

    status = AppointmentStatus.booked
    if appt.status:
        status = AppointmentStatus(appt.status)
    location_type = AppointmentLocationType.clinic
    if appt.location_type:
        location_type = AppointmentLocationType(appt.location_type)
    is_domiciliary = location_type == AppointmentLocationType.visit

    updates = {
        "starts_at": appt.starts_at,
        "ends_at": appt.ends_at,
        "status": status,
        "appointment_type": appt.appointment_type,
        "clinician": appt.clinician,
        "location": appt.location,
        "location_type": location_type,
        "is_domiciliary": is_domiciliary,
        "legacy_patient_code": str(appt.patient_code) if appt.patient_code is not None else None,
        "updated_by_user_id": actor_id,
    }

    if existing:
        if existing.patient_id is None:
            if mapped_patient_id is None:
                stats.appts_unmapped_patient_refs += 1
            else:
                updates["patient_id"] = mapped_patient_id
        elif mapped_patient_id is not None and mapped_patient_id != existing.patient_id:
            stats.appts_patient_conflicts += 1
        updated = _apply_updates(existing, updates)
        if updated:
            stats.appts_updated += 1
        else:
            stats.appts_skipped += 1
        return existing

    if mapped_patient_id is None:
        stats.appts_unmapped_patient_refs += 1
    updates["patient_id"] = mapped_patient_id
    row = Appointment(
        legacy_source=legacy_source,
        legacy_id=legacy_id,
        created_by_user_id=actor_id,
        **updates,
    )
    session.add(row)
    stats.appts_created += 1
    return row


def _build_appointment_legacy_id(appt: R4Appointment) -> str:
    patient_code = str(appt.patient_code) if appt.patient_code is not None else "unknown"
    clinician = (appt.clinician or "unknown").strip()
    location = (appt.location or "unknown").strip()
    return f"{patient_code}:{appt.starts_at.isoformat()}:{clinician}:{location}"


def _apply_updates(model, updates: dict) -> bool:
    changed = False
    for field, value in updates.items():
        if getattr(model, field) != value:
            setattr(model, field, value)
            changed = True
    return changed
