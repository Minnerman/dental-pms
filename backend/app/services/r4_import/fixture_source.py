from __future__ import annotations

import json
from pathlib import Path

from app.services.r4_import.source import R4Source
from app.services.r4_import.types import R4Appointment, R4Patient


class FixtureSource(R4Source):
    def __init__(self, base_path: Path | None = None) -> None:
        if base_path is None:
            base_path = Path(__file__).resolve().parent / "fixtures"
        self.base_path = base_path

    def list_patients(self) -> list[R4Patient]:
        data = self._load_json("patients.json")
        return [R4Patient.model_validate(item) for item in data]

    def list_appts(self) -> list[R4Appointment]:
        data = self._load_json("appts.json")
        return [R4Appointment.model_validate(item) for item in data]

    def _load_json(self, filename: str) -> list[dict]:
        path = self.base_path / filename
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        if not isinstance(data, list):
            raise ValueError(f"{path} must contain a JSON list.")
        return data
