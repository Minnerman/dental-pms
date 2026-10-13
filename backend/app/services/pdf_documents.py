from __future__ import annotations

from datetime import date
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.pdfbase.pdfmetrics import stringWidth

from app.models.patient import Patient
from app.services.document_render import patient_document_name
from app.services.pdf import CLINIC_ADDRESS_LINES, CLINIC_NAME, CLINIC_PHONE


def generate_patient_document_pdf(
    patient: Patient,
    title: str,
    rendered_text: str,
    profile: dict[str, str | None] | None = None,
) -> bytes:
    data = profile or {}
    name = data.get("name") or CLINIC_NAME
    address_line1 = data.get("address_line1") or (
        CLINIC_ADDRESS_LINES[0] if CLINIC_ADDRESS_LINES else ""
    )
    address_line2 = data.get("address_line2") or (
        CLINIC_ADDRESS_LINES[1] if len(CLINIC_ADDRESS_LINES) > 1 else ""
    )
    city = data.get("city") or ""
    postcode = data.get("postcode") or ""
    phone = data.get("phone") or CLINIC_PHONE.replace("Tel: ", "")
    website = data.get("website") or (
        CLINIC_ADDRESS_LINES[1] if len(CLINIC_ADDRESS_LINES) > 1 else ""
    )
    email = data.get("email") or ""
    lines = []
    for entry in [address_line1, address_line2]:
        if entry and entry not in lines:
            lines.append(entry)
    city_line = " ".join(part for part in [city, postcode] if part)
    if city_line and city_line not in lines:
        lines.append(city_line)
    if website and website not in lines:
        lines.append(website)
    if email and email not in lines:
        lines.append(email)
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    left = 20 * mm
    right = width - 20 * mm
    top = height - 20 * mm
    y = top

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(left, y, name)
    pdf.setFont("Helvetica", 10)
    y -= 6 * mm
    for line in lines:
        pdf.drawString(left, y, line)
        y -= 4 * mm
    pdf.drawString(left, y, f"Tel: {phone}" if phone else CLINIC_PHONE)
    y -= 8 * mm

    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(left, y, title)
    y -= 6 * mm

    pdf.setFont("Helvetica", 10)
    pdf.drawString(left, y, f"Patient: {patient_document_name(patient)}")
    y -= 5 * mm
    pdf.drawString(left, y, f"Generated: {date.today().isoformat()}")
    y -= 10 * mm

    pdf.setFont("Helvetica", 11)
    lines = []
    for raw_line in rendered_text.splitlines() or [""]:
        wrapped = _wrap_pdf_line(raw_line, right - left)
        lines.extend(wrapped)

    line_height = 6 * mm
    page_num = 1
    for line in lines:
        if y < 20 * mm:
            _draw_footer(pdf, page_num)
            pdf.showPage()
            page_num += 1
            y = top
            pdf.setFont("Helvetica", 10)
            pdf.drawString(left, y, f"Patient: {patient_document_name(patient)} | ID: {patient.id}")
            y -= 8 * mm
            pdf.setFont("Helvetica", 11)
        pdf.drawString(left, y, line)
        y -= line_height

    _draw_footer(pdf, page_num)
    pdf.save()
    return buffer.getvalue()


def _wrap_pdf_line(text: str, width: float) -> list[str]:
    """Wrap by printed width, including long medicine names with no spaces."""
    remaining = text.expandtabs(4)
    lines = []
    while remaining:
        used = 0.0
        end = 0
        for character in remaining:
            advance = stringWidth(character, "Helvetica", 11)
            if used + advance > width:
                break
            used += advance
            end += 1
        if end == len(remaining):
            lines.append(remaining)
            break
        boundary = remaining.rfind(" ", 0, end + 1)
        cut = boundary if boundary > 0 else max(1, end)
        lines.append(remaining[:cut].rstrip())
        remaining = remaining[cut:].lstrip()
    return lines or [""]


def _draw_footer(pdf: canvas.Canvas, page_num: int) -> None:
    pdf.setFont("Helvetica", 9)
    pdf.drawRightString(190 * mm, 10 * mm, f"Page {page_num}")
