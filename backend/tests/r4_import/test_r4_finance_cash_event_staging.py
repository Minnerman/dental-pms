from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import pytest

from app.scripts import r4_finance_cash_event_staging
from app.services.r4_import.finance_cash_event_staging import (
    _read_only_query,
    run_cash_event_staging_proof,
)


class FakeCashEventSource:
    select_only = True

    def __init__(self) -> None:
        self.queries: list[tuple[str, list[object]]] = []
        self.ensure_count = 0

    def ensure_select_only(self) -> None:
        self.ensure_count += 1
        if not self.select_only:
            raise RuntimeError("not select-only")

    def _query(self, sql: str, params: list[object] | None = None):
        self.queries.append((sql, params or []))
        if (
            "FROM dbo.vwPayments WITH (NOLOCK)" in sql
            and "COUNT(1) AS row_count" in sql
            and "GROUP BY" not in sql
            and "WHERE" not in sql
        ):
            return [
                {
                    "row_count": 16,
                    "distinct_patient_code_count": 12,
                    "null_blank_patient_code_count": 1,
                    "min_at": datetime(2025, 1, 1),
                    "max_at": datetime(2026, 5, 1),
                    "missing_date_count": 1,
                    "missing_amount_count": 1,
                    "zero_amount_count": 1,
                    "total_amount": "-1200.00",
                    "payment_flag_count": 9,
                    "refund_flag_count": 2,
                    "credit_flag_count": 3,
                    "cancellation_count": 1,
                    "ambiguous_flag_count": 1,
                    "missing_flag_count": 0,
                }
            ]
        if (
            "FROM dbo.Adjustments WITH (NOLOCK)" in sql
            and "COUNT(1) AS row_count" in sql
            and "GROUP BY" not in sql
        ):
            return [
                {
                    "row_count": 13,
                    "distinct_patient_code_count": 10,
                    "null_blank_patient_code_count": 0,
                    "min_at": datetime(2025, 1, 2),
                    "max_at": datetime(2026, 5, 2),
                    "missing_date_count": 0,
                    "missing_amount_count": 0,
                    "zero_amount_count": 0,
                    "total_amount": "-1300.00",
                    "cancellation_of_count": 1,
                    "current_status_count": 10,
                    "non_current_status_count": 2,
                }
            ]
        if "'vwPayments' AS source_name" in sql and "GROUP BY" in sql:
            return [
                _vw_bucket("negative", "Payment", 1, 0, 0, 0, 0, 8, "-800.00"),
                _vw_bucket("positive", "Refund", 0, 1, 0, 0, 0, 2, "80.00"),
                _vw_bucket("negative", "Credit", 0, 0, 1, 0, 0, 3, "-120.00"),
                _vw_bucket("negative", "Payment", 1, 0, 0, 1, 0, 1, "-50.00"),
                _vw_bucket("negative", "Payment", 1, 1, 0, 0, 0, 1, "-25.00"),
                _vw_bucket("negative", "Payment", 1, 0, 0, 0, 0, 1, "-10.00", patient=0),
            ]
        if "'Adjustments' AS source_name" in sql and "GROUP BY" in sql:
            return [
                _adjustment_bucket("negative", "Current", "1", "1", 1, 1, "-40.00"),
                _adjustment_bucket("negative", "Current", "1", "1", 0, 10, "-1000.00"),
                _adjustment_bucket("negative", "Deleted", "1", "1", 0, 2, "-200.00"),
            ]
        if "SELECT TOP (?) [RefId] AS ref_id" in sql:
            return [
                {
                    "ref_id": 7001,
                    "patient_code": "P001",
                    "at": datetime(2026, 5, 1, 10, 0),
                    "amount": "-100.00",
                    "type": "Payment",
                    "is_payment": 1,
                    "is_refund": 0,
                    "is_credit": 0,
                    "is_cancelled": 0,
                    "payment_type_description": "Cash",
                    "adjustment_type_description": "Private",
                }
            ]
        if "FROM dbo.Adjustments c WITH (NOLOCK)" in sql and "COUNT(1)" in sql:
            return [
                {
                    "cancellation_of_count": 1,
                    "original_found_count": 1,
                    "original_missing_count": 0,
                    "patient_match_count": 1,
                    "patient_mismatch_count": 0,
                    "opposite_amount_match_count": 1,
                    "cancellation_after_or_same_count": 1,
                    "cancellation_before_original_count": 0,
                    "cancellation_total_amount": "50.00",
                    "paired_original_total_amount": "-50.00",
                    "paired_net_amount": "0.00",
                }
            ]
        if "SELECT TOP (?) c.[RefId] AS cancellation_ref_id" in sql:
            return [
                {
                    "cancellation_ref_id": 3001,
                    "cancellation_of": 2001,
                    "cancellation_patient_code": "P002",
                    "cancellation_at": datetime(2026, 2, 2),
                    "cancellation_amount": "50.00",
                    "cancellation_adjustment_type": 1,
                    "cancellation_payment_type": 1,
                    "cancellation_status": "Current",
                    "original_ref_id": 2001,
                    "original_patient_code": "P002",
                    "original_at": datetime(2026, 2, 1),
                    "original_amount": "-50.00",
                    "original_adjustment_type": 1,
                    "original_payment_type": 1,
                    "original_status": "Current",
                    "net_amount": "0.00",
                }
            ]
        if "FROM dbo.vwPayments WITH (NOLOCK)" in sql and "WHERE [IsRefund] = 1" in sql:
            return [
                {
                    "refund_row_count": 2,
                    "refund_total_amount": "80.00",
                    "refund_candidate_count": 2,
                    "cancelled_refund_count": 0,
                    "unexpected_sign_or_missing_amount_count": 0,
                    "missing_date_count": 0,
                    "null_blank_patient_code_count": 0,
                }
            ]
        if "FROM dbo.PaymentAllocations a WITH (NOLOCK)" in sql and "COUNT(1)" in sql:
            return [
                {
                    "allocation_refund_count": 5,
                    "matching_vw_refund_count": 1,
                    "allocation_refunds_without_vw_refund_count": 4,
                    "patient_match_count": 1,
                    "patient_mismatch_count": 0,
                    "opposite_amount_match_count": 1,
                }
            ]
        if "vw_refunds_without_allocation_count" in sql:
            return [{"vw_refunds_without_allocation_count": 1}]
        if "FROM dbo.vwPayments WITH (NOLOCK)" in sql and "WHERE [IsCredit] = 1" in sql:
            return [
                {
                    "credit_row_count": 3,
                    "credit_total_amount": "-120.00",
                    "credit_candidate_count": 3,
                    "cancelled_credit_count": 0,
                    "unexpected_sign_or_missing_amount_count": 0,
                }
            ]
        if (
            "FROM dbo.PaymentAllocations WITH (NOLOCK)" in sql
            and "WHERE [IsAdvancedPayment] = 1" in sql
        ):
            return [
                {
                    "advanced_payment_allocation_count": 4,
                    "advanced_payment_total_cost": "200.00",
                    "linked_payment_count": 4,
                }
            ]
        if "FROM dbo.vwPayments WITH (NOLOCK)" in sql and "GROUP BY COALESCE" in sql:
            return [{"value": "Payment", "row_count": 8, "total_amount": "-800.00"}]
        if "method_family" in sql:
            return [{"method_family": "cash", "row_count": 8, "total_amount": "-800.00"}]
        if "FROM dbo.Adjustments WITH (NOLOCK)" in sql and "GROUP BY [AdjustmentType]" in sql:
            return [
                {
                    "adjustment_type": 1,
                    "payment_type": 1,
                    "status": "Current",
                    "row_count": 10,
                    "total_amount": "-1000.00",
                }
            ]
        raise AssertionError(f"unexpected SQL: {sql}")


