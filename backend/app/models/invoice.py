from __future__ import annotations

import enum
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AuditMixin, Base


class InvoiceStatus(str, enum.Enum):
    draft = "draft"
    issued = "issued"
    part_paid = "part_paid"
    paid = "paid"
    void = "void"


class PaymentMethod(str, enum.Enum):
    cash = "cash"
    card = "card"
    bank_transfer = "bank_transfer"
    other = "other"


class Invoice(Base, AuditMixin):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), nullable=False, index=True)
    appointment_id: Mapped[int | None] = mapped_column(
        ForeignKey("appointments.id"), nullable=True, index=True
    )
    invoice_number: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    issue_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[InvoiceStatus] = mapped_column(
        Enum(InvoiceStatus, name="invoice_status"),
        nullable=False,
        default=InvoiceStatus.draft,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    subtotal_pence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    discount_pence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_pence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    patient = relationship("Patient", back_populates="invoices", lazy="joined")
    appointment = relationship("Appointment", back_populates="invoices", lazy="joined")
    lines = relationship(
        "InvoiceLine", back_populates="invoice", cascade="all, delete-orphan", lazy="selectin"
    )
    payments = relationship(
        "Payment", back_populates="invoice", cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def paid_pence(self) -> int:
        return sum(payment.amount_pence for payment in self.payments or [])

    @property
    def balance_pence(self) -> int:
        return max(self.total_pence - self.paid_pence, 0)


class InvoiceLine(Base):
    __tablename__ = "invoice_lines"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"), nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit_price_pence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    line_total_pence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    invoice = relationship("Invoice", back_populates="lines")


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"), nullable=False, index=True)
    amount_pence: Mapped[int] = mapped_column(Integer, nullable=False)
    method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod, name="payment_method"), nullable=False
    )
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    received_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    invoice = relationship("Invoice", back_populates="payments")
