from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.r4_manual_mapping import R4ManualMapping
from app.models.r4_patient_mapping import R4PatientMapping


logger = logging.getLogger(__name__)


def resolve_patient_id_from_r4_patient_code(
    session: Session,
    patient_code: int | None,
    legacy_source: str = "r4",
) -> int | None:
    if patient_code is None:
        return None

    manual_id = session.scalar(
        select(R4ManualMapping.target_patient_id).where(
            R4ManualMapping.legacy_source == legacy_source,
            R4ManualMapping.legacy_patient_code == patient_code,
        )
    )
    if manual_id is not None:
        logger.info(
            "R4 manual mapping used",
            extra={
                "patient_code": int(patient_code),
                "target_patient_id": int(manual_id),
            },
        )
        return int(manual_id)

    mapped_id = session.scalar(
        select(R4PatientMapping.patient_id).where(
            R4PatientMapping.legacy_source == legacy_source,
            R4PatientMapping.legacy_patient_code == patient_code,
        )
    )
    return int(mapped_id) if mapped_id is not None else None