def _vw_bucket(
    amount_state: str,
    type_name: str,
    is_payment: int,
    is_refund: int,
    is_credit: int,
    is_cancelled: int,
    cancellation_of: int,
    row_count: int,
    total_amount: str,
    *,
    patient: int = 1,
    date: int = 1,
) -> dict[str, object]:
    return {
        "source_name": "vwPayments",
        "patient_code_present": patient,
        "date_present": date,
        "amount_state": amount_state,
        "type": type_name,
        "is_payment": is_payment,
        "is_refund": is_refund,
        "is_credit": is_credit,
        "is_cancelled": is_cancelled,
        "cancellation_of_present": cancellation_of,
        "row_count": row_count,
        "total_amount": total_amount,
        "min_at": datetime(2025, 1, 1),
        "max_at": datetime(2026, 5, 1),
    }


def _adjustment_bucket(
    amount_state: str,
    status: str,
    adjustment_type: str,
    payment_type: str,
    cancellation_of: int,
    row_count: int,
    total_amount: str,
) -> dict[str, object]:
    return {
        "source_name": "Adjustments",
        "patient_code_present": 1,
        "date_present": 1,
        "amount_state": amount_state,
        "status": status,
        "adjustment_type": adjustment_type,
        "payment_type": payment_type,
        "cancellation_of_present": cancellation_of,
        "row_count": row_count,
        "total_amount": total_amount,
        "min_at": datetime(2025, 1, 2),
        "max_at": datetime(2026, 5, 2),
    }


