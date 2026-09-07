from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import require_capability
from app.models.user import User
from app.schemas.clinical_journal import ClinicalJournalOut, JournalFilter
from app.services.clinical_journal import clinical_journal

router = APIRouter(prefix="/patients/{patient_id}/clinical-journal", tags=["clinical-journal"])


@router.get("", response_model=ClinicalJournalOut)
def get_clinical_journal(
    patient_id: int,
    limit: int = Query(default=50, ge=1, le=100),
    before: str | None = Query(default=None, max_length=2000),
    category: JournalFilter = "all",
    q: str = Query(default="", max_length=200),
    tooth: str | None = Query(default=None, pattern=r"^(UR|UL|LR|LL)[1-8]$"),
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("patients.view")),
):
    return clinical_journal(db, patient_id=patient_id, user=user, limit=limit,
                            before=before, category=category, q=q, tooth=tooth)
