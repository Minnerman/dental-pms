from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import require_capability, require_roles
from app.models.user import Role, User
from app.schemas.capability import CapabilityOut, UserCapabilitiesUpdate
from app.schemas.user import UserCreate, UserOut, UserPasswordResetRequest, UserPasswordResetResponse, UserUpdate
from app.services.audit import log_event
from app.services.capabilities import get_user_capabilities, replace_user_capabilities
from app.services.users import (
    PasswordPolicyError,
    create_user,
    get_user_by_email,
    get_user_by_id,
    set_password,
    update_user,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db),
    _=Depends(require_roles("superadmin")),
):
    return list(db.scalars(select(User).order_by(User.id)))


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def add_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("superadmin")),
):
    existing = get_user_by_email(db, payload.email)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already exists")
    try:
        user = create_user(
            db,
            email=payload.email,
            password=payload.temp_password,
            full_name=payload.full_name,
            role=Role(payload.role),
            is_active=True,
            must_change_password=True,
        )
    except PasswordPolicyError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
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
def list_roles(_=Depends(require_roles("superadmin"))):
    return [role.value for role in Role]


@router.get("/{user_id}", response_model=UserOut)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_roles("superadmin")),
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
    admin: User = Depends(require_roles("superadmin")),
):
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if payload.is_active is False and user.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot disable your own account",
        )
    if payload.role and user.role == Role.superadmin and payload.role != Role.superadmin:
        superadmin_count = db.scalar(
            select(func.count(User.id)).where(User.role == Role.superadmin)
        )
        if (superadmin_count or 0) <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one superadmin is required",
            )
    if payload.is_active is False and user.role == Role.superadmin:
        superadmin_count = db.scalar(
            select(func.count(User.id)).where(User.role == Role.superadmin, User.is_active.is_(True))
        )
        if (superadmin_count or 0) <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one active superadmin is required",
            )
    previous_role = user.role
    previous_active = user.is_active
    try:
        updated = update_user(
            db,
            user=user,
            full_name=payload.full_name,
            role=Role(payload.role) if payload.role else None,
            is_active=payload.is_active,
            password=payload.password,
        )
    except PasswordPolicyError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
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
    if payload.is_active is not None and updated.is_active != previous_active:
        log_event(
            db,
            actor=admin,
            action="user.activated" if updated.is_active else "user.deactivated",
            entity_type="user",
            entity_id=str(updated.id),
            before_data={"is_active": previous_active},
            after_data={"is_active": updated.is_active},
        )
        db.commit()
    return updated


@router.post("/{user_id}/reset-password", response_model=UserPasswordResetResponse)
def reset_user_password(
    user_id: int,
    payload: UserPasswordResetRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("superadmin")),
):
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    try:
        set_password(db, user=user, new_password=payload.temp_password, must_change_password=True)
    except PasswordPolicyError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
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


@router.get("/{user_id}/capabilities", response_model=list[CapabilityOut])
def list_user_capabilities(
    user_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_roles("superadmin")),
    __=Depends(require_capability("admin.permissions.manage")),
):
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return get_user_capabilities(db, user_id)


@router.put("/{user_id}/capabilities", response_model=list[CapabilityOut])
def replace_capabilities(
    user_id: int,
    payload: UserCapabilitiesUpdate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_roles("superadmin")),
    __=Depends(require_capability("admin.permissions.manage")),
):
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    try:
        return replace_user_capabilities(db, user_id, payload.capability_codes)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
