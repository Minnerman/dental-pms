from __future__ import annotations

from datetime import date
from io import BytesIO
from textwrap import wrap

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from app.models.patient import Patient
from app.models.patient_recall import PatientRecall
from app.services.pdf import CLINIC_NAME, CLINIC_PHONE

CLINIC_ADDRESS = "7 Chapel Road, Worthing, BN11 1EG"
CLINIC_WEBSITE = "https://www.dental-worthing.co.uk"


def build_recall_letter_pdf(patient: Patient, recall: PatientRecall) -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    left = 20 * mm
    right = width - 20 * mm
    top = height - 20 * mm
    y = top

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(left, y, CLINIC_NAME)
    pdf.setFont("Helvetica", 10)
    y -= 6 * mm
    for line in _build_header_lines():
        pdf.drawString(left, y, line)
        y -= 4 * mm
    pdf.drawRightString(right, y + 4 * mm, f"Date: {date.today().isoformat()}")
    y -= 6 * mm

    pdf.setFont("Helvetica", 10)
    for line in _build_patient_lines(patient):
        pdf.drawString(left, y, line)
        y -= 4 * mm
    y -= 4 * mm

    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(left, y, "Recall Reminder")
    y -= 8 * mm

    pdf.setFont("Helvetica", 11)
    body_lines = _build_body_lines(recall)
    for line in _wrap_lines(body_lines, width=98):
        if y < 25 * mm:
            pdf.showPage()
            y = top
            pdf.setFont("Helvetica", 11)
        pdf.drawString(left, y, line)
        y -= 6 * mm

    _draw_footer(pdf, left)
    pdf.save()
    return buffer.getvalue()


def _build_header_lines() -> list[str]:
    phone = CLINIC_PHONE.replace("Tel: ", "").strip()
    phone_line = f"Telephone: {phone}" if phone else "Telephone: 01903 821822"
    return [
        CLINIC_ADDRESS,
        phone_line,
        f"Website: {CLINIC_WEBSITE}",
    ]


def _build_patient_lines(patient: Patient) -> list[str]:
    name_parts = [patient.title, patient.first_name, patient.last_name]
    name = " ".join(part for part in name_parts if part)
    lines = [name]
    for part in [patient.address_line1, patient.address_line2]:
        if part:
            lines.append(part)
    city_line = " ".join(part for part in [patient.city, patient.postcode] if part)
    if city_line:
        lines.append(city_line)
    return lines


def _build_body_lines(recall: PatientRecall) -> list[str]:
    due_date = recall.due_date.isoformat()
    kind_label = recall.kind.value.replace("_", " ").title()
    return [
        "Our records show you are due for a dental recall appointment "
        f"(Type: {kind_label}, Due: {due_date}).",
        "Please contact us to arrange an appointment at your convenience.",
        "If you have already booked, please disregard this letter.",
    ]


def _wrap_lines(lines: list[str], *, width: int) -> list[str]:
    wrapped: list[str] = []
    for line in lines:
        wrapped.extend(wrap(line, width=width) or [""])
    return wrapped


def _draw_footer(pdf: canvas.Canvas, left: float) -> None:
    phone = CLINIC_PHONE.replace("Tel: ", "").strip()
    phone_line = f"Telephone: {phone}" if phone else "Telephone: 01903 821822"
    pdf.setFont("Helvetica", 9)
    pdf.drawString(left, 12 * mm, f"{phone_line} · Website: {CLINIC_WEBSITE}")
