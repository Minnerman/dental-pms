from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.r4_import.mapping_resolver import resolve_patient_id_from_r4_patient_code
from app.services.r4_import.patient_importer import import_r4_patients
from app.services.r4_import.source import R4Source


def mapping_exists(session: Session, legacy_source: str, patient_code: int) -> bool:
    return (
        resolve_patient_id_from_r4_patient_code(
            session, patient_code, legacy_source=legacy_source
        )
        is not None
    )


def ensure_mapping_for_patient(
    session: Session,
    source: R4Source,
    actor_id: int,
    patient_code: int,
    legacy_source: str = "r4",
) -> bool:
    if mapping_exists(session, legacy_source, patient_code):
        return True
    import_r4_patients(
        session,
        source,
        actor_id,
        legacy_source=legacy_source,
        patients_from=patient_code,
        patients_to=patient_code,
    )
    session.flush()
    return mapping_exists(session, legacy_source, patient_code)


def ensure_mappings_for_range(
    session: Session,
    source: R4Source,
    actor_id: int,
    patients_from: int | None,
    patients_to: int | None,
    legacy_source: str = "r4",
) -> None:
    if patients_from is None or patients_to is None:
        return
    import_r4_patients(
        session,
        source,
        actor_id,
        legacy_source=legacy_source,
        patients_from=patients_from,
        patients_to=patients_to,
    )
    session.flush()
