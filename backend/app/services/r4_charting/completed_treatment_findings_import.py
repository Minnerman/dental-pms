from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable

from app.services.r4_charting.canonical_types import CanonicalRecordInput
from app.services.r4_import.types import R4CompletedTreatmentFinding
from app.services.tooth_state_classification import classify_tooth_state_type

COMPLETED_TREATMENT_FINDINGS_DOMAIN = "completed_treatment_finding"
COMPLETED_TREATMENT_FINDINGS_SOURCE = "dbo.vwCompletedTreatmentTransactions"


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


def completed_treatment_finding_recorded_at(item: R4CompletedTreatmentFinding) -> datetime | None:
    return item.completed_date


def completed_treatment_finding_unique_key(item: R4CompletedTreatmentFinding) -> str:
    if item.ref_id is not None:
        return f"ref:{item.ref_id}"
    recorded_at = completed_treatment_finding_recorded_at(item)
    recorded_key = recorded_at.isoformat() if recorded_at is not None else ""
    return (
        f"{item.patient_code}:{recorded_key}:{item.tooth}:{item.code_id}:"
        f"{item.tp_number}:{item.tp_item}"
    )


def completed_treatment_finding_source_id(item: R4CompletedTreatmentFinding) -> str:
    return completed_treatment_finding_unique_key(item)


def _is_in_window(value: datetime | None, *, date_from: date | None, date_to: date | None) -> bool:
    if date_from is None and date_to is None:
        return True
    if value is None:
        return False
    day = value.date()
    if date_from is not None and day < date_from:
        return False
    if date_to is not None and day >= date_to:
        return False
    return True


def _is_restorative_like(label: str | None) -> bool:
    return classify_tooth_state_type(label) != "other"


def filter_completed_treatment_findings(
    rows: Iterable[R4CompletedTreatmentFinding],
    *,
    date_from: date | None,
    date_to: date | None,
) -> tuple[list[R4CompletedTreatmentFinding], CompletedTreatmentFindingDropReport]:
    report = CompletedTreatmentFindingDropReport()
    accepted: list[R4CompletedTreatmentFinding] = []
    seen_keys: set[str] = set()

    for item in rows:
        recorded_at = completed_treatment_finding_recorded_at(item)
        if not _is_in_window(recorded_at, date_from=date_from, date_to=date_to):
            report.out_of_window += 1
            continue
        if item.patient_code is None:
            report.missing_patient_code += 1
            continue
        # Keep scout semantics: tooth=0 is present-but-unspecified in this source, while NULL is missing.
        if item.tooth is None:
            report.missing_tooth += 1
            continue
        if item.code_id is None:
            report.missing_code_id += 1
            continue
        if _is_restorative_like(item.treatment_label):
            # Stage 163C already imports restorative semantics; this domain tracks non-restorative findings.
            report.restorative_classified += 1
            continue

        unique_key = completed_treatment_finding_unique_key(item)
        if unique_key in seen_keys:
            report.duplicate_key += 1
            continue
        seen_keys.add(unique_key)

        report.included += 1
        accepted.append(item)

    return accepted, report


def completed_treatment_finding_payload(item: R4CompletedTreatmentFinding) -> dict[str, object]:
    return {
        "patient_code": item.patient_code,
        "completed_date": completed_treatment_finding_recorded_at(item),
        "code_id": item.code_id,
        "tooth": item.tooth,
        "treatment_label": item.treatment_label,
        "ref_id": item.ref_id,
        "tp_number": item.tp_number,
        "tp_item": item.tp_item,
        "clinic_code": item.clinic_code,
        "provider_code": item.provider_code,
    }


def completed_treatment_finding_to_canonical(
    item: R4CompletedTreatmentFinding,
) -> CanonicalRecordInput:
    return CanonicalRecordInput(
        domain=COMPLETED_TREATMENT_FINDINGS_DOMAIN,
        r4_source=COMPLETED_TREATMENT_FINDINGS_SOURCE,
        r4_source_id=completed_treatment_finding_source_id(item),
        legacy_patient_code=item.patient_code,
        recorded_at=completed_treatment_finding_recorded_at(item),
        entered_at=None,
        tooth=item.tooth,
        surface=None,
        code_id=item.code_id,
        status="completed",
        payload=completed_treatment_finding_payload(item),
    )


def collect_completed_treatment_finding_canonical_records(
    rows: Iterable[R4CompletedTreatmentFinding],
    *,
    date_from: date | None,
    date_to: date | None,
) -> tuple[list[CanonicalRecordInput], CompletedTreatmentFindingDropReport]:
    accepted, report = filter_completed_treatment_findings(
        rows,
        date_from=date_from,
        date_to=date_to,
    )
    records = [completed_treatment_finding_to_canonical(item) for item in accepted]
    return records, report
