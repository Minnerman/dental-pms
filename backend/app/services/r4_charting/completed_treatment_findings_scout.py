from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable

from app.services.tooth_state_classification import classify_tooth_state_type


@dataclass(frozen=True)
class CompletedTreatmentFindingRow:
    legacy_patient_code: int | None
    completed_at: date | datetime | None
    tooth: int | None
    code_id: int | None
    treatment_label: str | None
    ref_id: int | None = None
    tp_number: int | None = None
    tp_item: int | None = None


@dataclass
class CompletedTreatmentFindingDropReport:
    missing_patient_code: int = 0
    missing_tooth: int = 0
    missing_code_id: int = 0
    out_of_window: int = 0
    restorative_classified: int = 0
    duplicate_key: int = 0
    included: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "missing_patient_code": self.missing_patient_code,
            "missing_tooth": self.missing_tooth,
            "missing_code_id": self.missing_code_id,
            "out_of_window": self.out_of_window,
            "restorative_classified": self.restorative_classified,
            "duplicate_key": self.duplicate_key,
            "included": self.included,
        }


def _coerce_day(value: date | datetime | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    return value


def _build_row_key(row: CompletedTreatmentFindingRow) -> str:
    if row.ref_id is not None:
        return f"ref:{row.ref_id}"
    completed = _coerce_day(row.completed_at)
    completed_str = completed.isoformat() if completed else ""
    return (
        f"{row.legacy_patient_code}:{completed_str}:{row.tooth}:{row.code_id}:"
        f"{row.tp_number}:{row.tp_item}"
    )


def _is_restorative_label(label: str | None) -> bool:
    return classify_tooth_state_type(label) != "other"


def apply_drop_reason_skeleton(
    rows: Iterable[CompletedTreatmentFindingRow],
    *,
    date_from: date,
    date_to: date,
) -> tuple[list[CompletedTreatmentFindingRow], CompletedTreatmentFindingDropReport]:
    """Filter candidate rows and produce guard-first drop-reason counters.

    This is a Stage 163F scouting skeleton only; filters can tighten during import stage.
    """

    report = CompletedTreatmentFindingDropReport()
    accepted: list[CompletedTreatmentFindingRow] = []
    seen_keys: set[str] = set()

    for row in rows:
        completed_day = _coerce_day(row.completed_at)
        if completed_day is None or completed_day < date_from or completed_day >= date_to:
            report.out_of_window += 1
            continue
        if row.legacy_patient_code is None:
            report.missing_patient_code += 1
            continue
        if row.tooth is None:
            report.missing_tooth += 1
            continue
        if row.code_id is None:
            report.missing_code_id += 1
            continue
        if _is_restorative_label(row.treatment_label):
            # Stage 163C already imports restorative semantics; this domain scouts non-restorative findings.
            report.restorative_classified += 1
            continue

        unique_key = _build_row_key(row)
        if unique_key in seen_keys:
            report.duplicate_key += 1
            continue
        seen_keys.add(unique_key)

        report.included += 1
        accepted.append(row)

    return accepted, report
