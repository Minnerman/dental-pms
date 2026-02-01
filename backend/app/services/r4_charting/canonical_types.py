from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class CanonicalImportStats:
    total: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0
    unmapped_patients: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "total": self.total,
            "created": self.created,
            "updated": self.updated,
            "skipped": self.skipped,
            "unmapped_patients": self.unmapped_patients,
        }


@dataclass
class CanonicalRecordInput:
    domain: str
    r4_source: str
    r4_source_id: str
    legacy_patient_code: int | None
    recorded_at: datetime | None
    entered_at: datetime | None
    tooth: int | None
    surface: int | None
    code_id: int | None
    status: str | None
    payload: dict | None
