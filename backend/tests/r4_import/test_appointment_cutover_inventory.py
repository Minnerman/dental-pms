from __future__ import annotations

from datetime import date, datetime

import pytest

from app.scripts.r4_appointment_cutover_inventory import (
    _read_only_query,
    run_inventory,
)


class FakeAppointmentSource:
    select_only = True

    def __init__(self) -> None:
        self.queries: list[tuple[str, list[object]]] = []

    def ensure_select_only(self) -> None:
        if not self.select_only:
            raise RuntimeError("not select-only")

    def _require_column(self, _table: str, candidates: list[str]) -> str:
        return candidates[0]

    def _pick_column(self, _table: str, candidates: list[str]) -> str:
        return candidates[0]

    def _query(self, sql: str, params: list[object] | None = None):
        self.queries.append((sql, params or []))
        if "COUNT(1) AS total_count" in sql:
            return [
                {
                    "total_count": 5,
                    "past_count": 3,
                    "future_count": 2,
                    "min_start": datetime(2025, 1, 1, 9, 0),
                    "max_start": datetime(2026, 11, 18, 9, 0),
                    "null_start_count": 0,
                    "null_blank_patient_code_count": 1,
                    "cutover_day_count": 1,
                    "seven_days_before_count": 2,
                    "seven_days_after_count": 2,
                }
            ]
        if "DATEPART(year" in sql:
            return [{"year": 2025, "count": 3}, {"year": 2026, "count": 2}]
        if "CONVERT(char(7)" in sql:
            return [{"month": "2026-04", "count": 1}, {"month": "2026-11", "count": 1}]
        if "COUNT(DISTINCT" in sql:
            return [{"distinct_count": 2, "blank_count": 1}]
        if "GROUP BY" in sql:
            return [{"value": "Pending", "count": 3}, {"value": "<blank>", "count": 1}]
        if "SELECT TOP (?)" in sql:
            return [
                {
                    "appointment_id": 10,
                    "starts_at": datetime(2026, 4, 29, 9, 0),
                    "patient_code": None,
                    "status": "Odd",
                    "cancelled": False,
                    "clinician_code": 1001,
                    "clinic_code": 1,
                    "appt_flag": 7,
                }
            ]
        raise AssertionError(f"unexpected SQL: {sql}")


def test_appointment_cutover_inventory_uses_select_only_vw_appointment_details():
    source = FakeAppointmentSource()

    report = run_inventory(
        source,
        cutover_date=date(2026, 4, 29),
        sample_limit=2,
        top_limit=3,
    )

    assert report["counts"]["total_appointments"] == 5
    assert report["counts"]["past_appointments"] == 3
    assert report["counts"]["future_appointments"] == 2
    assert report["counts"]["null_blank_patient_code_count"] == 1
    assert report["date_range"] == {
        "min_start": "2025-01-01T09:00:00",
        "max_start": "2026-11-18T09:00:00",
    }
    assert report["cutover_boundary"]["cutover_day_count"] == 1
    assert report["distributions"]["status"]["top"][0] == {
        "value": "Pending",
        "count": 3,
    }
    assert report["samples"]["future_rows"][0]["appointment_id"] == 10

    assert source.queries
    for sql, _params in source.queries:
        normalized = sql.lstrip().upper()
        assert normalized.startswith("SELECT ")
        assert "FROM dbo.vwAppointmentDetails WITH (NOLOCK)" in sql
        assert "INSERT" not in normalized
        assert "UPDATE" not in normalized
        assert "DELETE" not in normalized


def test_appointment_cutover_inventory_rejects_non_select_query():
    source = FakeAppointmentSource()

    with pytest.raises(RuntimeError, match="SELECT"):
        _read_only_query(source, "UPDATE dbo.vwAppointmentDetails SET status = 'x'")
