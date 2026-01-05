from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.settings import settings
from app.core.security import create_access_token, generate_reset_token, hash_reset_token, verify_password
from app.db.session import get_db
from app.services.audit import log_event
from app.services.rate_limit import SimpleRateLimiter
from app.schemas.auth import (
    ChangePasswordRequest,
    ChangePasswordResponse,
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetConfirmResponse,
    PasswordResetRequest,
    PasswordResetResponse,
    Token,
)
from app.services.users import get_user_by_email, reset_password_with_token, set_password, set_password_reset_token
from app.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])

JWT_SECRET = settings.secret_key
JWT_ALG = settings.jwt_alg
EXPIRES = settings.access_token_expire_minutes
RESET_EXPIRES = settings.reset_token_expire_minutes
RESET_DEBUG = settings.reset_token_debug
RESET_REQUESTS_PER_MINUTE = settings.reset_requests_per_minute
RESET_CONFIRM_PER_MINUTE = settings.reset_confirm_per_minute

RESET_REQUEST_LIMITER = SimpleRateLimiter(
    max_events=RESET_REQUESTS_PER_MINUTE, window_seconds=60
)
RESET_CONFIRM_LIMITER = SimpleRateLimiter(
    max_events=RESET_CONFIRM_PER_MINUTE, window_seconds=60
)
LOGIN_LIMITER = SimpleRateLimiter(max_events=10, window_seconds=60)
LOGIN_IP_LIMITER = SimpleRateLimiter(max_events=20, window_seconds=60)


@router.post("/login", response_model=Token)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    ip_address = request.client.host if request else "unknown"
    rate_key = f"{ip_address}:{payload.email.lower().strip()}"
    if not LOGIN_LIMITER.allow(rate_key) or not LOGIN_IP_LIMITER.allow(ip_address):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many login attempts")

    user = get_user_by_email(db, payload.email)
    if user and not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token(
        subject=str(user.id),
        secret=JWT_SECRET,
        alg=JWT_ALG,
        expires_minutes=EXPIRES,
        extra={"role": user.role.value, "email": user.email},
    )
    return Token(access_token=token, must_change_password=user.must_change_password)


@router.post("/password-reset/request", response_model=PasswordResetResponse)
def request_password_reset(
    payload: PasswordResetRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    email = payload.email.lower().strip()
    ip_address = request.client.host if request else None
    rate_key = f"{ip_address or 'unknown'}:{email}"
    if not RESET_REQUEST_LIMITER.allow(rate_key):
        log_event(
            db,
            actor=None,
            action="password_reset_throttle",
            entity_type="auth",
            entity_id="password_reset_request",
            after_data={"email": email, "status": "throttled"},
            ip_address=ip_address,
        )
        db.commit()
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many requests")
    user = get_user_by_email(db, email)
    token: str | None = None
    if user and user.is_active:
        token = generate_reset_token()
        token_hash = hash_reset_token(token)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=RESET_EXPIRES)
        set_password_reset_token(db, user=user, token_hash=token_hash, expires_at=expires_at)
        log_event(
            db,
            actor=None,
            action="password_reset_request",
            entity_type="user",
            entity_id=str(user.id),
            after_data={"email": email, "status": "issued"},
            ip_address=ip_address,
        )
    else:
        log_event(
            db,
            actor=None,
            action="password_reset_request",
            entity_type="user",
            entity_id="unknown",
            after_data={"email": email, "status": "ignored"},
            ip_address=ip_address,
        )
    db.commit()
    response = PasswordResetResponse(
        message="If the account exists, a reset link has been generated.",
        reset_token=token if RESET_DEBUG else None,
    )
    return response


@router.post("/password-reset/confirm", response_model=PasswordResetConfirmResponse)
def confirm_password_reset(
    payload: PasswordResetConfirm,
    request: Request,
    db: Session = Depends(get_db),
):
    ip_address = request.client.host if request else None
    rate_key = f"{ip_address or 'unknown'}:confirm"
    if not RESET_CONFIRM_LIMITER.allow(rate_key):
        log_event(
            db,
            actor=None,
            action="password_reset_throttle",
            entity_type="auth",
            entity_id="password_reset_confirm",
            after_data={"status": "throttled"},
            ip_address=ip_address,
        )
        db.commit()
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many requests")
    token_hash = hash_reset_token(payload.token)
    user = reset_password_with_token(db, token_hash=token_hash, new_password=payload.new_password)
    if not user:
        log_event(
            db,
            actor=None,
            action="password_reset_confirm",
            entity_type="user",
            entity_id="unknown",
            after_data={"status": "failed"},
            ip_address=ip_address,
        )
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token")
    log_event(
        db,
        actor=None,
        action="password_reset_confirm",
        entity_type="user",
        entity_id=str(user.id),
        after_data={"status": "success"},
        ip_address=ip_address,
    )
    db.commit()
    return PasswordResetConfirmResponse(message="Password updated. You can now sign in.")


@router.post("/change-password", response_model=ChangePasswordResponse)
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    ip_address = request.client.host if request else None
    if not user.must_change_password:
        if not payload.old_password:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Old password required")
        if not verify_password(payload.old_password, user.hashed_password):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid old password")
    elif payload.old_password and not verify_password(payload.old_password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid old password")

    set_password(db, user=user, new_password=payload.new_password, must_change_password=False)
    log_event(
        db,
        actor=user,
        action="user.password_changed",
        entity_type="user",
        entity_id=str(user.id),
        after_data={"status": "success"},
        ip_address=ip_address,
    )
    db.commit()
    return ChangePasswordResponse(message="Password updated.")
