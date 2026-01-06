from __future__ import annotations

from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle

from app.models.estimate import Estimate, EstimateFeeType
from app.models.patient import PatientCategory
from app.services.pdf import CLINIC_ADDRESS_LINES, CLINIC_NAME, CLINIC_PHONE

CATEGORY_LABELS = {
    PatientCategory.clinic_private: "Clinic (Private)",
    PatientCategory.domiciliary_private: "Domiciliary (Private)",
    PatientCategory.denplan: "Denplan",
}

DISCLAIMER_TEXT = {
    PatientCategory.domiciliary_private: (
        "Prices may vary depending on access, complexity and clinical findings."
    ),
    PatientCategory.denplan: (
        "Included items covered under Denplan; excluded treatments are charged privately as agreed."
    ),
}


def _format_gbp(pence: int) -> str:
    return f"£{pence / 100:.2f}"


def _draw_header(pdf: canvas.Canvas, title: str) -> None:
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
    pdf.setStrokeColor(colors.lightgrey)
    pdf.line(20 * mm, 258 * mm, 190 * mm, 258 * mm)


def _draw_patient_block(pdf: canvas.Canvas, estimate: Estimate) -> None:
    patient = estimate.patient
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(20 * mm, 245 * mm, "Patient")
    pdf.setFont("Helvetica", 10)
    pdf.drawString(20 * mm, 240 * mm, f"{patient.first_name} {patient.last_name}")
    if patient.date_of_birth:
        pdf.drawString(20 * mm, 235 * mm, f"DOB: {patient.date_of_birth.isoformat()}")
    address = ", ".join(
        part
        for part in [
            patient.address_line1,
            patient.address_line2,
            patient.city,
            patient.postcode,
        ]
        if part
    )
    if address:
        pdf.drawString(20 * mm, 230 * mm, address)


def _draw_estimate_meta(pdf: canvas.Canvas, estimate: Estimate) -> None:
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(120 * mm, 245 * mm, f"Estimate: EST-{estimate.id}")
    pdf.setFont("Helvetica", 10)
    issued_date = "—"
    if estimate.status.value != "DRAFT":
        issued_date = estimate.updated_at.date().isoformat()
    valid_until = estimate.valid_until.isoformat() if estimate.valid_until else "—"
    category_label = CATEGORY_LABELS.get(estimate.category_snapshot, "—")
    pdf.drawString(120 * mm, 240 * mm, f"Status: {estimate.status.value}")
    pdf.drawString(120 * mm, 235 * mm, f"Issued date: {issued_date}")
    pdf.drawString(120 * mm, 230 * mm, f"Valid until: {valid_until}")
    pdf.drawString(120 * mm, 225 * mm, f"Category: {category_label}")


def _draw_items_table(pdf: canvas.Canvas, estimate: Estimate) -> float:
    data = [["Description", "Qty", "Unit", "Line total"]]
    for item in estimate.items:
        qty = max(item.qty or 1, 1)
        if item.fee_type == EstimateFeeType.range:
            min_unit = item.min_unit_amount_pence or 0
            max_unit = item.max_unit_amount_pence or 0
            unit = f"{_format_gbp(min_unit)} - {_format_gbp(max_unit)}"
            total = f"{_format_gbp(min_unit * qty)} - {_format_gbp(max_unit * qty)}"
        else:
            unit_amount = item.unit_amount_pence or 0
            unit = _format_gbp(unit_amount)
            total = _format_gbp(unit_amount * qty)
        data.append([item.description, str(qty), unit, total])

    table = Table(data, colWidths=[95 * mm, 15 * mm, 35 * mm, 25 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f0f0")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
            ]
        )
    )
    table.wrapOn(pdf, 20 * mm, 150 * mm)
    table.drawOn(pdf, 20 * mm, 160 * mm)
    return 150 * mm


def _estimate_totals(estimate: Estimate) -> tuple[int, int, bool]:
    min_total = 0
    max_total = 0
    has_range = False
    for item in estimate.items:
        qty = max(item.qty or 1, 1)
        if item.fee_type == EstimateFeeType.range:
            has_range = True
            min_total += (item.min_unit_amount_pence or 0) * qty
            max_total += (item.max_unit_amount_pence or 0) * qty
        else:
            value = (item.unit_amount_pence or 0) * qty
            min_total += value
            max_total += value
    return min_total, max_total, has_range


def _draw_totals(pdf: canvas.Canvas, estimate: Estimate, y: float) -> None:
    min_total, max_total, has_range = _estimate_totals(estimate)
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawRightString(170 * mm, y, "Total")
    if has_range:
        total_text = f"{_format_gbp(min_total)} - {_format_gbp(max_total)}"
    else:
        total_text = _format_gbp(min_total)
    pdf.drawRightString(190 * mm, y, total_text)


def _draw_notes(pdf: canvas.Canvas, estimate: Estimate, y: float) -> float:
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(20 * mm, y, "Notes")
    pdf.setFont("Helvetica", 9)
    if estimate.notes:
        pdf.drawString(20 * mm, y - 10, estimate.notes)
        return y - 25
    pdf.drawString(20 * mm, y - 10, "No additional notes.")
    return y - 25


def _draw_disclaimer(pdf: canvas.Canvas, estimate: Estimate, y: float) -> None:
    disclaimer = DISCLAIMER_TEXT.get(estimate.category_snapshot)
    if not disclaimer:
        return
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(20 * mm, y, "Disclaimer")
    pdf.setFont("Helvetica", 9)
    pdf.drawString(20 * mm, y - 10, disclaimer)


def build_estimate_pdf(estimate: Estimate) -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    _draw_header(pdf, "Estimate")
    _draw_patient_block(pdf, estimate)
    _draw_estimate_meta(pdf, estimate)
    _draw_items_table(pdf, estimate)
    _draw_totals(pdf, estimate, 120 * mm)
    next_y = _draw_notes(pdf, estimate, 100 * mm)
    _draw_disclaimer(pdf, estimate, next_y)
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()
