from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import hashlib
from typing import Iterable

from app.services.r4_charting.canonical_types import CanonicalRecordInput
from app.services.r4_import.types import R4AppointmentNote

APPOINTMENT_NOTES_DOMAIN = "appointment_note"
APPOINTMENT_NOTES_SOURCE = "dbo.vwAppointmentDetails"


@dataclass
class AppointmentNoteDropReport:
    missing_patient_code: int = 0
    missing_appt_id: int = 0
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
            "missing_appt_id": self.missing_appt_id,
            "missing_date": self.missing_date,
            "out_of_window": self.out_of_window,
            "blank_note": self.blank_note,
            "duplicate_key": self.duplicate_key,
            "accepted_nonblank_note": self.accepted_nonblank_note,
            "accepted_blank_note": self.accepted_blank_note,
            "included": self.included,
        }


def appointment_note_recorded_at(item: R4AppointmentNote) -> datetime | None:
    return item.appointment_datetime


def appointment_note_text(item: R4AppointmentNote) -> str | None:
    value = item.note
    if value is None:
        return None
    text = value.strip()
    return text or None


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


def appointment_note_unique_key(item: R4AppointmentNote) -> str:
    if item.source_apptid is not None:
        return f"apptid:{int(item.source_apptid)}"
    recorded_at = appointment_note_recorded_at(item)
    recorded_key = recorded_at.isoformat() if recorded_at is not None else ""
    digest = hashlib.sha1((appointment_note_text(item) or "").encode("utf-8")).hexdigest()[:16]
    return f"{item.patient_code}:{recorded_key}:{digest}"


def appointment_note_source_id(item: R4AppointmentNote) -> str:
    return appointment_note_unique_key(item)


def filter_appointment_notes(
    rows: Iterable[R4AppointmentNote],
    *,
    date_from: date | None,
    date_to: date | None,
) -> tuple[list[R4AppointmentNote], AppointmentNoteDropReport]:
    report = AppointmentNoteDropReport()
    accepted: list[R4AppointmentNote] = []
    seen_keys: set[str] = set()

    for item in rows:
        if item.patient_code is None:
            report.missing_patient_code += 1
            continue

        if item.source_apptid is None or int(item.source_apptid) <= 0:
            report.missing_appt_id += 1
            continue

        recorded_at = appointment_note_recorded_at(item)
        if recorded_at is None:
            report.missing_date += 1
            continue
        if not _is_in_window(recorded_at, date_from=date_from, date_to=date_to):
            report.out_of_window += 1
            continue

        note_body = appointment_note_text(item)
        if note_body is None:
            report.blank_note += 1
            report.accepted_blank_note += 1
            continue

        unique_key = appointment_note_unique_key(item)
        if unique_key in seen_keys:
            report.duplicate_key += 1
            continue
        seen_keys.add(unique_key)

        report.accepted_nonblank_note += 1
        report.included += 1
        accepted.append(item)

    return accepted, report


def appointment_note_payload(item: R4AppointmentNote) -> dict[str, object]:
    return {
        "patient_code": item.patient_code,
        "source_apptid": item.source_apptid,
        "appointment_datetime": appointment_note_recorded_at(item),
        "note": item.note,
        "clinician_code": item.clinician_code,
        "clinic_code": item.clinic_code,
        "treatment_code": item.treatment_code,
        "appointment_type": item.appointment_type,
        "status": item.status,
        "cancelled": item.cancelled,
        "appt_flag": item.appt_flag,
    }


def appointment_note_to_canonical(item: R4AppointmentNote) -> CanonicalRecordInput:
    return CanonicalRecordInput(
        domain=APPOINTMENT_NOTES_DOMAIN,
        r4_source=APPOINTMENT_NOTES_SOURCE,
        r4_source_id=appointment_note_source_id(item),
        legacy_patient_code=item.patient_code,
        recorded_at=appointment_note_recorded_at(item),
        entered_at=None,
        tooth=None,
        surface=None,
        code_id=None,
        status=item.status,
        payload=appointment_note_payload(item),
    )


def collect_appointment_note_canonical_records(
    rows: Iterable[R4AppointmentNote],
    *,
    date_from: date | None,
    date_to: date | None,
) -> tuple[list[CanonicalRecordInput], AppointmentNoteDropReport]:
    accepted, report = filter_appointment_notes(
        rows,
        date_from=date_from,
        date_to=date_to,
    )
    records = [appointment_note_to_canonical(item) for item in accepted]
    return records, report

