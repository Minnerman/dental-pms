from __future__ import annotations

from datetime import date
from typing import Iterable, Protocol

from app.services.r4_import.types import (
    R4Appointment,
    R4Patient,
    R4Treatment,
    R4TreatmentPlan,
    R4TreatmentPlanItem,
    R4TreatmentPlanReview,
)


class R4Source(Protocol):
    def list_patients(self, limit: int | None = None) -> Iterable[R4Patient]:
        raise NotImplementedError

    def list_appts(
        self,
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int | None = None,
    ) -> Iterable[R4Appointment]:
        raise NotImplementedError

    def list_treatments(self, limit: int | None = None) -> Iterable[R4Treatment]:
        raise NotImplementedError

    def list_treatment_plans(
        self,
        patients_from: int | None = None,
        patients_to: int | None = None,
        tp_from: int | None = None,
        tp_to: int | None = None,
        limit: int | None = None,
    ) -> Iterable[R4TreatmentPlan]:
        raise NotImplementedError

    def list_treatment_plan_items(
        self,
        patients_from: int | None = None,
        patients_to: int | None = None,
        tp_from: int | None = None,
        tp_to: int | None = None,
        limit: int | None = None,
    ) -> Iterable[R4TreatmentPlanItem]:
        raise NotImplementedError

    def list_treatment_plan_reviews(
        self,
        patients_from: int | None = None,
        patients_to: int | None = None,
        tp_from: int | None = None,
        tp_to: int | None = None,
        limit: int | None = None,
    ) -> Iterable[R4TreatmentPlanReview]:
        raise NotImplementedError
