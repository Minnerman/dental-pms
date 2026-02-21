from __future__ import annotations

from datetime import date
from typing import Iterable

from app.services.r4_charting.completed_treatment_findings_import import (
    CompletedTreatmentFindingDropReport,
    filter_completed_treatment_findings,
)
from app.services.r4_import.types import R4CompletedTreatmentFinding as CompletedTreatmentFindingRow


def apply_drop_reason_skeleton(
    rows: Iterable[CompletedTreatmentFindingRow],
    *,
    date_from: date,
    date_to: date,
) -> tuple[list[CompletedTreatmentFindingRow], CompletedTreatmentFindingDropReport]:
    """Filter candidate rows and produce guard-first drop-reason counters.

    This is a Stage 163F scouting skeleton only; filters can tighten during import stage.
    """

    accepted, report = filter_completed_treatment_findings(
        rows,
        date_from=date_from,
        date_to=date_to,
    )
    return accepted, report
