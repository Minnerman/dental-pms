from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import require_roles
from app.models.treatment import FeeType, Treatment, TreatmentFee
from app.models.user import User
from app.schemas.treatment import (
    TreatmentCreate,
    TreatmentFeeOut,
    TreatmentFeeUpsert,
    TreatmentOut,
    TreatmentUpdate,
)

router = APIRouter(prefix="/treatments", tags=["treatments"])


def validate_fee_payload(payload: TreatmentFeeUpsert) -> None:
    if payload.fee_type == FeeType.fixed:
        if payload.amount_pence is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="amount_pence is required for FIXED fees",
            )
    elif payload.fee_type == FeeType.range:
        if payload.min_amount_pence is None or payload.max_amount_pence is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="min_amount_pence and max_amount_pence are required for RANGE fees",
            )
        if payload.min_amount_pence > payload.max_amount_pence:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="min_amount_pence cannot exceed max_amount_pence",
            )


@router.get("", response_model=list[TreatmentOut])
def list_treatments(
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles("superadmin")),
    include_inactive: bool = Query(default=False),
):
    stmt = select(Treatment).order_by(Treatment.name)
    if not include_inactive:
        stmt = stmt.where(Treatment.is_active.is_(True))
    return list(db.scalars(stmt))


@router.post("", response_model=TreatmentOut, status_code=status.HTTP_201_CREATED)
def create_treatment(
    payload: TreatmentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("superadmin")),
):
    treatment = Treatment(
        code=payload.code,
        name=payload.name,
        description=payload.description,
        is_active=payload.is_active,
        default_duration_minutes=payload.default_duration_minutes,
        is_denplan_included_default=payload.is_denplan_included_default,
        created_by_user_id=user.id,
        updated_by_user_id=user.id,
    )
    db.add(treatment)
    db.commit()
    db.refresh(treatment)
    return treatment


@router.get("/{treatment_id}", response_model=TreatmentOut)
def get_treatment(
    treatment_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles("superadmin")),
):
    treatment = db.get(Treatment, treatment_id)
    if not treatment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Treatment not found")
    return treatment


@router.patch("/{treatment_id}", response_model=TreatmentOut)
def update_treatment(
    treatment_id: int,
    payload: TreatmentUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("superadmin")),
):
    treatment = db.get(Treatment, treatment_id)
    if not treatment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Treatment not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(treatment, field, value)
    treatment.updated_by_user_id = user.id
    db.add(treatment)
    db.commit()
    db.refresh(treatment)
    return treatment


@router.get("/{treatment_id}/fees", response_model=list[TreatmentFeeOut])
def list_treatment_fees(
    treatment_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles("superadmin")),
):
    treatment = db.get(Treatment, treatment_id)
    if not treatment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Treatment not found")
    stmt = select(TreatmentFee).where(TreatmentFee.treatment_id == treatment_id)
    return list(db.scalars(stmt))


@router.put("/{treatment_id}/fees", response_model=list[TreatmentFeeOut])
def replace_treatment_fees(
    treatment_id: int,
    payload: list[TreatmentFeeUpsert],
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles("superadmin")),
):
    treatment = db.get(Treatment, treatment_id)
    if not treatment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Treatment not found")

    for fee in payload:
        validate_fee_payload(fee)

    db.execute(delete(TreatmentFee).where(TreatmentFee.treatment_id == treatment_id))
    for fee in payload:
        db.add(
            TreatmentFee(
                treatment_id=treatment_id,
                patient_category=fee.patient_category,
                fee_type=fee.fee_type,
                amount_pence=fee.amount_pence,
                min_amount_pence=fee.min_amount_pence,
                max_amount_pence=fee.max_amount_pence,
                notes=fee.notes,
            )
        )
    db.commit()
    stmt = select(TreatmentFee).where(TreatmentFee.treatment_id == treatment_id)
    return list(db.scalars(stmt))
