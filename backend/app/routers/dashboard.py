from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import get_current_user
from app.models.capability import Capability, UserCapability
from app.models.user import User
from app.schemas.dashboard import HomeDashboard
from app.services.dashboard import build_home_dashboard

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/home", response_model=HomeDashboard)
def home_dashboard(
    response: Response,
    limit: int = Query(default=8, ge=1, le=20),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    capabilities = set(db.scalars(select(Capability.code)
        .join(UserCapability, UserCapability.capability_id == Capability.id)
        .where(UserCapability.user_id == user.id)))
    response.headers["Cache-Control"] = "no-store"
    return build_home_dashboard(db, capabilities, limit=limit)
