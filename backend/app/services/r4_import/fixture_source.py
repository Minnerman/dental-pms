from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from app.services.r4_import.source import R4Source
from app.services.r4_import.types import R4Appointment, R4Patient


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
