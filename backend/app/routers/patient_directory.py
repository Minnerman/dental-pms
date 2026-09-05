from datetime import date

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import require_capability
from app.models.capability import Capability, UserCapability
from app.models.patient import PatientCategory
from app.models.user import User
from app.schemas.patient_directory import (
    DirectoryDirection, DirectorySort, DirectoryStatus, PatientDirectory,
)
from app.services.patient_directory import build_patient_directory

router = APIRouter(prefix="/patients", tags=["patients"])


@router.get("/directory", response_model=PatientDirectory)
def patient_directory(
    response: Response,
    query: str | None = Query(default=None, max_length=320),
    email: str | None = Query(default=None, max_length=320),
    dob: date | None = None,
    category: PatientCategory | None = None,
    status: DirectoryStatus = "active",
    sort: DirectorySort = "last_name",
    direction: DirectoryDirection = "asc",
    with_debt: bool = False,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("patients.view")),
):
    capabilities = set(db.scalars(select(Capability.code)
        .join(UserCapability, UserCapability.capability_id == Capability.id)
        .where(UserCapability.user_id == user.id)))
    response.headers["Cache-Control"] = "no-store"
    return build_patient_directory(
        db, capabilities, query=query, email=email, dob=dob, category=category,
        status=status, sort=sort, direction=direction, with_debt=with_debt,
        limit=limit, offset=offset,
    )
