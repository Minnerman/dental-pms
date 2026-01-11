from __future__ import annotations

from datetime import date
import re

from app.models.patient import Patient
from app.services.pdf import CLINIC_ADDRESS_LINES, CLINIC_NAME, CLINIC_PHONE

PLACEHOLDER_PATTERN = re.compile(r"\{\{([^}]+)\}\}")


def _build_patient_address(patient: Patient) -> str:
    parts = [
        patient.address_line1,
        patient.address_line2,
        patient.city,
        patient.postcode,
    ]
    return ", ".join(part for part in parts if part)


def _build_practice_address() -> str:
    return ", ".join(part for part in CLINIC_ADDRESS_LINES if part)


def _practice_line(index: int) -> str:
    if index < len(CLINIC_ADDRESS_LINES):
        return CLINIC_ADDRESS_LINES[index]
    return ""


def _enum_value(value) -> str:
    if value is None:
        return ""
    return value.value if hasattr(value, "value") else str(value)


def _build_field_map(patient: Patient) -> dict[str, str]:
    full_name = " ".join(part for part in [patient.first_name, patient.last_name] if part)
    return {
        "patient.id": str(patient.id),
        "patient.first_name": patient.first_name or "",
        "patient.last_name": patient.last_name or "",
        "patient.full_name": full_name,
        "patient.dob": patient.date_of_birth.isoformat() if patient.date_of_birth else "",
        "patient.email": patient.email or "",
        "patient.phone": patient.phone or "",
        "patient.address": _build_patient_address(patient),
        "patient.address_line1": patient.address_line1 or "",
        "patient.address_line2": patient.address_line2 or "",
        "patient.city": patient.city or "",
        "patient.postcode": patient.postcode or "",
        "patient.nhs_number": patient.nhs_number or "",
        "patient.category": _enum_value(patient.patient_category),
        "patient.care_setting": _enum_value(patient.care_setting),
        "patient.denplan_member_no": patient.denplan_member_no or "",
        "patient.denplan_plan_name": patient.denplan_plan_name or "",
        "patient.recall_due_date": patient.recall_due_date.isoformat()
        if patient.recall_due_date
        else "",
        "patient.recall_status": _enum_value(patient.recall_status),
        "patient.recall_type": patient.recall_type or "",
        "recall.due_date": patient.recall_due_date.isoformat()
        if patient.recall_due_date
        else "",
        "recall.status": _enum_value(patient.recall_status),
        "recall.type": patient.recall_type or "",
        "practice.name": CLINIC_NAME,
        "practice.address": _build_practice_address(),
        "practice.address_line1": _practice_line(0),
        "practice.website": _practice_line(1),
        "practice.phone": CLINIC_PHONE,
        "today": date.today().isoformat(),
    }


def render_template_with_warnings(content: str, patient: Patient) -> tuple[str, list[str]]:
    mapping = _build_field_map(patient)
    unknown: set[str] = set()

    def replace(match: re.Match[str]) -> str:
        key = match.group(1).strip()
        value = mapping.get(key)
        if value is None:
            unknown.add(key)
            return match.group(0)
        return value

    rendered = PLACEHOLDER_PATTERN.sub(replace, content)
    return rendered, sorted(unknown)


def render_template(content: str, patient: Patient) -> str:
    rendered, _unknown = render_template_with_warnings(content, patient)
    return rendered
