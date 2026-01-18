from __future__ import annotations

import uuid

from app.services.capabilities import CAPABILITIES


def test_capabilities_seeded(api_client, auth_headers):
    response = api_client.get("/capabilities", headers=auth_headers)
    assert response.status_code == 200, response.text
    payload = response.json()
    codes = {item["code"] for item in payload}
    expected = {code for code, _ in CAPABILITIES}
    assert expected.issubset(codes)


def test_user_has_all_capabilities_by_default(api_client, auth_headers):
    email = f"caps-{uuid.uuid4().hex[:8]}@example.com"
    payload = {
        "email": email,
        "full_name": "Cap Test",
        "role": "reception",
        "temp_password": "ChangeMe12345!",
    }
    create_res = api_client.post("/users", json=payload, headers=auth_headers)
    assert create_res.status_code == 201, create_res.text
    user_id = create_res.json()["id"]

    caps_res = api_client.get(f"/users/{user_id}/capabilities", headers=auth_headers)
    assert caps_res.status_code == 200, caps_res.text
    codes = {item["code"] for item in caps_res.json()}
    expected = {code for code, _ in CAPABILITIES}
    assert expected.issubset(codes)


def test_capability_guard_denies_when_removed(api_client, auth_headers):
    email = f"caps-guard-{uuid.uuid4().hex[:8]}@example.com"
    password = "ChangeMe12345!"
    payload = {
        "email": email,
        "full_name": "Cap Guard",
        "role": "reception",
        "temp_password": password,
    }
    create_res = api_client.post("/users", json=payload, headers=auth_headers)
    assert create_res.status_code == 201, create_res.text
    user_id = create_res.json()["id"]

    update_res = api_client.put(
        f"/users/{user_id}/capabilities",
        json={"capability_codes": []},
        headers=auth_headers,
    )
    assert update_res.status_code == 200, update_res.text
    assert update_res.json() == []

    login_res = api_client.post("/auth/login", json={"email": email, "password": password})
    assert login_res.status_code == 200, login_res.text
    token = login_res.json().get("access_token")
    assert token
    user_headers = {"Authorization": f"Bearer {token}"}

    denied = api_client.get("/capabilities", headers=user_headers)
    assert denied.status_code == 403, denied.text
