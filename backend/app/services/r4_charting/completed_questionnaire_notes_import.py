from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import hashlib
from typing import Iterable

from app.services.r4_charting.canonical_types import CanonicalRecordInput
from app.services.r4_import.types import R4CompletedQuestionnaireNote

COMPLETED_QUESTIONNAIRE_NOTES_DOMAIN = "completed_questionnaire_note"
COMPLETED_QUESTIONNAIRE_NOTES_SOURCE = "dbo.CompletedQuestionnaire"


@dataclass
class CompletedQuestionnaireNoteDropReport:
    missing_patient_code: int = 0
    missing_date: int = 0
    out_of_window: int = 0
    blank_note: int = 0
    duplicate_key: int = 0
    accepted_nonblank_note: int = 0
    accepted_blank_note: int = 0
    included: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "missing_patient_code": self.missing_patient_code,
            "missing_date": self.missing_date,
            "out_of_window": self.out_of_window,
            "blank_note": self.blank_note,
            "duplicate_key": self.duplicate_key,
            "accepted_nonblank_note": self.accepted_nonblank_note,
            "accepted_blank_note": self.accepted_blank_note,
            "included": self.included,
        }


def completed_questionnaire_note_recorded_at(
    item: R4CompletedQuestionnaireNote,
) -> datetime | None:
    return item.completed_at


def completed_questionnaire_note_text(item: R4CompletedQuestionnaireNote) -> str | None:
    value = item.note
    if value is None:
        return None
    text = value.strip()
    return text or None


def completed_questionnaire_note_unique_key(item: R4CompletedQuestionnaireNote) -> str:
    if item.source_row_id is not None:
        return f"rowid:{int(item.source_row_id)}"
    recorded_at = completed_questionnaire_note_recorded_at(item)
    recorded_key = recorded_at.isoformat() if recorded_at is not None else ""
    digest = hashlib.sha1((completed_questionnaire_note_text(item) or "").encode("utf-8")).hexdigest()[:16]
    return f"{item.patient_code}:{recorded_key}:{digest}"


def completed_questionnaire_note_source_id(item: R4CompletedQuestionnaireNote) -> str:
    return completed_questionnaire_note_unique_key(item)


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


def filter_completed_questionnaire_notes(
    rows: Iterable[R4CompletedQuestionnaireNote],
    *,
    date_from: date | None,
    date_to: date | None,
) -> tuple[list[R4CompletedQuestionnaireNote], CompletedQuestionnaireNoteDropReport]:
    report = CompletedQuestionnaireNoteDropReport()
    accepted: list[R4CompletedQuestionnaireNote] = []
    seen_keys: set[str] = set()

    for item in rows:
        if item.patient_code is None:
            report.missing_patient_code += 1
            continue

        recorded_at = completed_questionnaire_note_recorded_at(item)
        if recorded_at is None:
            report.missing_date += 1
            continue
        if not _is_in_window(recorded_at, date_from=date_from, date_to=date_to):
            report.out_of_window += 1
            continue

        note_body = completed_questionnaire_note_text(item)
        if note_body is None:
            report.blank_note += 1
            report.accepted_blank_note += 1
            continue

        unique_key = completed_questionnaire_note_unique_key(item)
        if unique_key in seen_keys:
            report.duplicate_key += 1
            continue
        seen_keys.add(unique_key)

        report.accepted_nonblank_note += 1
        report.included += 1
        accepted.append(item)

    return accepted, report


def completed_questionnaire_note_payload(item: R4CompletedQuestionnaireNote) -> dict[str, object]:
    return {
        "patient_code": item.patient_code,
        "source_row_id": item.source_row_id,
        "completed_at": completed_questionnaire_note_recorded_at(item),
        "note": completed_questionnaire_note_text(item),
    }


def completed_questionnaire_note_to_canonical(
    item: R4CompletedQuestionnaireNote,
) -> CanonicalRecordInput:
    return CanonicalRecordInput(
        domain=COMPLETED_QUESTIONNAIRE_NOTES_DOMAIN,
        r4_source=COMPLETED_QUESTIONNAIRE_NOTES_SOURCE,
        r4_source_id=completed_questionnaire_note_source_id(item),
        legacy_patient_code=item.patient_code,
        recorded_at=completed_questionnaire_note_recorded_at(item),
        entered_at=None,
        tooth=None,
        surface=None,
        code_id=None,
        status=None,
        payload=completed_questionnaire_note_payload(item),
    )


def collect_completed_questionnaire_note_canonical_records(
    rows: Iterable[R4CompletedQuestionnaireNote],
    *,
    date_from: date | None,
    date_to: date | None,
) -> tuple[list[CanonicalRecordInput], CompletedQuestionnaireNoteDropReport]:
    accepted, report = filter_completed_questionnaire_notes(
        rows,
        date_from=date_from,
        date_to=date_to,
    )
    records = [completed_questionnaire_note_to_canonical(item) for item in accepted]
    return records, report
