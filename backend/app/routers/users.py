from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import require_admin
from app.models.user import Role, User
from app.schemas.user import UserCreate, UserOut, UserPasswordResetRequest, UserPasswordResetResponse, UserUpdate
from app.services.audit import log_event
from app.services.users import create_user, get_user_by_email, get_user_by_id, set_password, update_user

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
    admin: User = Depends(require_admin),
):
    existing = get_user_by_email(db, payload.email)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already exists")
    user = create_user(
        db,
        email=payload.email,
        password=payload.temp_password,
        full_name=payload.full_name,
        role=Role(payload.role),
        is_active=True,
        must_change_password=True,
    )
    log_event(
        db,
        actor=admin,
        action="user.created",
        entity_type="user",
        entity_id=str(user.id),
        after_data={"email": user.email, "role": user.role.value},
    )
    db.commit()
    return user


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
    admin: User = Depends(require_admin),
):
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    previous_role = user.role
    updated = update_user(
        db,
        user=user,
        full_name=payload.full_name,
        role=Role(payload.role) if payload.role else None,
        is_active=payload.is_active,
        password=payload.password,
    )
    if payload.role and updated.role != previous_role:
        log_event(
            db,
            actor=admin,
            action="user.role_changed",
            entity_type="user",
            entity_id=str(updated.id),
            before_data={"role": previous_role.value},
            after_data={"role": updated.role.value},
        )
        db.commit()
    return updated


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
    temp_password = payload.temp_password
    if len(temp_password) < 12:
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
    return UserPasswordResetResponse(message="Temporary password set.")
