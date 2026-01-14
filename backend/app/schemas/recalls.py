from datetime import date, datetime

from pydantic import BaseModel

from app.models.patient_recall import PatientRecallKind, PatientRecallStatus
from app.models.patient_recall_communication import PatientRecallCommunicationChannel


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
    last_contacted_at: datetime | None = None
    last_contact_channel: PatientRecallCommunicationChannel | None = None
    last_contact_method: PatientRecallCommunicationChannel | None = None
    last_contact_note: str | None = None
    last_contact_outcome: str | None = None


class RecallContactCreate(BaseModel):
    method: PatientRecallCommunicationChannel
    outcome: str | None = None
    note: str | None = None
    contacted_at: datetime | None = None


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
