from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import get_current_user
from app.models.user import User
from app.schemas.user import UserOut
from app.services.capabilities import get_user_capabilities

router = APIRouter(tags=["me"])


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.get("/me/capabilities", response_model=list[str])
def me_capabilities(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return [capability.code for capability in get_user_capabilities(db, user.id)]
