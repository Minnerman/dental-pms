from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

Availability = Literal["available", "forbidden"]


class DashboardPeriods(BaseModel):
    current_start: date
    current_end: date
    previous_start: date
    previous_end: date
    week_start: date
    week_end: date
    month_start: date
    month_end: date


class UnavailableMetric(BaseModel):
    availability: Literal["unavailable", "forbidden"]
    value: None = None
    reason: str


class AppointmentPeriod(BaseModel):
    appointments: int
    completed: int
    completion_rate: float | None


class DashboardAppointment(BaseModel):
    id: int
    patient_id: int | None
    patient_name: str | None
    starts_at: datetime
    ends_at: datetime
    status: str
    appointment_type: str | None
    clinician: str | None
    location_type: str


class DashboardAppointments(BaseModel):
    availability: Availability
    today_count: int | None
    in_clinic_count: int | None
    schedule_availability: Availability
    schedule: list[DashboardAppointment]
    schedule_has_more: bool
    unconfirmed_tomorrow: UnavailableMetric
    last_7_days: AppointmentPeriod | None
    previous_7_days: AppointmentPeriod | None


class OverdueInvoice(BaseModel):
    invoice_id: int
    invoice_number: str
    patient_id: int
    patient_name: str
    due_date: date
    balance_pence: int


class DashboardPayments(BaseModel):
    availability: Availability
    overdue_invoice_count: int | None
    overdue_balance_pence: int | None
    items_availability: Availability
    items: list[OverdueInvoice]
    items_has_more: bool
    last_7_days_invoiced_pence: int | None
    previous_7_days_invoiced_pence: int | None


class RecentPatient(BaseModel):
    id: int
    name: str
    phone: str | None
    created_at: datetime


class DashboardPatients(BaseModel):
    availability: Availability
    recent: list[RecentPatient]
    recent_has_more: bool
    basis: Literal["created_at"] = "created_at"


class DashboardRecalls(BaseModel):
    availability: Availability
    due_this_week: int | None
    overdue: int | None
    scheduled_this_month: int | None
    conversion_rate: UnavailableMetric


class HomeDashboard(BaseModel):
    generated_at: datetime
    date: date
    timezone: Literal["Europe/London"] = "Europe/London"
    currency: Literal["GBP"] = "GBP"
    periods: DashboardPeriods
    appointments: DashboardAppointments
    payments: DashboardPayments
    patients: DashboardPatients
    recalls: DashboardRecalls
    definitions: dict[str, str]
