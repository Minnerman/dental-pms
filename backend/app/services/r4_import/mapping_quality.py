from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.services.r4_import.types import R4Patient

_EMAIL_RE = re.compile(r"^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$")
_POSTCODE_RE = re.compile(r"^[A-Z]{1,2}\\d{1,2}[A-Z]?\\d[A-Z]{2}$")


def _normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _normalize_email(value: str | None) -> str | None:
    cleaned = _normalize_text(value)
    if not cleaned:
        return None
    return cleaned.lower()


def _normalize_phone(value: str | None) -> str | None:
    cleaned = _normalize_text(value)
    if not cleaned:
        return None
    digits = re.sub(r"\\D", "", cleaned)
    if not digits:
        return None
    if digits.startswith("44") and len(digits) == 12:
        digits = "0" + digits[2:]
    return digits


def _normalize_postcode(value: str | None) -> str | None:
    cleaned = _normalize_text(value)
    if not cleaned:
        return None
    compact = re.sub(r"\\s+", "", cleaned).upper()
    return compact or None


def _normalize_nhs_number(value: str | int | None) -> str | None:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    digits = re.sub(r"\\D", "", raw)
    if len(digits) != 10:
        return None
    return digits


def _is_valid_email(value: str) -> bool:
    return bool(_EMAIL_RE.match(value))


def _is_valid_phone(value: str) -> bool:
    return len(value) in {10, 11}


def _is_valid_postcode(value: str) -> bool:
    return bool(_POSTCODE_RE.match(value))


@dataclass
class PatientMappingQualityReportBuilder:
    sample_limit: int = 10
    patients_total: int = 0
    missing_fields: dict[str, int] = field(
        default_factory=lambda: {
            "surname": 0,
            "dob": 0,
            "postcode": 0,
            "phone": 0,
            "email": 0,
        }
    )
    invalid_fields: dict[str, int] = field(
        default_factory=lambda: {"email": 0, "phone": 0, "postcode": 0}
    )
    _duplicate_counts: dict[str, dict[str, int]] = field(
        default_factory=lambda: {"nhs_number": {}, "email": {}, "phone": {}}
    )

    def ingest(self, patient: R4Patient) -> None:
        self.patients_total += 1
        if not _normalize_text(patient.last_name):
            self.missing_fields["surname"] += 1
        if patient.date_of_birth is None:
            self.missing_fields["dob"] += 1

        postcode = _normalize_postcode(patient.postcode)
        if postcode is None:
            self.missing_fields["postcode"] += 1
        elif not _is_valid_postcode(postcode):
            self.invalid_fields["postcode"] += 1

        phone_raw = patient.phone or patient.mobile_no
        phone = _normalize_phone(phone_raw)
        if phone is None:
            self.missing_fields["phone"] += 1
        elif not _is_valid_phone(phone):
            self.invalid_fields["phone"] += 1
        else:
            self._track_duplicate("phone", phone)

        email = _normalize_email(patient.email)
        if email is None:
            self.missing_fields["email"] += 1
        elif not _is_valid_email(email):
            self.invalid_fields["email"] += 1
        else:
            self._track_duplicate("email", email)

        nhs_number = _normalize_nhs_number(patient.nhs_number)
        if nhs_number is not None:
            self._track_duplicate("nhs_number", nhs_number)

    def _track_duplicate(self, key: str, value: str) -> None:
        counts = self._duplicate_counts[key]
        counts[value] = counts.get(value, 0) + 1

    def finalize(self) -> dict[str, object]:
        duplicates: dict[str, dict[str, object]] = {}
        for key, counts in self._duplicate_counts.items():
            duplicate_records = sum(count - 1 for count in counts.values() if count > 1)
            values = sorted(value for value, count in counts.items() if count > 1)
            duplicates[key] = {
                "count": duplicate_records,
                "sample": values[: self.sample_limit],
            }
        return {
            "patients_total": self.patients_total,
            "missing_fields": dict(self.missing_fields),
            "invalid_fields": dict(self.invalid_fields),
            "duplicates": duplicates,
        }
