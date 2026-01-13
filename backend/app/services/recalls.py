from __future__ import annotations

from datetime import date

from app.models.patient_recall import PatientRecall, PatientRecallStatus


def resolve_recall_status(
    recall: PatientRecall, *, today: date | None = None
) -> PatientRecallStatus:
    if recall.status in (
        PatientRecallStatus.completed,
        PatientRecallStatus.cancelled,
        PatientRecallStatus.due,
        PatientRecallStatus.overdue,
    ):
        return recall.status
    if not recall.due_date:
        return recall.status
    resolved_today = today or date.today()
    if recall.due_date < resolved_today:
        return PatientRecallStatus.overdue
    if recall.due_date <= resolved_today:
        return PatientRecallStatus.due
    return recall.status
