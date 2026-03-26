from __future__ import annotations

from uuid import uuid4

import pytest

from app.db.session import SessionLocal
from app.models.user import Role
from app.services.users import create_user

_ROLE_HEADERS: dict[Role, dict[str, str]] = {}


def _login_headers(api_client, role: Role) -> dict[str, str]:
    cached = _ROLE_HEADERS.get(role)
    if cached is not None:
        return cached

    email = f"{role.value}-{uuid4().hex[:8]}@example.com"
    password = "ChangeMe123!000"
    session = SessionLocal()
    try:
        create_user(session, email=email, password=password, role=role, full_name=role.value.title())
    finally:
        session.close()

    response = api_client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    _ROLE_HEADERS[role] = headers
    return headers


def _seed_target_user() -> int:
    email = f"target-{uuid4().hex[:8]}@example.com"
    session = SessionLocal()
    try:
        user = create_user(
            session,
            email=email,
            password="ChangeMe123!111",
            role=Role.external,
            full_name="Target User",
        )
        return int(user.id)
    finally:
        session.close()


def _build_request(case_name: str, target_user_id: int) -> tuple[str, str, dict | None]:
    if case_name == "list_users":
        return "GET", "/users", None
    if case_name == "list_roles":
        return "GET", "/users/roles", None
    if case_name == "get_user":
        return "GET", f"/users/{target_user_id}", None
    if case_name == "create_user":
        return "POST", "/users", {
            "email": f"created-{uuid4().hex[:8]}@example.com",
            "full_name": "Created User",
            "role": "reception",
            "temp_password": "ChangeMe123!222",
        }
    if case_name == "patch_user":
        return "PATCH", f"/users/{target_user_id}", {"full_name": "Updated User"}
    if case_name == "reset_user_password":
        return "POST", f"/users/{target_user_id}/reset-password", {"temp_password": "ChangeMe123!333"}
    raise AssertionError(f"Unknown case: {case_name}")


@pytest.mark.parametrize(
    ("case_name", "expected_status"),
    [
        ("list_users", 200),
        ("list_roles", 200),
        ("get_user", 200),
        ("create_user", 201),
        ("patch_user", 200),
        ("reset_user_password", 200),
    ],
)
def test_users_management_surface_allows_superadmin(
    api_client,
    auth_headers,
    case_name: str,
    expected_status: int,
):
    target_user_id = _seed_target_user()
    method, path, payload = _build_request(case_name, target_user_id)

    response = api_client.request(method, path, headers=auth_headers, json=payload)

    assert response.status_code == expected_status, response.text


@pytest.mark.parametrize(
    "role",
    [Role.dentist, Role.nurse, Role.receptionist, Role.reception],
)
@pytest.mark.parametrize(
    "case_name",
    [
        "list_users",
        "list_roles",
        "get_user",
        "create_user",
        "patch_user",
        "reset_user_password",
    ],
)
def test_users_management_surface_denies_non_superadmins(
    api_client,
    role: Role,
    case_name: str,
):
    headers = _login_headers(api_client, role)
    target_user_id = _seed_target_user()
    method, path, payload = _build_request(case_name, target_user_id)

    response = api_client.request(method, path, headers=headers, json=payload)

    assert response.status_code == 403, response.text
