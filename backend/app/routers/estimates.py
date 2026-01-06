from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.deps import require_roles
from app.models.appointment import Appointment
from app.models.estimate import Estimate, EstimateFeeType, EstimateItem, EstimateStatus
from app.models.patient import Patient
from app.models.treatment import Treatment
from app.models.user import User
from app.schemas.estimate import (
    EstimateCreate,
    EstimateItemCreate,
    EstimateItemOut,
    EstimateItemUpdate,
    EstimateOut,
    EstimateUpdate,
)

router = APIRouter(prefix="/estimates", tags=["estimates"])
patient_router = APIRouter(prefix="/patients/{patient_id}/estimates", tags=["estimates"])


def validate_item_fee(payload: EstimateItemCreate | EstimateItemUpdate) -> None:
    if payload.fee_type is None:
        return
    if payload.fee_type == EstimateFeeType.fixed:
        if payload.unit_amount_pence is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="unit_amount_pence is required for FIXED items",
            )
    elif payload.fee_type == EstimateFeeType.range:
        if payload.min_unit_amount_pence is None or payload.max_unit_amount_pence is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="min_unit_amount_pence and max_unit_amount_pence are required for RANGE items",
            )
        if payload.min_unit_amount_pence > payload.max_unit_amount_pence:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="min_unit_amount_pence cannot exceed max_unit_amount_pence",
            )


def get_estimate_or_404(db: Session, estimate_id: int) -> Estimate:
    estimate = db.scalar(
        select(Estimate)
        .where(Estimate.id == estimate_id)
        .options(selectinload(Estimate.items))
    )
    if not estimate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Estimate not found")
    return estimate


@patient_router.get("", response_model=list[EstimateOut])
def list_patient_estimates(
    patient_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles("superadmin")),
):
    patient = db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    stmt = (
        select(Estimate)
        .where(Estimate.patient_id == patient_id)
        .order_by(Estimate.created_at.desc())
        .options(selectinload(Estimate.items))
    )
    return list(db.scalars(stmt))


@patient_router.post("", response_model=EstimateOut, status_code=status.HTTP_201_CREATED)
def create_estimate(
    patient_id: int,
    payload: EstimateCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("superadmin")),
):
    patient = db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

    appointment_id = payload.appointment_id
    if appointment_id is not None:
        appointment = db.get(Appointment, appointment_id)
        if not appointment or appointment.patient_id != patient_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Appointment does not match patient",
            )

    estimate = Estimate(
        patient_id=patient_id,
        appointment_id=appointment_id,
        category_snapshot=payload.category_snapshot or patient.patient_category,
        status=EstimateStatus.draft,
        valid_until=payload.valid_until,
        notes=payload.notes,
        created_by_user_id=user.id,
        updated_by_user_id=user.id,
    )
    db.add(estimate)
    db.commit()
    db.refresh(estimate)
    return estimate


@router.get("/{estimate_id}", response_model=EstimateOut)
def get_estimate(
    estimate_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles("superadmin")),
):
    return get_estimate_or_404(db, estimate_id)


@router.patch("/{estimate_id}", response_model=EstimateOut)
def update_estimate(
    estimate_id: int,
    payload: EstimateUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("superadmin")),
):
    estimate = get_estimate_or_404(db, estimate_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(estimate, field, value)
    estimate.updated_by_user_id = user.id
    db.add(estimate)
    db.commit()
    db.refresh(estimate)
    return estimate


@router.post("/{estimate_id}/items", response_model=EstimateItemOut, status_code=status.HTTP_201_CREATED)
def add_estimate_item(
    estimate_id: int,
    payload: EstimateItemCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("superadmin")),
):
    estimate = get_estimate_or_404(db, estimate_id)
    validate_item_fee(payload)

    description = payload.description
    treatment_id = payload.treatment_id
    if treatment_id is not None:
        treatment = db.get(Treatment, treatment_id)
        if not treatment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Treatment not found")
        if not description:
            description = treatment.name

    if not description:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="description is required",
        )

    sort_order = payload.sort_order
    if sort_order is None:
        sort_order = (
            db.scalar(
                select(func.coalesce(func.max(EstimateItem.sort_order), 0)).where(
                    EstimateItem.estimate_id == estimate_id
                )
            )
            or 0
        ) + 1

    item = EstimateItem(
        estimate_id=estimate_id,
        treatment_id=treatment_id,
        description=description,
        qty=payload.qty,
        fee_type=payload.fee_type,
        unit_amount_pence=payload.unit_amount_pence,
        min_unit_amount_pence=payload.min_unit_amount_pence,
        max_unit_amount_pence=payload.max_unit_amount_pence,
        sort_order=sort_order,
    )
    estimate.updated_by_user_id = user.id
    db.add(item)
    db.add(estimate)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/{estimate_id}/items/{item_id}", response_model=EstimateItemOut)
def update_estimate_item(
    estimate_id: int,
    item_id: int,
    payload: EstimateItemUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("superadmin")),
):
    estimate = get_estimate_or_404(db, estimate_id)
    item = db.get(EstimateItem, item_id)
    if not item or item.estimate_id != estimate_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Estimate item not found")

    if payload.fee_type is not None:
        validate_item_fee(payload)

    if payload.treatment_id is not None:
        treatment = db.get(Treatment, payload.treatment_id)
        if not treatment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Treatment not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    estimate.updated_by_user_id = user.id
    db.add(item)
    db.add(estimate)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{estimate_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_estimate_item(
    estimate_id: int,
    item_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("superadmin")),
):
    estimate = get_estimate_or_404(db, estimate_id)
    item = db.get(EstimateItem, item_id)
    if not item or item.estimate_id != estimate_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Estimate item not found")

    estimate.updated_by_user_id = user.id
    db.delete(item)
    db.add(estimate)
    db.commit()
    return None
