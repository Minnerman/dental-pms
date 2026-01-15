import os

import httpx
import pytest


@pytest.fixture(scope="session")
def admin_credentials():
    email = os.getenv("ADMIN_EMAIL", "admin@example.com")
    password = os.getenv("ADMIN_PASSWORD", "ChangeMe123!")
    return email, password


@pytest.fixture(scope="session")
def api_client():
    base_url = os.getenv("BACKEND_BASE_URL", "http://localhost:8000")
    with httpx.Client(base_url=base_url, timeout=10.0) as client:
        yield client


@pytest.fixture(scope="session")
def auth_headers(api_client, admin_credentials):
    email, password = admin_credentials
    response = api_client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    token = response.json().get("access_token")
    assert token, "Missing access_token in login response"
    return {"Authorization": f"Bearer {token}"}
