from __future__ import annotations

from datetime import date
from typing import Iterable, Protocol

from app.services.r4_import.types import R4Appointment, R4Patient


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
