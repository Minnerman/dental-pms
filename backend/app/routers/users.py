import secrets
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import require_admin
from app.models.user import Role, User
from app.schemas.user import UserCreate, UserOut, UserPasswordResetRequest, UserPasswordResetResponse, UserUpdate
from app.services.audit import log_event
from app.services.users import create_user, get_user_by_id, set_password, update_user

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    return list(db.scalars(select(User).order_by(User.id)))


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def add_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    return create_user(
        db,
        email=payload.email,
        password=payload.password,
        full_name=payload.full_name,
        role=Role(payload.role),
        is_active=True,
    )


@router.get("/roles", response_model=list[str])
def list_roles(_=Depends(require_admin)):
    return [role.value for role in Role]


@router.get("/{user_id}", response_model=UserOut)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.patch("/{user_id}", response_model=UserOut)
def patch_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return update_user(
        db,
        user=user,
        full_name=payload.full_name,
        role=Role(payload.role) if payload.role else None,
        is_active=payload.is_active,
        password=payload.password,
    )


@router.post("/{user_id}/reset-password", response_model=UserPasswordResetResponse)
def reset_user_password(
    user_id: int,
    payload: UserPasswordResetRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    temp_password = payload.temp_password or secrets.token_urlsafe(12)
    if len(temp_password) < 8:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password too short")
    if len(temp_password.encode("utf-8")) > 72:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password too long")
    set_password(db, user=user, new_password=temp_password, must_change_password=True)
    log_event(
        db,
        actor=admin,
        action="user.password_reset",
        entity_type="user",
        entity_id=str(user.id),
        after_data={"status": "issued"},
    )
    db.commit()
    return UserPasswordResetResponse(temp_password=temp_password)
