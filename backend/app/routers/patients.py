from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import get_current_user
from app.models.audit_log import AuditLog
from app.models.patient import Patient
from app.services.audit import log_event, snapshot_model
from app.schemas.audit_log import AuditLogOut
from app.schemas.patient import PatientCreate, PatientOut, PatientSearchOut, PatientUpdate
from app.models.user import User

router = APIRouter(prefix="/patients", tags=["patients"])


@router.get("", response_model=list[PatientOut])
def list_patients(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    query: str | None = Query(default=None, alias="query"),
    q: str | None = Query(default=None, alias="q"),
    email: str | None = Query(default=None),
    dob: date | None = Query(default=None),
    include_deleted: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    stmt = select(Patient).order_by(Patient.last_name, Patient.first_name)
    if not include_deleted:
        stmt = stmt.where(Patient.deleted_at.is_(None))
    search = q or query
    if search:
        like = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                Patient.first_name.ilike(like),
                Patient.last_name.ilike(like),
                Patient.email.ilike(like),
                Patient.phone.ilike(like),
            )
        )
    if email:
        stmt = stmt.where(Patient.email.ilike(f"%{email.strip()}%"))
    if dob:
        stmt = stmt.where(Patient.date_of_birth == dob)
    stmt = stmt.limit(limit).offset(offset)
    return list(db.scalars(stmt))


@router.get("/search", response_model=list[PatientSearchOut])
def search_patients(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    q: str = Query(min_length=1),
    limit: int = Query(default=20, ge=1, le=50),
):
    term = q.strip()
    like = f"%{term}%"
    stmt = select(Patient).where(Patient.deleted_at.is_(None))
    criteria = [
        Patient.first_name.ilike(like),
        Patient.last_name.ilike(like),
        Patient.phone.ilike(like),
    ]
    try:
        parsed = date.fromisoformat(term)
        criteria.append(Patient.date_of_birth == parsed)
    except ValueError:
        pass
    stmt = stmt.where(or_(*criteria)).order_by(Patient.last_name, Patient.first_name).limit(limit)
    return list(db.scalars(stmt))


@router.post("", response_model=PatientOut, status_code=status.HTTP_201_CREATED)
def create_patient(
    payload: PatientCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    request_id: str | None = Header(default=None),
):
    patient = Patient(
        nhs_number=payload.nhs_number,
        title=payload.title,
        first_name=payload.first_name,
        last_name=payload.last_name,
        date_of_birth=payload.date_of_birth,
        phone=payload.phone,
        email=payload.email,
        address_line1=payload.address_line1,
        address_line2=payload.address_line2,
        city=payload.city,
        postcode=payload.postcode,
        notes=payload.notes,
        allergies=payload.allergies,
        medical_alerts=payload.medical_alerts,
        safeguarding_notes=payload.safeguarding_notes,
        created_by_user_id=user.id,
        updated_by_user_id=user.id,
    )
    db.add(patient)
    db.flush()
    log_event(
        db,
        actor=user,
        action="create",
        entity_type="patient",
        entity_id=str(patient.id),
        before_obj=None,
        after_obj=patient,
        request_id=request_id,
        ip_address=request.client.host if request else None,
    )
    db.commit()
    db.refresh(patient)
    return patient


@router.get("/{patient_id}", response_model=PatientOut)
def get_patient(
    patient_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    include_deleted: bool = Query(default=False),
):
    patient = db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    if patient.deleted_at is not None and not include_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    return patient


@router.patch("/{patient_id}", response_model=PatientOut)
def update_patient(
    patient_id: int,
    payload: PatientUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    request_id: str | None = Header(default=None),
):
    patient = db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    if patient.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

    before_data = snapshot_model(patient)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(patient, field, value)
    patient.updated_by_user_id = user.id
    patient.updated_at = datetime.now(timezone.utc)
    db.add(patient)
    log_event(
        db,
        actor=user,
        action="update",
        entity_type="patient",
        entity_id=str(patient.id),
        before_data=before_data,
        after_obj=patient,
        request_id=request_id,
        ip_address=request.client.host if request else None,
    )
    db.commit()
    db.refresh(patient)
    return patient


@router.post("/{patient_id}/archive", response_model=PatientOut)
def archive_patient(
    patient_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    request_id: str | None = Header(default=None),
):
    patient = db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    if patient.deleted_at is not None:
        return patient

    before_data = snapshot_model(patient)
    patient.deleted_at = datetime.now(timezone.utc)
    patient.deleted_by_user_id = user.id
    patient.updated_by_user_id = user.id
    db.add(patient)
    log_event(
        db,
        actor=user,
        action="delete",
        entity_type="patient",
        entity_id=str(patient.id),
        before_data=before_data,
        after_obj=patient,
        request_id=request_id,
        ip_address=request.client.host if request else None,
    )
    db.commit()
    db.refresh(patient)
    return patient


@router.post("/{patient_id}/restore", response_model=PatientOut)
def restore_patient(
    patient_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    request_id: str | None = Header(default=None),
):
    patient = db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    if patient.deleted_at is None:
        return patient

    before_data = snapshot_model(patient)
    patient.deleted_at = None
    patient.deleted_by_user_id = None
    patient.updated_by_user_id = user.id
    db.add(patient)
    log_event(
        db,
        actor=user,
        action="restore",
        entity_type="patient",
        entity_id=str(patient.id),
        before_data=before_data,
        after_obj=patient,
        request_id=request_id,
        ip_address=request.client.host if request else None,
    )
    db.commit()
    db.refresh(patient)
    return patient


@router.get("/{patient_id}/audit", response_model=list[AuditLogOut])
def patient_audit(
    patient_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    stmt = (
        select(AuditLog)
        .where(AuditLog.entity_type == "patient", AuditLog.entity_id == str(patient_id))
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.scalars(stmt))
