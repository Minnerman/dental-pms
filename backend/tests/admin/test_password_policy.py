from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.core.security import create_access_token, hash_reset_token, verify_password
from app.core.settings import settings
from app.db.session import SessionLocal
from app.models.user import Role
from app.services.users import (
    PASSWORD_MAX_BYTES,
    PASSWORD_MIN_LENGTH,
    create_user,
    get_user_by_id,
    set_password_reset_token,
)

VALID_PASSWORD = "PolicyPass12!"
UPDATED_PASSWORD = "PolicyPass34!"
TOO_SHORT_PASSWORD = "A" * (PASSWORD_MIN_LENGTH - 1)
OVERLONG_PASSWORD = "A" * (PASSWORD_MAX_BYTES + 1)


def _error_detail(response) -> str:
    payload = response.json()
    detail = payload.get("detail")
    if isinstance(detail, list):
        return " ".join(str(item.get("msg", "")) for item in detail)
    return str(detail)


def _jwt_secret() -> str:
    return settings.secret_key or settings.jwt_secret or "change-me"


def _auth_headers_for_user(*, user_id: int, email: str, role: Role) -> dict[str, str]:
    token = create_access_token(
        subject=str(user_id),
        secret=_jwt_secret(),
        alg=settings.jwt_alg,
        expires_minutes=settings.access_token_expire_minutes,
        extra={"role": role.value, "email": email},
    )
    return {"Authorization": f"Bearer {token}"}


def _create_user(*, password: str = VALID_PASSWORD, role: Role = Role.external) -> dict[str, object]:
    email = f"password-policy-{uuid4().hex[:12]}@example.com"
    session = SessionLocal()
    try:
        user = create_user(
            session,
            email=email,
            password=password,
            full_name="Password Policy User",
            role=role,
        )
        user_id = int(user.id)
    finally:
        session.close()

    return {
        "user_id": user_id,
        "email": email,
        "password": password,
        "role": role,
        "headers": _auth_headers_for_user(user_id=user_id, email=email, role=role),
    }


def _issue_reset_token(user_id: int) -> str:
    token = f"reset-{uuid4().hex}{uuid4().hex}"
    session = SessionLocal()
    try:
        user = get_user_by_id(session, user_id)
        assert user is not None
        set_password_reset_token(
            session,
            user=user,
            token_hash=hash_reset_token(token),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        )
    finally:
        session.close()
    return token


def _get_user_state(user_id: int):
    session = SessionLocal()
    try:
        user = get_user_by_id(session, user_id)
        assert user is not None
        return {
            "hashed_password": user.hashed_password,
            "must_change_password": user.must_change_password,
            "reset_token_hash": user.reset_token_hash,
            "reset_token_expires_at": user.reset_token_expires_at,
            "reset_token_used_at": user.reset_token_used_at,
        }
    finally:
        session.close()


def test_change_password_rejects_too_short_password(api_client):
    user = _create_user()

    response = api_client.post(
        "/auth/change-password",
        headers=user["headers"],
        json={"old_password": user["password"], "new_password": TOO_SHORT_PASSWORD},
    )

    assert response.status_code == 422, response.text
    assert f"at least {PASSWORD_MIN_LENGTH} characters" in _error_detail(response)


def test_change_password_rejects_overlong_password(api_client):
    user = _create_user()

    response = api_client.post(
        "/auth/change-password",
        headers=user["headers"],
        json={"old_password": user["password"], "new_password": OVERLONG_PASSWORD},
    )

    assert response.status_code == 400, response.text
    assert _error_detail(response) == f"Password must be {PASSWORD_MAX_BYTES} bytes or fewer."


def test_change_password_accepts_valid_password(api_client):
    user = _create_user()

    response = api_client.post(
        "/auth/change-password",
        headers=user["headers"],
        json={"old_password": user["password"], "new_password": UPDATED_PASSWORD},
    )

    assert response.status_code == 200, response.text
    state = _get_user_state(int(user["user_id"]))
    assert verify_password(UPDATED_PASSWORD, state["hashed_password"])
    assert not verify_password(user["password"], state["hashed_password"])
    assert state["must_change_password"] is False


