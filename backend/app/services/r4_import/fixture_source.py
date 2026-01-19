from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from app.services.r4_import.source import R4Source
from app.services.r4_import.types import (
    R4Appointment,
    R4Patient,
    R4Treatment,
    R4TreatmentPlan,
    R4TreatmentPlanItem,
    R4TreatmentPlanReview,
)


class FixtureSource(R4Source):
    def __init__(self, base_path: Path | None = None) -> None:
        if base_path is None:
            base_path = Path(__file__).resolve().parent / "fixtures"
        self.base_path = base_path

    def list_patients(self, limit: int | None = None) -> list[R4Patient]:
        data = self._load_json("patients.json")
        items = [R4Patient.model_validate(item) for item in data]
        if limit is None:
            return items
        return items[:limit]

    def list_appts(
        self,
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int | None = None,
    ) -> list[R4Appointment]:
        data = self._load_json("appts.json")
        items = [R4Appointment.model_validate(item) for item in data]
        if date_from or date_to:
            filtered: list[R4Appointment] = []
            for item in items:
                starts_at = item.starts_at.date()
                if date_from and starts_at < date_from:
                    continue
                if date_to and starts_at > date_to:
                    continue
                filtered.append(item)
            items = filtered
        if limit is None:
            return items
        return items[:limit]

    def _load_json(self, filename: str) -> list[dict]:
        path = self.base_path / filename
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        if not isinstance(data, list):
            raise ValueError(f"{path} must contain a JSON list.")
        return data

    def list_treatments(self, limit: int | None = None) -> list[R4Treatment]:
        data = self._load_json("treatments.json")
        items = [R4Treatment.model_validate(item) for item in data]
        if limit is None:
            return items
        return items[:limit]

    def list_treatment_plans(
        self,
        patients_from: int | None = None,
        patients_to: int | None = None,
        tp_from: int | None = None,
        tp_to: int | None = None,
        limit: int | None = None,
    ) -> list[R4TreatmentPlan]:
        data = self._load_json("treatment_plans.json")
        items = [R4TreatmentPlan.model_validate(item) for item in data]
        items = self._filter_plans(items, patients_from, patients_to, tp_from, tp_to)
        if limit is None:
            return items
        return items[:limit]

    def list_treatment_plan_items(
        self,
        patients_from: int | None = None,
        patients_to: int | None = None,
        tp_from: int | None = None,
        tp_to: int | None = None,
        limit: int | None = None,
    ) -> list[R4TreatmentPlanItem]:
        data = self._load_json("treatment_plan_items.json")
        items = [R4TreatmentPlanItem.model_validate(item) for item in data]
        items = self._filter_plan_items(items, patients_from, patients_to, tp_from, tp_to)
        if limit is None:
            return items
        return items[:limit]

    def list_treatment_plan_reviews(
        self,
        patients_from: int | None = None,
        patients_to: int | None = None,
        tp_from: int | None = None,
        tp_to: int | None = None,
        limit: int | None = None,
    ) -> list[R4TreatmentPlanReview]:
        path = self.base_path / "treatment_plan_reviews.json"
        if not path.exists():
            return []
        data = self._load_json("treatment_plan_reviews.json")
        items = [R4TreatmentPlanReview.model_validate(item) for item in data]
        items = self._filter_plans(items, patients_from, patients_to, tp_from, tp_to)
        if limit is None:
            return items
        return items[:limit]

    @staticmethod
    def _filter_plans(items, patients_from, patients_to, tp_from, tp_to):
        if patients_from is None and patients_to is None and tp_from is None and tp_to is None:
            return items
        filtered = []
        for item in items:
            if patients_from is not None and item.patient_code < patients_from:
                continue
            if patients_to is not None and item.patient_code > patients_to:
                continue
            if tp_from is not None and item.tp_number < tp_from:
                continue
            if tp_to is not None and item.tp_number > tp_to:
                continue
            filtered.append(item)
        return filtered

    @staticmethod
    def _filter_plan_items(items, patients_from, patients_to, tp_from, tp_to):
        if patients_from is None and patients_to is None and tp_from is None and tp_to is None:
            return items
        filtered = []
        for item in items:
            if patients_from is not None and item.patient_code < patients_from:
                continue
            if patients_to is not None and item.patient_code > patients_to:
                continue
            if tp_from is not None and item.tp_number < tp_from:
                continue
            if tp_to is not None and item.tp_number > tp_to:
                continue
            filtered.append(item)
        return filtered
