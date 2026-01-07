from __future__ import annotations

import argparse
from datetime import datetime, time, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.db.session import SessionLocal
from app.models.invoice import Invoice, InvoiceStatus, Payment
from app.models.ledger import LedgerEntryType, PatientLedgerEntry
from app.models.user import User


def resolve_actor_id(session) -> int:
    actor_id = session.scalar(select(func.min(User.id)))
    if not actor_id:
        raise RuntimeError("No users found; cannot attribute ledger entries.")
    return int(actor_id)


def get_existing_entry(session, reference: str | None, predicate) -> bool:
    if reference:
        exists = session.scalar(
            select(PatientLedgerEntry.id).where(PatientLedgerEntry.reference == reference)
        )
        if exists:
            return True
    exists = session.scalar(select(PatientLedgerEntry.id).where(predicate))
    return bool(exists)


def backfill_invoices(session, actor_id: int, apply: bool) -> tuple[int, int]:
    created = 0
    skipped = 0
    stmt = select(Invoice).where(
        Invoice.status.in_(
            [InvoiceStatus.issued, InvoiceStatus.part_paid, InvoiceStatus.paid]
        )
    )
    for invoice in session.scalars(stmt):
        if invoice.total_pence <= 0:
            skipped += 1
            continue
        reference = f"INV:{invoice.id}"
        predicate = (
            (PatientLedgerEntry.entry_type == LedgerEntryType.charge)
            & (PatientLedgerEntry.related_invoice_id == invoice.id)
            & (PatientLedgerEntry.amount_pence == invoice.total_pence)
        )
        if get_existing_entry(session, reference, predicate):
            skipped += 1
            continue
        created_at = invoice.created_at
        if invoice.issue_date:
            created_at = datetime.combine(invoice.issue_date, time.min, tzinfo=timezone.utc)
        entry = PatientLedgerEntry(
            patient_id=invoice.patient_id,
            entry_type=LedgerEntryType.charge,
            amount_pence=invoice.total_pence,
            reference=reference,
            note=f"Backfill invoice {invoice.invoice_number}",
            related_invoice_id=invoice.id,
            created_by_user_id=actor_id,
            updated_by_user_id=actor_id,
            created_at=created_at,
            updated_at=created_at,
        )
        if apply:
            session.add(entry)
        created += 1
    return created, skipped


def backfill_payments(session, actor_id: int, apply: bool) -> tuple[int, int]:
    created = 0
    skipped = 0
    stmt = select(Payment).options(selectinload(Payment.invoice))
    for payment in session.scalars(stmt):
        reference = f"PAY:{payment.id}"
        paid_at = payment.paid_at
        if not payment.invoice:
            skipped += 1
            continue
        predicate = (
            (PatientLedgerEntry.entry_type == LedgerEntryType.payment)
            & (PatientLedgerEntry.related_invoice_id == payment.invoice_id)
            & (PatientLedgerEntry.amount_pence == -abs(payment.amount_pence))
            & (PatientLedgerEntry.method == payment.method)
            & (func.date(PatientLedgerEntry.created_at) == paid_at.date())
        )
        if get_existing_entry(session, reference, predicate):
            skipped += 1
            continue
        entry = PatientLedgerEntry(
            patient_id=payment.invoice.patient_id,
            entry_type=LedgerEntryType.payment,
            amount_pence=-abs(payment.amount_pence),
            method=payment.method,
            reference=reference,
            note="Backfill payment",
            related_invoice_id=payment.invoice_id,
            created_by_user_id=actor_id,
            updated_by_user_id=actor_id,
            created_at=paid_at,
            updated_at=paid_at,
        )
        if apply:
            session.add(entry)
        created += 1
    return created, skipped


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill patient ledger entries.")
    parser.add_argument("--apply", action="store_true", help="Write changes to the database.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing (default).",
    )
    args = parser.parse_args()
    apply = args.apply and not args.dry_run

    session = SessionLocal()
    try:
        actor_id = resolve_actor_id(session)
        inv_created, inv_skipped = backfill_invoices(session, actor_id, apply)
        pay_created, pay_skipped = backfill_payments(session, actor_id, apply)
        if apply:
            session.commit()
        print("Ledger backfill")
        print(f"Invoices: created={inv_created} skipped={inv_skipped}")
        print(f"Payments: created={pay_created} skipped={pay_skipped}")
        if not apply:
            print("Dry run only. Use --apply to persist changes.")
        return 0
    except Exception as exc:
        session.rollback()
        raise exc
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
