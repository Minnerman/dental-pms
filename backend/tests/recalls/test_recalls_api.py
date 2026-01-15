import httpx
import pytest
from fastapi import HTTPException
from datetime import datetime, timezone

from app.routers import recalls as recalls_router


def _get_first_recall_id(client: httpx.Client, headers: dict[str, str]) -> int:
    response = client.get("/recalls", headers=headers, params={"limit": 1})
    assert response.status_code == 200, response.text
    data = response.json()
    assert isinstance(data, list)
    assert data, "Expected seeded recalls"
    return data[0]["id"]


def test_recalls_list_returns_rows(api_client, auth_headers):
    response = api_client.get("/recalls", headers=auth_headers, params={"limit": 1})
    assert response.status_code == 200, response.text
    data = response.json()
    assert isinstance(data, list)
    assert data, "Expected seeded recalls"


def test_export_count_returns_int(api_client, auth_headers):
    response = api_client.get("/recalls/export_count", headers=auth_headers)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert isinstance(payload.get("count"), int)

    response_repeat = api_client.get("/recalls/export_count", headers=auth_headers)
    assert response_repeat.status_code == 200, response_repeat.text
    assert response_repeat.json().get("count") == payload.get("count")


def test_export_count_filter_affects_results(api_client, auth_headers):
    total_resp = api_client.get("/recalls/export_count", headers=auth_headers)
    assert total_resp.status_code == 200, total_resp.text
    total = total_resp.json().get("count")
    assert isinstance(total, int)
    assert total > 0

    contacted_resp = api_client.get(
        "/recalls/export_count",
        headers=auth_headers,
        params={"contact_state": "contacted"},
    )
    assert contacted_resp.status_code == 200, contacted_resp.text
    contacted = contacted_resp.json().get("count")
    assert isinstance(contacted, int)
    assert 0 < contacted <= total

    never_resp = api_client.get(
        "/recalls/export_count",
        headers=auth_headers,
        params={"contact_state": "never"},
    )
    assert never_resp.status_code == 200, never_resp.text
    never = never_resp.json().get("count")
    assert isinstance(never, int)
    assert never == 0


def test_recalls_list_includes_last_contact_fields(api_client, auth_headers):
    response = api_client.get(
        "/recalls",
        headers=auth_headers,
        params={"contact_state": "contacted", "limit": 5},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert isinstance(data, list)
    assert data, "Expected contacted recalls"
    assert any(row.get("last_contacted_at") for row in data)


def test_recalls_last_contact_filters(api_client, auth_headers):
    recall_id = _get_first_recall_id(api_client, auth_headers)
    contacted_at = datetime.now(timezone.utc).isoformat()
    response = api_client.post(
        f"/recalls/{recall_id}/contact",
        headers=auth_headers,
        json={"method": "phone", "contacted_at": contacted_at},
    )
    assert response.status_code == 200, response.text

    recent = api_client.get(
        "/recalls",
        headers=auth_headers,
        params={"last_contact": "7d", "method": "phone"},
    )
    assert recent.status_code == 200, recent.text
    recent_ids = {row.get("id") for row in recent.json()}
    assert recall_id in recent_ids

    older = api_client.get(
        "/recalls",
        headers=auth_headers,
        params={"last_contact": "older30d", "method": "phone"},
    )
    assert older.status_code == 200, older.text
    older_ids = {row.get("id") for row in older.json()}
    assert recall_id not in older_ids


def test_contact_validation_other_detail(api_client, auth_headers):
    recall_id = _get_first_recall_id(api_client, auth_headers)

    missing_detail = api_client.post(
        f"/recalls/{recall_id}/contact",
        headers=auth_headers,
        json={"method": "other"},
    )
    assert missing_detail.status_code == 422, missing_detail.text

    valid = api_client.post(
        f"/recalls/{recall_id}/contact",
        headers=auth_headers,
        json={"method": "other", "other_detail": "WhatsApp", "outcome": "seeded"},
    )
    assert valid.status_code == 200, valid.text


def test_export_csv_returns_csv(api_client, auth_headers):
    response = api_client.get("/recalls/export.csv", headers=auth_headers)
    assert response.status_code == 200, response.text
    content_type = response.headers.get("content-type", "")
    assert "text/csv" in content_type
    body = response.text.strip().splitlines()
    assert body, "Expected CSV output"
    assert "patient_id" in body[0]


def test_export_guardrail_rejects_large_exports(monkeypatch):
    monkeypatch.setattr(recalls_router, "MAX_EXPORT_ROWS", 0)

    class DummyResult:
        def __init__(self, value: int):
            self._value = value

        def scalar_one(self):
            return self._value

    class DummyDB:
        def execute(self, _stmt):
            return DummyResult(1)

    with pytest.raises(HTTPException) as excinfo:
        recalls_router.export_recalls_csv(
            db=DummyDB(),
            _user=object(),
            start=None,
            end=None,
            recall_status=None,
            recall_type=None,
            contact_state=None,
            last_contact=None,
            method=None,
            contacted=None,
            contacted_within_days=None,
            contact_channel=None,
            page_only=False,
            limit=50,
            offset=0,
        )

    assert excinfo.value.status_code == 413
