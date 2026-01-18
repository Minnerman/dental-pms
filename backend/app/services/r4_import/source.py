from __future__ import annotations

from typing import Protocol

from app.services.r4_import.types import R4Appointment, R4Patient


class R4Source(Protocol):
    def list_patients(self) -> list[R4Patient]:
        raise NotImplementedError

    def list_appts(self) -> list[R4Appointment]:
        raise NotImplementedError
