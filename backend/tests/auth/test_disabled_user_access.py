from __future__ import annotations

from uuid import uuid4

from app.db.session import SessionLocal
from app.models.user import Role
from app.services.users import create_user, get_user_by_id, update_user


def test_disabling_user_invalidates_existing_token_and_blocks_login(api_client):
    email = f"disabled-auth-{uuid4().hex[:8]}@example.com"
    password = "ChangeMe123!444"

    session = SessionLocal()
    try:
        user = create_user(
            session,
            email=email,
            password=password,
            role=Role.external,
            full_name="Disabled Auth User",
        )
        user_id = int(user.id)
    finally:
        session.close()

    login = api_client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert api_client.get("/me", headers=headers).status_code == 200

    session = SessionLocal()
    try:
        user = get_user_by_id(session, user_id)
        assert user is not None
        update_user(session, user=user, is_active=False)
    finally:
        session.close()

    current_user = api_client.get("/me", headers=headers)
    assert current_user.status_code == 401
    assert current_user.json()["detail"] == "Inactive user"

    relogin = api_client.post("/auth/login", json={"email": email, "password": password})
    assert relogin.status_code == 403
    assert relogin.json()["detail"] == "Account disabled"