def test_cash_event_report_schema_and_candidate_population():
    source = FakeCashEventSource()

    report = run_cash_event_staging_proof(source, sample_limit=2, top_limit=2)

    assert report["select_only"] is True
    assert set(report) >= {
        "generated_at",
        "candidate_population",
        "cancellation_pairing",
        "refund_handling",
        "credit_handling",
        "payment_type_mapping",
        "classification_summary",
        "import_readiness",
        "risks",
        "samples",
    }
    population = report["candidate_population"]
    assert population["vw_payments_summary"]["row_count"] == 16
    assert population["adjustments_summary"]["row_count"] == 13
    assert population["eligible_cash_event_candidate_count"] == 13
    assert population["payment_candidate_count"] == 8
    assert population["refund_candidate_count"] == 2
    assert population["credit_candidate_count"] == 3
    assert population["excluded_count"] == 1
    assert population["cancellation_or_reversal_count"] == 2
    assert source.ensure_count >= len(source.queries)


def test_cancellation_refund_credit_and_import_gate_are_reported():
    source = FakeCashEventSource()

    report = run_cash_event_staging_proof(source, sample_limit=2, top_limit=2)

    pairing = report["cancellation_pairing"]
    assert pairing["summary"]["cancellation_of_count"] == 1
    assert pairing["summary"]["original_found_count"] == 1
    assert pairing["summary"]["original_missing_count"] == 0
    assert pairing["paired_net_zero_within_tolerance"] is True
    refund = report["refund_handling"]
    assert refund["vw_payments_refunds"]["refund_candidate_count"] == 2
    assert refund["allocation_refund_overlap"]["allocation_refund_count"] == 5
    assert (
        refund["allocation_refund_overlap"][
            "allocation_refunds_without_vw_refund_count"
        ]
        == 4
    )
    credit = report["credit_handling"]
    assert credit["vw_payments_credits"]["credit_candidate_count"] == 3
    assert credit["advanced_payment_allocations"][
        "advanced_payment_allocation_count"
    ] == 4
    assert report["import_readiness"]["finance_import_ready"] is False
    assert any("PaymentAllocations remain reconciliation-only" in risk for risk in report["risks"])


def test_classification_summary_preserves_raw_signs_and_blocks_writes():
    source = FakeCashEventSource()

    report = run_cash_event_staging_proof(source, sample_limit=2, top_limit=2)

    classification = report["classification_summary"]
    assert classification["classification_counts"]["payment_candidate"] == 8
    assert classification["classification_counts"]["refund_candidate"] == 2
    assert classification["classification_counts"]["credit_candidate"] == 3
    assert classification["classification_counts"]["cancellation_or_reversal"] == 2
    assert classification["classification_counts"]["manual_review"] >= 1
    assert classification["classification_counts"]["excluded"] == 1
    assert classification["raw_sign_counts"]["negative"] >= 1
    assert classification["proposed_pms_direction_counts"]["decrease_debt"] == 11
    assert classification["proposed_pms_direction_counts"]["increase_debt"] == 2
    assert "adjustments_base_cross_check_only" in classification["reason_counts"]
    assert all(
        sample["can_create_finance_record"] is False
        for sample in classification["sample_classifications"]
    )


def test_read_only_query_rejects_non_select_sql():
    source = FakeCashEventSource()

    with pytest.raises(RuntimeError, match="only permits SELECT"):
        _read_only_query(source, "UPDATE dbo.vwPayments SET Amount = 0")

    with pytest.raises(RuntimeError, match="refused a non-read-only query"):
        _read_only_query(
            source,
            "SELECT * FROM dbo.vwPayments; DELETE FROM dbo.vwPayments",
        )


def test_cash_event_cli_writes_json_without_pms_db(monkeypatch, tmp_path):
    fake_source = FakeCashEventSource()

    class FakeConfig:
        def require_enabled(self) -> None:
            pass

        def require_readonly(self) -> None:
            pass

    monkeypatch.setattr(
        r4_finance_cash_event_staging.R4SqlServerConfig,
        "from_env",
        classmethod(lambda cls: FakeConfig()),
    )
    monkeypatch.setattr(
        r4_finance_cash_event_staging,
        "R4SqlServerSource",
        lambda _config: fake_source,
    )
    output_path = tmp_path / "cash_event_staging.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "r4_finance_cash_event_staging",
            "--sample-limit",
            "2",
            "--top-limit",
            "2",
            "--output-json",
            str(output_path),
        ],
    )

    assert r4_finance_cash_event_staging.main() == 0

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["select_only"] is True
    assert payload["candidate_population"][
        "eligible_cash_event_candidate_count"
    ] == 13
    assert payload["import_readiness"]["finance_import_ready"] is False


def test_cash_event_files_do_not_contain_pms_db_or_write_paths():
    backend_root = Path(__file__).resolve().parents[2]
    files = [
        backend_root / "app/services/r4_import/finance_cash_event_staging.py",
        backend_root / "app/scripts/r4_finance_cash_event_staging.py",
    ]

    combined = "\n".join(path.read_text(encoding="utf-8") for path in files)

    assert "SessionLocal" not in combined
    assert "get_db" not in combined
    assert "PatientLedgerEntry(" not in combined
    assert "Invoice(" not in combined
    assert "Payment(" not in combined
    assert "commit(" not in combined
    assert "flush(" not in combined
    assert ".add(" not in combined
