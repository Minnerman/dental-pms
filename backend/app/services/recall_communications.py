from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.patient_recall_communication import (
    PatientRecallCommunication,
    PatientRecallCommunicationChannel,
    PatientRecallCommunicationDirection,
    PatientRecallCommunicationStatus,
)


def log_recall_communication(
    db: Session,
    *,
    patient_id: int,
    recall_id: int,
    channel: PatientRecallCommunicationChannel,
    direction: PatientRecallCommunicationDirection,
    status: PatientRecallCommunicationStatus,
    notes: str | None,
    outcome: str | None = None,
    contacted_at: datetime | None = None,
    created_by_user_id: int | None,
    guard_seconds: int | None = 60,
) -> PatientRecallCommunication | None:
    if guard_seconds:
        threshold = datetime.now(timezone.utc) - timedelta(seconds=guard_seconds)
        recent = db.scalars(
            select(PatientRecallCommunication)
            .where(PatientRecallCommunication.patient_id == patient_id)
            .where(PatientRecallCommunication.recall_id == recall_id)
            .where(PatientRecallCommunication.channel == channel)
            .where(PatientRecallCommunication.notes == notes)
            .where(PatientRecallCommunication.created_at >= threshold)
            .limit(1)
        ).first()
        if recent:
            return None

    entry = PatientRecallCommunication(
        patient_id=patient_id,
        recall_id=recall_id,
        channel=channel,
        direction=direction,
        status=status,
        notes=notes,
        outcome=outcome,
        contacted_at=contacted_at or datetime.now(timezone.utc),
        created_by_user_id=created_by_user_id,
    )
    db.add(entry)
    return entry
