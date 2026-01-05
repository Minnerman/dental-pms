from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.user import Role, User


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email))


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.scalar(select(User).where(User.id == user_id))


def authenticate(db: Session, email: str, password: str) -> User | None:
    user = get_user_by_email(db, email)
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def create_user(
    db: Session,
    *,
    email: str,
    password: str,
    full_name: str = "",
    role: Role = Role.reception,
    is_active: bool = True,
    must_change_password: bool = False,
) -> User:
    now = datetime.now(timezone.utc)
    user = User(
        email=email.lower().strip(),
        full_name=full_name,
        role=role,
        is_active=is_active,
        must_change_password=must_change_password,
        hashed_password=hash_password(password),
        created_at=now,
        updated_at=now,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def ensure_admin_user(db: Session, *, email: str, password: str) -> User:
    existing = get_user_by_email(db, email)
    if existing:
        return existing
    return create_user(
        db,
        email=email,
        password=password,
        full_name="Admin",
        role=Role.superadmin,
        is_active=True,
    )


def user_count(db: Session) -> int:
    return int(db.scalar(select(func.count(User.id))) or 0)


def seed_initial_admin(db: Session, *, email: str, password: str) -> bool:
    if user_count(db) > 0:
        return False
    create_user(
        db,
        email=email,
        password=password,
        full_name="Admin",
        role=Role.superadmin,
        is_active=True,
        must_change_password=True,
    )
    return True


def update_user(
    db: Session,
    *,
    user: User,
    full_name: str | None = None,
    role: Role | None = None,
    is_active: bool | None = None,
    password: str | None = None,
) -> User:
    if full_name is not None:
        user.full_name = full_name
    if role is not None:
        user.role = role
    if is_active is not None:
        user.is_active = is_active
    if password:
        user.hashed_password = hash_password(password)
        user.must_change_password = False
    user.updated_at = datetime.now(timezone.utc)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def set_password(
    db: Session,
    *,
    user: User,
    new_password: str,
    must_change_password: bool | None = None,
) -> User:
    user.hashed_password = hash_password(new_password)
    if must_change_password is not None:
        user.must_change_password = must_change_password
    user.updated_at = datetime.now(timezone.utc)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def set_password_reset_token(
    db: Session,
    *,
    user: User,
    token_hash: str,
    expires_at: datetime,
) -> User:
    user.reset_token_hash = token_hash
    user.reset_token_expires_at = expires_at
    user.reset_token_used_at = None
    user.updated_at = datetime.now(timezone.utc)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def reset_password_with_token(
    db: Session,
    *,
    token_hash: str,
    new_password: str,
) -> User | None:
    now = datetime.now(timezone.utc)
    user = db.scalar(
        select(User).where(
            User.reset_token_hash == token_hash,
            User.reset_token_expires_at.is_not(None),
            User.reset_token_expires_at > now,
            User.reset_token_used_at.is_(None),
        )
    )
    if not user or not user.is_active:
        return None
    user.hashed_password = hash_password(new_password)
    user.must_change_password = False
    user.reset_token_used_at = now
    user.reset_token_hash = None
    user.reset_token_expires_at = None
    user.updated_at = now
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
