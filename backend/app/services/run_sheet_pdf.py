from __future__ import annotations

from datetime import date
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from app.models.appointment import Appointment
from app.services.pdf import CLINIC_ADDRESS_LINES, CLINIC_NAME, CLINIC_PHONE


def _draw_header(pdf: canvas.Canvas, title: str, subtitle: str) -> None:
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(20 * mm, 280 * mm, CLINIC_NAME)
    pdf.setFont("Helvetica", 10)
    y = 274 * mm
    for line in CLINIC_ADDRESS_LINES:
        pdf.drawString(20 * mm, y, line)
        y -= 4 * mm
    pdf.drawString(20 * mm, y, CLINIC_PHONE)
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawRightString(190 * mm, 280 * mm, title)
    pdf.setFont("Helvetica", 10)
    pdf.drawRightString(190 * mm, 274 * mm, subtitle)
    pdf.setStrokeColor(colors.lightgrey)
    pdf.line(20 * mm, 260 * mm, 190 * mm, 260 * mm)


def _format_window(appt: Appointment) -> str:
    start_local = appt.starts_at.astimezone().strftime("%H:%M")
    end_local = appt.ends_at.astimezone().strftime("%H:%M")
    return f"{start_local}-{end_local}"


def _estimate_status(appt: Appointment) -> str:
    if not appt.estimates:
        return "N/A"
    latest = sorted(appt.estimates, key=lambda e: e.updated_at, reverse=True)[0]
    return latest.status.value


def build_run_sheet_pdf(appointments: list[Appointment], start: date, end: date) -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)

    subtitle = start.isoformat() if start == end else f"{start.isoformat()} to {end.isoformat()}"
    _draw_header(pdf, "Run sheet", subtitle)

    y = 250 * mm
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(20 * mm, y, "Visits")
    y -= 8 * mm

    for appt in appointments:
        if y < 40 * mm:
            pdf.showPage()
            _draw_header(pdf, "Run sheet", subtitle)
            y = 250 * mm

        patient = appt.patient
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(20 * mm, y, f"{_format_window(appt)}  {patient.first_name} {patient.last_name}")
        pdf.setFont("Helvetica", 9)
        y -= 6 * mm

        dob = patient.date_of_birth.isoformat() if patient.date_of_birth else "N/A"
        pdf.drawString(20 * mm, y, f"DOB: {dob}  Status: {appt.status.value}")
        y -= 5 * mm

        address = appt.location_text or appt.visit_address or patient.visit_address_text or "N/A"
        pdf.drawString(20 * mm, y, f"Address: {address}")
        y -= 5 * mm

        access = patient.access_notes or "N/A"
        pdf.drawString(20 * mm, y, f"Access: {access}")
        y -= 5 * mm

        contact_name = patient.primary_contact_name or "N/A"
        contact_phone = patient.primary_contact_phone or "N/A"
        pdf.drawString(20 * mm, y, f"Contact: {contact_name}  {contact_phone}")
        y -= 5 * mm

        estimate_status = _estimate_status(appt)
        pdf.drawString(20 * mm, y, f"Estimate: {estimate_status}")
        y -= 8 * mm

        pdf.setStrokeColor(colors.lightgrey)
        pdf.line(20 * mm, y, 190 * mm, y)
        y -= 6 * mm

    pdf.showPage()
    pdf.save()
    return buffer.getvalue()
