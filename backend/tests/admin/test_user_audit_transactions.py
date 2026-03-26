from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.core.security import create_access_token, hash_reset_token, verify_password
from app.core.settings import settings
from app.db.session import SessionLocal
from app.models.audit_log import AuditLog
from app.models.user import Role, User
from app.routers import auth as auth_router
from app.routers import users as users_router
from app.services.users import create_user, get_user_by_email, get_user_by_id, set_password_reset_token

VALID_PASSWORD = "AuditAtomic12!"
UPDATED_PASSWORD = "AuditAtomic34!"


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


@pytest.fixture
def local_api_client():
    # Rollback tests monkeypatch router-local audit helpers, so they must hit the app in-process.
    with TestClient(app) as client:
        yield client


def _create_user(*, password: str = VALID_PASSWORD, role: Role = Role.external) -> dict[str, object]:
    email = f"user-audit-{uuid4().hex[:12]}@example.com"
    session = SessionLocal()
    try:
        user = create_user(
            session,
            email=email,
            password=password,
            full_name="Audit Transaction User",
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


def _admin_headers(admin_credentials: tuple[str, str]) -> dict[str, str]:
    email, _password = admin_credentials
    session = SessionLocal()
    try:
        user = get_user_by_email(session, email)
        assert user is not None
        return _auth_headers_for_user(user_id=int(user.id), email=user.email, role=user.role)
    finally:
        session.close()


def _get_user(user_id: int) -> User:
    session = SessionLocal()
    try:
        user = get_user_by_id(session, user_id)
        assert user is not None
        session.expunge(user)
        return user
    finally:
        session.close()


def _get_user_by_email_value(email: str) -> User | None:
    session = SessionLocal()
    try:
        user = get_user_by_email(session, email)
        if user is not None:
            session.expunge(user)
        return user
    finally:
        session.close()


def _get_audit(action: str, entity_id: str) -> AuditLog | None:
    session = SessionLocal()
    try:
        audit = session.scalar(
            select(AuditLog)
            .where(AuditLog.action == action, AuditLog.entity_id == entity_id)
            .order_by(AuditLog.id.desc())
        )
        if audit is not None:
            session.expunge(audit)
        return audit
    finally:
        session.close()


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


def _boom(*_args, **_kwargs):
    raise RuntimeError("audit write failed")


def test_create_user_writes_audit_in_same_transaction(api_client, auth_headers, admin_credentials):
    email = f"atomic-create-{uuid4().hex[:12]}@example.com"

    response = api_client.post(
        "/users",
        headers=auth_headers,
        json={
            "email": email,
            "full_name": "Atomic Create",
            "role": Role.reception.value,
            "temp_password": VALID_PASSWORD,
        },
    )

    assert response.status_code == 201, response.text
    user = _get_user_by_email_value(email)
    assert user is not None
    audit = _get_audit("user.created", str(user.id))
    assert audit is not None
    assert audit.actor_email == admin_credentials[0]
    assert audit.after_json == {"email": user.email, "role": user.role.value}


def test_create_user_rolls_back_when_audit_write_fails(local_api_client, admin_credentials, monkeypatch):
    email = f"atomic-create-fail-{uuid4().hex[:12]}@example.com"
    monkeypatch.setattr(users_router, "log_event", _boom)

    with pytest.raises(RuntimeError, match="audit write failed"):
        local_api_client.post(
            "/users",
            headers=_admin_headers(admin_credentials),
            json={
                "email": email,
                "full_name": "Atomic Create Fail",
                "role": Role.reception.value,
                "temp_password": VALID_PASSWORD,
            },
        )

    assert _get_user_by_email_value(email) is None


def test_patch_role_change_writes_audit_in_same_transaction(api_client, auth_headers, admin_credentials):
    user = _create_user(role=Role.external)

    response = api_client.patch(
        f"/users/{user['user_id']}",
        headers=auth_headers,
        json={"role": Role.nurse.value},
    )

    assert response.status_code == 200, response.text
    updated = _get_user(int(user["user_id"]))
    assert updated.role == Role.nurse
    audit = _get_audit("user.role_changed", str(updated.id))
    assert audit is not None
    assert audit.actor_email == admin_credentials[0]
    assert audit.before_json == {"role": Role.external.value}
    assert audit.after_json == {"role": Role.nurse.value}


def test_patch_role_change_rolls_back_when_audit_write_fails(local_api_client, admin_credentials, monkeypatch):
    user = _create_user(role=Role.external)
    monkeypatch.setattr(users_router, "log_event", _boom)

    with pytest.raises(RuntimeError, match="audit write failed"):
        local_api_client.patch(
            f"/users/{user['user_id']}",
            headers=_admin_headers(admin_credentials),
            json={"role": Role.nurse.value},
        )

    current = _get_user(int(user["user_id"]))
    assert current.role == Role.external
    assert _get_audit("user.role_changed", str(current.id)) is None


def test_patch_password_writes_audit_in_same_transaction(api_client, auth_headers, admin_credentials):
    user = _create_user()

    response = api_client.patch(
        f"/users/{user['user_id']}",
        headers=auth_headers,
        json={"password": UPDATED_PASSWORD},
    )

    assert response.status_code == 200, response.text
    updated = _get_user(int(user["user_id"]))
    assert verify_password(UPDATED_PASSWORD, updated.hashed_password)
    assert updated.must_change_password is False
    audit = _get_audit("user.password_changed", str(updated.id))
    assert audit is not None
    assert audit.actor_email == admin_credentials[0]
    assert audit.after_json == {"status": "success"}


def test_patch_password_rolls_back_when_audit_write_fails(local_api_client, admin_credentials, monkeypatch):
    user = _create_user()
    original = _get_user(int(user["user_id"]))
    monkeypatch.setattr(users_router, "log_event", _boom)

    with pytest.raises(RuntimeError, match="audit write failed"):
        local_api_client.patch(
            f"/users/{user['user_id']}",
            headers=_admin_headers(admin_credentials),
            json={"password": UPDATED_PASSWORD},
        )

    current = _get_user(int(user["user_id"]))
    assert current.hashed_password == original.hashed_password
    assert verify_password(user["password"], current.hashed_password)
    assert _get_audit("user.password_changed", str(current.id)) is None


def test_admin_reset_writes_audit_in_same_transaction(api_client, auth_headers, admin_credentials):
    user = _create_user()

    response = api_client.post(
        f"/users/{user['user_id']}/reset-password",
        headers=auth_headers,
        json={"temp_password": UPDATED_PASSWORD},
    )

    assert response.status_code == 200, response.text
    updated = _get_user(int(user["user_id"]))
    assert verify_password(UPDATED_PASSWORD, updated.hashed_password)
    assert updated.must_change_password is True
    audit = _get_audit("user.password_reset", str(updated.id))
    assert audit is not None
    assert audit.actor_email == admin_credentials[0]
    assert audit.after_json == {"status": "issued"}


def test_admin_reset_rolls_back_when_audit_write_fails(local_api_client, admin_credentials, monkeypatch):
    user = _create_user()
    original = _get_user(int(user["user_id"]))
    monkeypatch.setattr(users_router, "log_event", _boom)

    with pytest.raises(RuntimeError, match="audit write failed"):
        local_api_client.post(
            f"/users/{user['user_id']}/reset-password",
            headers=_admin_headers(admin_credentials),
            json={"temp_password": UPDATED_PASSWORD},
        )

    current = _get_user(int(user["user_id"]))
    assert current.hashed_password == original.hashed_password
    assert current.must_change_password == original.must_change_password
    assert _get_audit("user.password_reset", str(current.id)) is None


def test_password_reset_request_writes_audit_in_same_transaction(api_client):
    user = _create_user()

    response = api_client.post(
        "/auth/password-reset/request",
        json={"email": user["email"]},
    )

    assert response.status_code == 200, response.text
    updated = _get_user(int(user["user_id"]))
    assert updated.reset_token_hash is not None
    assert updated.reset_token_expires_at is not None
    assert updated.reset_token_used_at is None
    audit = _get_audit("password_reset_request", str(updated.id))
    assert audit is not None
    assert audit.after_json == {"email": user["email"], "status": "issued"}


def test_password_reset_request_rolls_back_when_audit_write_fails(local_api_client, monkeypatch):
    user = _create_user()
    monkeypatch.setattr(auth_router, "log_event", _boom)

    with pytest.raises(RuntimeError, match="audit write failed"):
        local_api_client.post(
            "/auth/password-reset/request",
            json={"email": user["email"]},
        )

    current = _get_user(int(user["user_id"]))
    assert current.reset_token_hash is None
    assert current.reset_token_expires_at is None
    assert current.reset_token_used_at is None
    assert _get_audit("password_reset_request", str(current.id)) is None


def test_password_reset_confirm_writes_audit_in_same_transaction(api_client):
    user = _create_user()
    token = _issue_reset_token(int(user["user_id"]))

    response = api_client.post(
        "/auth/password-reset/confirm",
        json={"token": token, "new_password": UPDATED_PASSWORD},
    )

    assert response.status_code == 200, response.text
    updated = _get_user(int(user["user_id"]))
    assert verify_password(UPDATED_PASSWORD, updated.hashed_password)
    assert updated.reset_token_hash is None
    assert updated.reset_token_expires_at is None
    assert updated.reset_token_used_at is not None
    audit = _get_audit("password_reset_confirm", str(updated.id))
    assert audit is not None
    assert audit.after_json == {"status": "success"}


def test_password_reset_confirm_rolls_back_when_audit_write_fails(local_api_client, monkeypatch):
    user = _create_user()
    token = _issue_reset_token(int(user["user_id"]))
    original = _get_user(int(user["user_id"]))
    monkeypatch.setattr(auth_router, "log_event", _boom)

    with pytest.raises(RuntimeError, match="audit write failed"):
        local_api_client.post(
            "/auth/password-reset/confirm",
            json={"token": token, "new_password": UPDATED_PASSWORD},
        )

    current = _get_user(int(user["user_id"]))
    assert current.hashed_password == original.hashed_password
    assert current.reset_token_hash == original.reset_token_hash
    assert current.reset_token_expires_at == original.reset_token_expires_at
    assert current.reset_token_used_at == original.reset_token_used_at
    assert _get_audit("password_reset_confirm", str(current.id)) is None


def test_change_password_writes_audit_in_same_transaction(api_client):
    user = _create_user()

    response = api_client.post(
        "/auth/change-password",
        headers=user["headers"],
        json={"old_password": user["password"], "new_password": UPDATED_PASSWORD},
    )

    assert response.status_code == 200, response.text
    updated = _get_user(int(user["user_id"]))
    assert verify_password(UPDATED_PASSWORD, updated.hashed_password)
    assert updated.must_change_password is False
    audit = _get_audit("user.password_changed", str(updated.id))
    assert audit is not None
    assert audit.after_json == {"status": "success"}


def test_change_password_rolls_back_when_audit_write_fails(local_api_client, monkeypatch):
    user = _create_user()
    original = _get_user(int(user["user_id"]))
    monkeypatch.setattr(auth_router, "log_event", _boom)

    with pytest.raises(RuntimeError, match="audit write failed"):
        local_api_client.post(
            "/auth/change-password",
            headers=user["headers"],
            json={"old_password": user["password"], "new_password": UPDATED_PASSWORD},
        )

    current = _get_user(int(user["user_id"]))
    assert current.hashed_password == original.hashed_password
    assert verify_password(user["password"], current.hashed_password)
    assert _get_audit("user.password_changed", str(current.id)) is None
