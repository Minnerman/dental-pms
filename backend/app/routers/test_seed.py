from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import require_admin
from app.services.charting_seed import seed_charting_demo

router = APIRouter(prefix="/test", tags=["test"])


@router.post("/seed/charting")
def seed_charting(request_db: Session = Depends(get_db), _=Depends(require_admin)) -> dict[str, object]:
    result = seed_charting_demo(request_db)
    request_db.commit()
    return result
