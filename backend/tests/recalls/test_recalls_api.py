from datetime import datetime, timezone
from types import SimpleNamespace
import re

import httpx
import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.routers import recalls as recalls_router


def _get_first_recall_id(client: httpx.Client, headers: dict[str, str]) -> int:
    response = client.get("/recalls", headers=headers, params={"limit": 1})
    assert response.status_code == 200, response.text
    data = response.json()
    assert isinstance(data, list)
    assert data, "Expected seeded recalls"
    return data[0]["id"]


def _get_filename_from_disposition(headers: httpx.Headers) -> str:
    header = headers.get("content-disposition") or ""
    match = re.search(r'filename="([^"]+)"', header)
    return match.group(1) if match else ""


def _assert_safe_filename(value: str) -> None:
    assert value
    assert not re.search(r"[\\/:*?\"<>|]", value)
    assert len(value) <= recalls_router.MAX_EXPORT_FILENAME_LENGTH


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


def test_export_count_includes_filenames(api_client, auth_headers):
    response = api_client.get("/recalls/export_count", headers=auth_headers)
    assert response.status_code == 200, response.text
    payload = response.json()
    csv_name = payload.get("suggested_filename_csv")
    zip_name = payload.get("suggested_filename_zip")
    assert isinstance(csv_name, str)
    assert isinstance(zip_name, str)
    assert csv_name.endswith(".csv")
    assert zip_name.endswith(".zip")
    _assert_safe_filename(csv_name)
    _assert_safe_filename(zip_name)


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


def test_export_filenames_match_suggested(api_client, auth_headers):
    count_resp = api_client.get(
        "/recalls/export_count",
        headers=auth_headers,
        params={"page_only": True},
    )
    assert count_resp.status_code == 200, count_resp.text
    payload = count_resp.json()
    suggested_csv = payload.get("suggested_filename_csv")
    suggested_zip = payload.get("suggested_filename_zip")

    export_csv_resp = api_client.get(
        "/recalls/export.csv",
        headers=auth_headers,
        params={"page_only": True},
    )
    assert export_csv_resp.status_code == 200, export_csv_resp.text
    assert _get_filename_from_disposition(export_csv_resp.headers) == suggested_csv

    export_zip_resp = api_client.get(
        "/recalls/letters.zip",
        headers=auth_headers,
        params={"page_only": True},
    )
    assert export_zip_resp.status_code == 200, export_zip_resp.text
    assert _get_filename_from_disposition(export_zip_resp.headers) == suggested_zip


def test_export_csv_creates_audit_log(api_client, auth_headers):
    export_resp = api_client.get("/recalls/export.csv", headers=auth_headers)
    assert export_resp.status_code == 200, export_resp.text

    audit_resp = api_client.get(
        "/audit",
        headers=auth_headers,
        params={"entity_type": "recall_export", "entity_id": "csv", "limit": 10},
    )
    assert audit_resp.status_code == 200, audit_resp.text
    logs = audit_resp.json()
    assert any(log.get("action") == "recalls.export_csv" for log in logs)


def test_export_csv_respects_contact_filters(api_client, auth_headers):
    contacted_resp = api_client.get(
        "/recalls/export.csv",
        headers=auth_headers,
        params={"contact_state": "contacted"},
    )
    assert contacted_resp.status_code == 200, contacted_resp.text
    contacted_lines = contacted_resp.text.strip().splitlines()
    assert len(contacted_lines) > 1, "Expected rows for contacted recalls"

    never_resp = api_client.get(
        "/recalls/export.csv",
        headers=auth_headers,
        params={"contact_state": "never"},
    )
    assert never_resp.status_code == 200, never_resp.text
    never_lines = never_resp.text.strip().splitlines()
    assert len(never_lines) == 1, "Expected header-only CSV for never-contacted filter"


def _fetch_export_audit(
    client: httpx.Client,
    headers: dict[str, str],
    export_type: str,
) -> dict:
    response = client.get(
        "/audit",
        headers=headers,
        params={"entity_type": "recall_export", "entity_id": export_type, "limit": 1},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload, "Expected audit log entry"
    return payload[0]


def _assert_export_audit_payload(entry: dict, export_type: str):
    assert entry.get("entity_type") == "recall_export"
    assert entry.get("entity_id") == export_type
    after_json = entry.get("after_json") or {}
    assert after_json.get("export_type") == export_type
    assert isinstance(after_json.get("filters"), dict)
    for key in [
        "start",
        "end",
        "status",
        "type",
        "contact_state",
        "last_contact",
        "method",
        "contacted",
        "contacted_within_days",
        "contact_channel",
    ]:
        assert key in after_json["filters"]
    for key in [
        "page_only",
        "limit",
        "offset",
        "total",
        "exported_rows",
        "filename",
    ]:
        assert key in after_json


def test_export_csv_audit_entry(api_client, auth_headers):
    response = api_client.get("/recalls/export.csv", headers=auth_headers)
    assert response.status_code == 200, response.text
    entry = _fetch_export_audit(api_client, auth_headers, "csv")
    _assert_export_audit_payload(entry, "csv")


def test_export_csv_audit_includes_filters(api_client, auth_headers):
    response = api_client.get(
        "/recalls/export.csv",
        headers=auth_headers,
        params={"contact_state": "contacted", "last_contact": "7d"},
    )
    assert response.status_code == 200, response.text
    entry = _fetch_export_audit(api_client, auth_headers, "csv")
    filters = (entry.get("after_json") or {}).get("filters") or {}
    assert filters.get("contact_state") == "contacted"
    assert filters.get("last_contact") == "7d"


def test_export_letters_zip_audit_entry(api_client, auth_headers):
    response = api_client.get("/recalls/letters.zip", headers=auth_headers)
    assert response.status_code == 200, response.text
    entry = _fetch_export_audit(api_client, auth_headers, "letters_zip")
    _assert_export_audit_payload(entry, "letters_zip")


def test_sanitize_export_filename_strips_invalid_chars():
    raw = "recalls-2026-01-17/filtered:page?.csv"
    sanitized = recalls_router._sanitize_export_filename(raw)
    assert sanitized.endswith(".csv")
    _assert_safe_filename(sanitized)

    long_raw = f"{'a' * 200}.csv"
    truncated = recalls_router._sanitize_export_filename(long_raw)
    assert truncated.endswith(".csv")
    _assert_safe_filename(truncated)


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
        request = Request(
            scope={
                "type": "http",
                "headers": [],
                "client": ("testclient", 123),
            }
        )
        dummy_user = SimpleNamespace(id=1, email="audit@example.com")
        recalls_router.export_recalls_csv(
            request=request,
            db=DummyDB(),
            user=dummy_user,
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
