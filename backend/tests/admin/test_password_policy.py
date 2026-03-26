from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.routers import auth as auth_router
from app.core.security import hash_reset_token
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


@pytest.fixture(autouse=True)
def reset_auth_rate_limiters():
    auth_router.LOGIN_LIMITER._events.clear()
    auth_router.LOGIN_IP_LIMITER._events.clear()
    auth_router.RESET_REQUEST_LIMITER._events.clear()
    auth_router.RESET_CONFIRM_LIMITER._events.clear()
    yield
    auth_router.LOGIN_LIMITER._events.clear()
    auth_router.LOGIN_IP_LIMITER._events.clear()
    auth_router.RESET_REQUEST_LIMITER._events.clear()
    auth_router.RESET_CONFIRM_LIMITER._events.clear()


def _error_detail(response) -> str:
    payload = response.json()
    detail = payload.get("detail")
    if isinstance(detail, list):
        return " ".join(str(item.get("msg", "")) for item in detail)
    return str(detail)


def _create_user_with_login(api_client, *, password: str = VALID_PASSWORD) -> dict[str, object]:
    email = f"password-policy-{uuid4().hex[:12]}@example.com"
    session = SessionLocal()
    try:
        user = create_user(
            session,
            email=email,
            password=password,
            full_name="Password Policy User",
            role=Role.external,
        )
        user_id = int(user.id)
    finally:
        session.close()

    login = api_client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    return {
        "user_id": user_id,
        "email": email,
        "password": password,
        "headers": {"Authorization": f"Bearer {token}"},
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


def test_change_password_rejects_too_short_password(api_client):
    user = _create_user_with_login(api_client)

    response = api_client.post(
        "/auth/change-password",
        headers=user["headers"],
        json={"old_password": user["password"], "new_password": TOO_SHORT_PASSWORD},
    )

    assert response.status_code == 422, response.text
    assert f"at least {PASSWORD_MIN_LENGTH} characters" in _error_detail(response)


def test_change_password_rejects_overlong_password(api_client):
    user = _create_user_with_login(api_client)

    response = api_client.post(
        "/auth/change-password",
        headers=user["headers"],
        json={"old_password": user["password"], "new_password": OVERLONG_PASSWORD},
    )

    assert response.status_code == 400, response.text
    assert _error_detail(response) == f"Password must be {PASSWORD_MAX_BYTES} bytes or fewer."


def test_change_password_accepts_valid_password(api_client):
    user = _create_user_with_login(api_client)

    response = api_client.post(
        "/auth/change-password",
        headers=user["headers"],
        json={"old_password": user["password"], "new_password": UPDATED_PASSWORD},
    )

    assert response.status_code == 200, response.text
    old_login = api_client.post("/auth/login", json={"email": user["email"], "password": user["password"]})
    assert old_login.status_code == 401, old_login.text
    new_login = api_client.post("/auth/login", json={"email": user["email"], "password": UPDATED_PASSWORD})
    assert new_login.status_code == 200, new_login.text


def test_password_reset_confirm_rejects_too_short_password(api_client):
    user = _create_user_with_login(api_client)
    token = _issue_reset_token(int(user["user_id"]))

    response = api_client.post(
        "/auth/password-reset/confirm",
        json={"token": token, "new_password": TOO_SHORT_PASSWORD},
    )

    assert response.status_code == 422, response.text
    assert f"at least {PASSWORD_MIN_LENGTH} characters" in _error_detail(response)


def test_password_reset_confirm_rejects_overlong_password(api_client):
    user = _create_user_with_login(api_client)
    token = _issue_reset_token(int(user["user_id"]))

    response = api_client.post(
        "/auth/password-reset/confirm",
        json={"token": token, "new_password": OVERLONG_PASSWORD},
    )

    assert response.status_code == 400, response.text
    assert _error_detail(response) == f"Password must be {PASSWORD_MAX_BYTES} bytes or fewer."


def test_password_reset_confirm_accepts_valid_password(api_client):
    user = _create_user_with_login(api_client)
    token = _issue_reset_token(int(user["user_id"]))

    response = api_client.post(
        "/auth/password-reset/confirm",
        json={"token": token, "new_password": UPDATED_PASSWORD},
    )

    assert response.status_code == 200, response.text
    old_login = api_client.post("/auth/login", json={"email": user["email"], "password": user["password"]})
    assert old_login.status_code == 401, old_login.text
    new_login = api_client.post("/auth/login", json={"email": user["email"], "password": UPDATED_PASSWORD})
    assert new_login.status_code == 200, new_login.text


def test_admin_reset_password_rejects_too_short_password(api_client, auth_headers):
    user = _create_user_with_login(api_client)

    response = api_client.post(
        f"/users/{user['user_id']}/reset-password",
        headers=auth_headers,
        json={"temp_password": TOO_SHORT_PASSWORD},
    )

    assert response.status_code == 422, response.text
    assert f"at least {PASSWORD_MIN_LENGTH} characters" in _error_detail(response)


def test_admin_reset_password_rejects_overlong_password(api_client, auth_headers):
    user = _create_user_with_login(api_client)

    response = api_client.post(
        f"/users/{user['user_id']}/reset-password",
        headers=auth_headers,
        json={"temp_password": OVERLONG_PASSWORD},
    )

    assert response.status_code == 400, response.text
    assert _error_detail(response) == f"Password must be {PASSWORD_MAX_BYTES} bytes or fewer."


def test_admin_reset_password_accepts_valid_password(api_client, auth_headers):
    user = _create_user_with_login(api_client)

    response = api_client.post(
        f"/users/{user['user_id']}/reset-password",
        headers=auth_headers,
        json={"temp_password": UPDATED_PASSWORD},
    )

    assert response.status_code == 200, response.text
    login = api_client.post("/auth/login", json={"email": user["email"], "password": UPDATED_PASSWORD})
    assert login.status_code == 200, login.text
    assert login.json()["must_change_password"] is True


def test_patch_user_password_rejects_too_short_password(api_client, auth_headers):
    user = _create_user_with_login(api_client)

    response = api_client.patch(
        f"/users/{user['user_id']}",
        headers=auth_headers,
        json={"password": TOO_SHORT_PASSWORD},
    )

    assert response.status_code == 400, response.text
    assert _error_detail(response) == f"Password must be at least {PASSWORD_MIN_LENGTH} characters."


def test_patch_user_password_rejects_overlong_password(api_client, auth_headers):
    user = _create_user_with_login(api_client)

    response = api_client.patch(
        f"/users/{user['user_id']}",
        headers=auth_headers,
        json={"password": OVERLONG_PASSWORD},
    )

    assert response.status_code == 400, response.text
    assert _error_detail(response) == f"Password must be {PASSWORD_MAX_BYTES} bytes or fewer."


def test_patch_user_password_accepts_valid_password(api_client, auth_headers):
    user = _create_user_with_login(api_client)

    response = api_client.patch(
        f"/users/{user['user_id']}",
        headers=auth_headers,
        json={"password": UPDATED_PASSWORD},
    )

    assert response.status_code == 200, response.text
    old_login = api_client.post("/auth/login", json={"email": user["email"], "password": user["password"]})
    assert old_login.status_code == 401, old_login.text
    new_login = api_client.post("/auth/login", json={"email": user["email"], "password": UPDATED_PASSWORD})
    assert new_login.status_code == 200, new_login.text
