from datetime import date, datetime

from pydantic import BaseModel

from app.models.patient_recall import PatientRecallKind, PatientRecallStatus


class RecallDashboardRow(BaseModel):
    id: int
    patient_id: int
    first_name: str
    last_name: str
    recall_kind: PatientRecallKind
    due_date: date
    status: PatientRecallStatus
    notes: str | None = None
    completed_at: datetime | None = None


class RecallKpiRange(BaseModel):
    from_date: date
    to_date: date


class RecallKpiCounts(BaseModel):
    due: int
    overdue: int
    contacted: int
    booked: int
    declined: int


class RecallKpiRates(BaseModel):
    contacted_rate: float
    booked_rate: float


class RecallKpiOut(BaseModel):
    range: RecallKpiRange
    counts: RecallKpiCounts
    rates: RecallKpiRates
