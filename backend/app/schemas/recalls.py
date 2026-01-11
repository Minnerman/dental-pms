from datetime import date

from pydantic import BaseModel


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