def test_password_reset_confirm_rejects_too_short_password(api_client):
    user = _create_user()
    token = _issue_reset_token(int(user["user_id"]))

    response = api_client.post(
        "/auth/password-reset/confirm",
        json={"token": token, "new_password": TOO_SHORT_PASSWORD},
    )

    assert response.status_code == 422, response.text
    assert f"at least {PASSWORD_MIN_LENGTH} characters" in _error_detail(response)


def test_password_reset_confirm_rejects_overlong_password(api_client):
    user = _create_user()
    token = _issue_reset_token(int(user["user_id"]))

    response = api_client.post(
        "/auth/password-reset/confirm",
        json={"token": token, "new_password": OVERLONG_PASSWORD},
    )

    assert response.status_code == 400, response.text
    assert _error_detail(response) == f"Password must be {PASSWORD_MAX_BYTES} bytes or fewer."


def test_password_reset_confirm_accepts_valid_password(api_client):
    user = _create_user()
    token = _issue_reset_token(int(user["user_id"]))

    response = api_client.post(
        "/auth/password-reset/confirm",
        json={"token": token, "new_password": UPDATED_PASSWORD},
    )

    assert response.status_code == 200, response.text
    state = _get_user_state(int(user["user_id"]))
    assert verify_password(UPDATED_PASSWORD, state["hashed_password"])
    assert not verify_password(user["password"], state["hashed_password"])
    assert state["must_change_password"] is False
    assert state["reset_token_hash"] is None
    assert state["reset_token_expires_at"] is None
    assert state["reset_token_used_at"] is not None


def test_admin_reset_password_rejects_too_short_password(api_client, auth_headers):
    user = _create_user()

    response = api_client.post(
        f"/users/{user['user_id']}/reset-password",
        headers=auth_headers,
        json={"temp_password": TOO_SHORT_PASSWORD},
    )

    assert response.status_code == 422, response.text
    assert f"at least {PASSWORD_MIN_LENGTH} characters" in _error_detail(response)


def test_admin_reset_password_rejects_overlong_password(api_client, auth_headers):
    user = _create_user()

    response = api_client.post(
        f"/users/{user['user_id']}/reset-password",
        headers=auth_headers,
        json={"temp_password": OVERLONG_PASSWORD},
    )

    assert response.status_code == 400, response.text
    assert _error_detail(response) == f"Password must be {PASSWORD_MAX_BYTES} bytes or fewer."


def test_admin_reset_password_accepts_valid_password(api_client, auth_headers):
    user = _create_user()

    response = api_client.post(
        f"/users/{user['user_id']}/reset-password",
        headers=auth_headers,
        json={"temp_password": UPDATED_PASSWORD},
    )

    assert response.status_code == 200, response.text
    state = _get_user_state(int(user["user_id"]))
    assert verify_password(UPDATED_PASSWORD, state["hashed_password"])
    assert not verify_password(user["password"], state["hashed_password"])
    assert state["must_change_password"] is True


def test_patch_user_password_rejects_too_short_password(api_client, auth_headers):
    user = _create_user()

    response = api_client.patch(
        f"/users/{user['user_id']}",
        headers=auth_headers,
        json={"password": TOO_SHORT_PASSWORD},
    )

    assert response.status_code == 400, response.text
    assert _error_detail(response) == f"Password must be at least {PASSWORD_MIN_LENGTH} characters."


def test_patch_user_password_rejects_overlong_password(api_client, auth_headers):
    user = _create_user()

    response = api_client.patch(
        f"/users/{user['user_id']}",
        headers=auth_headers,
        json={"password": OVERLONG_PASSWORD},
    )

    assert response.status_code == 400, response.text
    assert _error_detail(response) == f"Password must be {PASSWORD_MAX_BYTES} bytes or fewer."


def test_patch_user_password_accepts_valid_password(api_client, auth_headers):
    user = _create_user()

    response = api_client.patch(
        f"/users/{user['user_id']}",
        headers=auth_headers,
        json={"password": UPDATED_PASSWORD},
    )

    assert response.status_code == 200, response.text
    state = _get_user_state(int(user["user_id"]))
    assert verify_password(UPDATED_PASSWORD, state["hashed_password"])
    assert not verify_password(user["password"], state["hashed_password"])
    assert state["must_change_password"] is False
