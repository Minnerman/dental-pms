from __future__ import annotations

from datetime import date
from io import BytesIO
from textwrap import wrap

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from app.models.patient import Patient
from app.services.pdf import CLINIC_ADDRESS_LINES, CLINIC_NAME, CLINIC_PHONE


def generate_patient_document_pdf(
    patient: Patient,
    title: str,
    rendered_text: str,
) -> bytes:
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
    for line in CLINIC_ADDRESS_LINES:
        pdf.drawString(left, y, line)
        y -= 4 * mm
    pdf.drawString(left, y, CLINIC_PHONE)
    y -= 8 * mm

    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(left, y, title)
    y -= 6 * mm

    pdf.setFont("Helvetica", 10)
    pdf.drawString(left, y, f"Patient: {patient.first_name} {patient.last_name}")
    y -= 5 * mm
    pdf.drawString(left, y, f"Generated: {date.today().isoformat()}")
    y -= 10 * mm

    pdf.setFont("Helvetica", 11)
    lines = []
    for raw_line in rendered_text.splitlines() or [""]:
        wrapped = wrap(raw_line, width=100, replace_whitespace=False) or [""]
        lines.extend(wrapped)

    line_height = 6 * mm
    page_num = 1
    for line in lines:
        if y < 20 * mm:
            _draw_footer(pdf, page_num)
            pdf.showPage()
            page_num += 1
            y = top
            pdf.setFont("Helvetica", 11)
        pdf.drawString(left, y, line)
        y -= line_height

    _draw_footer(pdf, page_num)
    pdf.save()
    return buffer.getvalue()


def _draw_footer(pdf: canvas.Canvas, page_num: int) -> None:
    pdf.setFont("Helvetica", 9)
    pdf.drawRightString(190 * mm, 10 * mm, f"Page {page_num}")
