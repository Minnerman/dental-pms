from __future__ import annotations

from datetime import date

from app.models.patient import Patient
from app.services.pdf import CLINIC_ADDRESS_LINES, CLINIC_NAME, CLINIC_PHONE


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


def render_template(content: str, patient: Patient) -> str:
    mapping = {
        "{{patient.first_name}}": patient.first_name or "",
        "{{patient.last_name}}": patient.last_name or "",
        "{{patient.dob}}": patient.date_of_birth.isoformat() if patient.date_of_birth else "",
        "{{patient.address}}": _build_patient_address(patient),
        "{{practice.name}}": CLINIC_NAME,
        "{{practice.address}}": _build_practice_address(),
        "{{practice.phone}}": CLINIC_PHONE,
        "{{today}}": date.today().isoformat(),
    }
    rendered = content
    for token, value in mapping.items():
        rendered = rendered.replace(token, value)
    return rendered
