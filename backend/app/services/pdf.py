from __future__ import annotations

from io import BytesIO
from typing import Iterable

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle

from app.models.invoice import Invoice, Payment

CLINIC_NAME = "Clinic for Implant & Orthodontic Dentistry"
CLINIC_ADDRESS_LINES = [
    "7 Chapel Road, Worthing, West Sussex BN11 1EG",
    "dental-worthing.co.uk",
]
CLINIC_PHONE = "Tel: 01903 821822"


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


def _draw_patient_block(pdf: canvas.Canvas, invoice: Invoice) -> None:
    patient = invoice.patient
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(20 * mm, 245 * mm, "Billed to")
    pdf.setFont("Helvetica", 10)
    pdf.drawString(20 * mm, 240 * mm, f"{patient.first_name} {patient.last_name}")
    address = ", ".join(
        part for part in [patient.address_line1, patient.address_line2, patient.city, patient.postcode] if part
    )
    if address:
        pdf.drawString(20 * mm, 235 * mm, address)
    if patient.phone:
        pdf.drawString(20 * mm, 230 * mm, patient.phone)
    if patient.email:
        pdf.drawString(20 * mm, 225 * mm, patient.email)


def _draw_invoice_meta(pdf: canvas.Canvas, invoice: Invoice) -> None:
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(120 * mm, 245 * mm, f"Invoice: {invoice.invoice_number}")
    pdf.setFont("Helvetica", 10)
    issue_date = invoice.issue_date.isoformat() if invoice.issue_date else "—"
    due_date = invoice.due_date.isoformat() if invoice.due_date else "—"
    pdf.drawString(120 * mm, 240 * mm, f"Issue date: {issue_date}")
    pdf.drawString(120 * mm, 235 * mm, f"Due date: {due_date}")
    pdf.drawString(120 * mm, 230 * mm, f"Status: {invoice.status.value}")


def _draw_lines_table(pdf: canvas.Canvas, invoice: Invoice) -> float:
    data = [["Description", "Qty", "Unit", "Line total"]]
    for line in invoice.lines:
        data.append(
            [
                line.description,
                str(line.quantity),
                _format_gbp(line.unit_price_pence),
                _format_gbp(line.line_total_pence),
            ]
        )
    table = Table(data, colWidths=[95 * mm, 15 * mm, 25 * mm, 25 * mm])
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
    return 155 * mm


def _draw_totals(pdf: canvas.Canvas, invoice: Invoice, y: float) -> None:
    paid = invoice.paid_pence
    balance = invoice.balance_pence
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawRightString(170 * mm, y, "Subtotal")
    pdf.drawRightString(190 * mm, y, _format_gbp(invoice.subtotal_pence))
    pdf.drawRightString(170 * mm, y - 12, "Discount")
    pdf.drawRightString(190 * mm, y - 12, _format_gbp(invoice.discount_pence))
    pdf.drawRightString(170 * mm, y - 24, "Total")
    pdf.drawRightString(190 * mm, y - 24, _format_gbp(invoice.total_pence))
    pdf.setFont("Helvetica", 10)
    pdf.drawRightString(170 * mm, y - 40, "Paid")
    pdf.drawRightString(190 * mm, y - 40, _format_gbp(paid))
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawRightString(170 * mm, y - 56, "Balance")
    pdf.drawRightString(190 * mm, y - 56, _format_gbp(balance))


def _draw_payments(pdf: canvas.Canvas, payments: Iterable[Payment], y: float) -> None:
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(20 * mm, y, "Payments")
    pdf.setFont("Helvetica", 9)
    y -= 10
    if not payments:
        pdf.drawString(20 * mm, y, "No payments recorded.")
        return
    for payment in payments:
        paid_at = payment.paid_at.strftime("%Y-%m-%d")
        line = f"{paid_at} • {_format_gbp(payment.amount_pence)} • {payment.method.value}"
        if payment.reference:
            line = f"{line} • {payment.reference}"
        pdf.drawString(20 * mm, y, line)
        y -= 10


def _draw_void_watermark(pdf: canvas.Canvas) -> None:
    pdf.saveState()
    pdf.setFont("Helvetica-Bold", 60)
    pdf.setFillColor(colors.lightgrey)
    pdf.translate(105 * mm, 150 * mm)
    pdf.rotate(45)
    pdf.drawCentredString(0, 0, "VOID")
    pdf.restoreState()


def build_invoice_pdf(invoice: Invoice) -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    _draw_header(pdf, "Invoice")
    _draw_patient_block(pdf, invoice)
    _draw_invoice_meta(pdf, invoice)
    _draw_lines_table(pdf, invoice)
    _draw_totals(pdf, invoice, 120 * mm)
    _draw_payments(pdf, invoice.payments, 90 * mm)
    if invoice.status.value == "void":
        _draw_void_watermark(pdf)
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def build_payment_receipt(payment: Payment) -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    invoice = payment.invoice
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(20 * mm, 280 * mm, CLINIC_NAME)
    pdf.setFont("Helvetica", 10)
    y = 274 * mm
    for line in CLINIC_ADDRESS_LINES:
        pdf.drawString(20 * mm, y, line)
        y -= 4 * mm
    pdf.drawString(20 * mm, y, CLINIC_PHONE)
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawRightString(190 * mm, 280 * mm, "Payment receipt")
    pdf.setStrokeColor(colors.lightgrey)
    pdf.line(20 * mm, 258 * mm, 190 * mm, 258 * mm)

    patient = invoice.patient
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(20 * mm, 245 * mm, "Received from")
    pdf.setFont("Helvetica", 10)
    pdf.drawString(20 * mm, 240 * mm, f"{patient.first_name} {patient.last_name}")
    address = ", ".join(
        part for part in [patient.address_line1, patient.address_line2, patient.city, patient.postcode] if part
    )
    if address:
        pdf.drawString(20 * mm, 235 * mm, address)

    pdf.setFont("Helvetica", 10)
    pdf.drawString(120 * mm, 245 * mm, f"Invoice: {invoice.invoice_number}")
    pdf.drawString(120 * mm, 240 * mm, f"Payment date: {payment.paid_at.strftime('%Y-%m-%d')}")
    pdf.drawString(120 * mm, 235 * mm, f"Method: {payment.method.value}")
    if payment.reference:
        pdf.drawString(120 * mm, 230 * mm, f"Reference: {payment.reference}")

    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(20 * mm, 205 * mm, f"Amount received: {_format_gbp(payment.amount_pence)}")
    pdf.setFont("Helvetica", 10)
    pdf.drawString(20 * mm, 190 * mm, f"Balance remaining: {_format_gbp(invoice.balance_pence)}")
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()
