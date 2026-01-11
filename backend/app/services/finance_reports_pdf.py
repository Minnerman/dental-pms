from __future__ import annotations

from io import BytesIO
from typing import Iterable

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


def _profile_lines(profile: dict[str, str | None]) -> tuple[str, list[str], str]:
    name = profile.get("name") or "Practice"
    address_line1 = profile.get("address_line1") or ""
    address_line2 = profile.get("address_line2") or ""
    city = profile.get("city") or ""
    postcode = profile.get("postcode") or ""
    phone = profile.get("phone") or ""
    website = profile.get("website") or ""
    email = profile.get("email") or ""

    lines: list[str] = []
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

    return name, lines, phone


def _draw_header(pdf: canvas.Canvas, profile: dict[str, str | None], title: str) -> float:
    name, lines, phone = _profile_lines(profile)
    left = 20 * mm
    y = 280 * mm
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(left, y, name)
    pdf.setFont("Helvetica", 10)
    y -= 6 * mm
    for line in lines:
        pdf.drawString(left, y, line)
        y -= 4 * mm
    if phone:
        pdf.drawString(left, y, f"Tel: {phone}")
        y -= 4 * mm
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawRightString(190 * mm, 280 * mm, title)
    return y - 6 * mm


def _draw_line(pdf: canvas.Canvas, left: float, y: float, text: str, bold: bool = False) -> float:
    pdf.setFont("Helvetica-Bold" if bold else "Helvetica", 10)
    pdf.drawString(left, y, text)
    return y - 5 * mm


def build_month_pack_pdf(
    *,
    profile: dict[str, str | None],
    period_label: str,
    totals_by_method: dict[str, int],
    total_pence: int,
    daily_rows: Iterable[tuple[str, int]],
    outstanding_total_pence: int,
    top_debtors: Iterable[tuple[str, int]],
    notes: list[str],
) -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    left = 20 * mm
    y = _draw_header(pdf, profile, "Monthly finance pack")

    y = _draw_line(pdf, left, y, f"Period: {period_label}", bold=True)
    y = _draw_line(pdf, left, y, "", bold=False)

    y = _draw_line(pdf, left, y, "Cash-up summary", bold=True)
    y = _draw_line(pdf, left, y, f"Total: £{total_pence / 100:.2f}")
    for method in ["cash", "card", "bank_transfer", "other"]:
        value = totals_by_method.get(method, 0)
        label = method.replace("_", " ").title()
        y = _draw_line(pdf, left, y, f"{label}: £{value / 100:.2f}")

    y = _draw_line(pdf, left, y, "")
    y = _draw_line(pdf, left, y, "Daily totals (top 10)", bold=True)
    for day, total in list(daily_rows)[:10]:
        y = _draw_line(pdf, left, y, f"{day}: £{total / 100:.2f}")

    y = _draw_line(pdf, left, y, "")
    y = _draw_line(pdf, left, y, "Outstanding balances", bold=True)
    y = _draw_line(pdf, left, y, f"Total outstanding: £{outstanding_total_pence / 100:.2f}")
    for name, balance in list(top_debtors)[:10]:
        y = _draw_line(pdf, left, y, f"{name}: £{balance / 100:.2f}")

    if notes:
        y = _draw_line(pdf, left, y, "")
        y = _draw_line(pdf, left, y, "Notes", bold=True)
        for note in notes:
            y = _draw_line(pdf, left, y, f"- {note}")

    pdf.showPage()
    pdf.save()
    return buffer.getvalue()
