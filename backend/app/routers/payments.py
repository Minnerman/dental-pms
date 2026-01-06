from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import get_current_user
from app.models.invoice import Payment
from app.models.user import User
from app.services.audit import log_event
from app.services.pdf import build_payment_receipt

router = APIRouter(prefix="/payments", tags=["payments"])


@router.get("/{payment_id}/receipt.pdf")
def get_payment_receipt(
    payment_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    request_id: str | None = Header(default=None),
):
    payment = db.get(Payment, payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    pdf_bytes = build_payment_receipt(payment)
    log_event(
        db,
        actor=user,
        action="payment.receipt_generated",
        entity_type="invoice",
        entity_id=str(payment.invoice_id),
        before_obj=None,
        after_obj=None,
        request_id=request_id,
        ip_address=request.client.host if request else None,
    )
    db.commit()
    filename = f"receipt-{payment.invoice_id}-{payment.id}.pdf"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)
