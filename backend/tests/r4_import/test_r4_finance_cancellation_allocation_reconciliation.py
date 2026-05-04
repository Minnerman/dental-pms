from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import pytest

from app.scripts import r4_finance_cancellation_allocation_reconciliation
from app.services.r4_import.finance_cancellation_allocation_reconciliation import (
    _read_only_query,
    run_cancellation_allocation_reconciliation,
)


class FakeCancellationAllocationSource:
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
        if "FROM dbo.vwPayments WITH (NOLOCK)" in sql and "WHERE [IsCancelled] = 1" in sql:
            return [
                {
                    "cancelled_row_count": 4,
                    "cancelled_total_amount": "0.00",
                    "cancelled_payment_count": 2,
                    "cancelled_refund_count": 1,
                    "cancelled_credit_count": 1,
                }
            ]
        if "FROM dbo.Adjustments c WITH (NOLOCK)" in sql and "COUNT(1)" in sql:
            return [
                {
                    "cancellation_of_count": 3,
                    "original_found_count": 2,
                    "original_missing_count": 1,
                    "patient_match_count": 1,
                    "patient_mismatch_count": 1,
                    "opposite_amount_match_count": 1,
                    "same_amount_match_count": 0,
                    "cancellation_after_or_same_count": 1,
                    "cancellation_before_original_count": 1,
                    "cancellation_total_amount": "50.00",
                    "paired_original_total_amount": "-40.00",
                    "paired_net_amount": "10.00",
                }
            ]
        if "FROM dbo.Adjustments c WITH (NOLOCK)" in sql and "SELECT TOP (?)" in sql:
            if "o.[RefId] IS NULL" in sql:
                return [
                    {
                        "cancellation_ref_id": 3003,
                        "cancellation_of": 1999,
                        "cancellation_patient_code": "P003",
                        "cancellation_at": datetime(2026, 1, 3),
                        "cancellation_amount": "25.00",
                        "cancellation_adjustment_type": 1,
                        "cancellation_payment_type": 2,
                        "cancellation_status": "Current",
                        "original_ref_id": None,
                        "original_patient_code": None,
                        "original_at": None,
                        "original_amount": None,
                        "original_adjustment_type": None,
                        "original_payment_type": None,
                        "original_status": None,
                        "net_amount": "25.00",
                    }
                ]
            if "NOT LTRIM" in sql or "c.[At] < o.[At]" in sql:
                return [
                    {
                        "cancellation_ref_id": 3002,
                        "cancellation_of": 2002,
                        "cancellation_patient_code": "P999",
                        "cancellation_at": datetime(2026, 1, 1),
                        "cancellation_amount": "20.00",
                        "cancellation_adjustment_type": 1,
                        "cancellation_payment_type": 2,
                        "cancellation_status": "Current",
                        "original_ref_id": 2002,
                        "original_patient_code": "P002",
                        "original_at": datetime(2026, 1, 2),
                        "original_amount": "-10.00",
                        "original_adjustment_type": 1,
                        "original_payment_type": 2,
                        "original_status": "Current",
                        "net_amount": "10.00",
                    }
                ]
            return [
                {
                    "cancellation_ref_id": 3001,
                    "cancellation_of": 2001,
                    "cancellation_patient_code": "P001",
                    "cancellation_at": datetime(2026, 1, 2),
                    "cancellation_amount": "50.00",
                    "cancellation_adjustment_type": 1,
                    "cancellation_payment_type": 2,
                    "cancellation_status": "Current",
                    "original_ref_id": 2001,
                    "original_patient_code": "P001",
                    "original_at": datetime(2026, 1, 1),
                    "original_amount": "-50.00",
                    "original_adjustment_type": 1,
                    "original_payment_type": 2,
                    "original_status": "Current",
                    "net_amount": "0.00",
                }
            ]
        if "vw_refunds_without_allocation_count" in sql:
            return [{"vw_refunds_without_allocation_count": 1}]
        if "FROM dbo.vwPayments WITH (NOLOCK)" in sql and "WHERE [IsRefund] = 1" in sql:
            return [
                {
                    "refund_count": 2,
                    "refund_total_amount": "80.00",
                    "cancelled_refund_count": 0,
                }
            ]
        if "FROM dbo.PaymentAllocations WITH (NOLOCK)" in sql and "WHERE [IsRefund] = 1" in sql:
            return [
                {
                    "refund_count": 5,
                    "refund_total_cost": "120.00",
                    "linked_payment_count": 5,
                    "missing_charge_ref_count": 5,
                }
            ]
        if "FROM dbo.vwAllocatedPayments WITH (NOLOCK)" in sql and "WHERE [IsRefund] = 1" in sql:
            return [
                {
                    "refund_count": 5,
                    "refund_total_cost": "120.00",
                    "linked_payment_count": 5,
                    "missing_charge_ref_count": 5,
                }
            ]
        if "FROM dbo.PaymentAllocations a WITH (NOLOCK)" in sql and "COUNT(1)" in sql:
            return [
                {
                    "allocation_refund_count": 5,
                    "matching_vw_refund_count": 1,
                    "without_matching_vw_refund_count": 4,
                    "patient_match_count": 1,
                    "patient_mismatch_count": 0,
                    "same_amount_match_count": 0,
                    "opposite_amount_match_count": 1,
                }
            ]
        if "FROM dbo.PaymentAllocations a WITH (NOLOCK)" in sql and "SELECT TOP (?)" in sql:
            if "p.[RefId] IS NULL" in sql:
                return [
                    {
                        "allocation_payment_id": 8001,
                        "allocation_patient_code": "P005",
                        "allocation_cost": "10.00",
                        "allocation_is_refund": 1,
                        "allocation_is_advanced_payment": 0,
                        "allocation_charge_transaction_ref_id": 0,
                        "allocation_charge_adjustment_ref_id": 0,
                        "payment_ref_id": None,
                        "payment_patient_code": None,
                        "payment_at": None,
                        "payment_amount": None,
                        "payment_type": None,
                        "payment_is_payment": None,
                        "payment_is_refund": None,
                        "payment_is_credit": None,
                        "payment_is_cancelled": None,
                    }
                ]
            return [
                {
                    "allocation_payment_id": 8000,
                    "allocation_patient_code": "P004",
                    "allocation_cost": "-30.00",
                    "allocation_is_refund": 1,
                    "allocation_is_advanced_payment": 0,
                    "allocation_charge_transaction_ref_id": 0,
                    "allocation_charge_adjustment_ref_id": 0,
                    "payment_ref_id": 7000,
                    "payment_patient_code": "P004",
                    "payment_at": datetime(2026, 2, 1),
                    "payment_amount": "30.00",
                    "payment_type": "Refund",
                    "payment_is_payment": 0,
                    "payment_is_refund": 1,
                    "payment_is_credit": 0,
                    "payment_is_cancelled": 0,
                }
            ]
        if "FROM dbo.vwPayments p WITH (NOLOCK)" in sql and "COUNT(1)" in sql:
            return [{"vw_refunds_without_allocation_count": 1}]
        if "FROM dbo.vwPayments p WITH (NOLOCK)" in sql and "SELECT TOP (?)" in sql:
            if "p.[IsCredit] = 1" in sql:
                return [
                    {
                        "RefId": 7101,
                        "PatientCode": "P007",
                        "At": datetime(2026, 2, 3),
                        "Amount": "-45.00",
                        "Type": "Credit",
                        "IsPayment": 0,
                        "IsRefund": 0,
                        "IsCredit": 1,
                        "IsCancelled": 0,
                    }
                ]
            return [
                {
                    "RefId": 7001,
                    "PatientCode": "P004",
                    "At": datetime(2026, 2, 2),
                    "Amount": "30.00",
                    "Type": "Refund",
                    "IsPayment": 0,
                    "IsRefund": 1,
                    "IsCredit": 0,
                    "IsCancelled": 0,
                }
            ]
        if "FROM dbo.vwPayments WITH (NOLOCK)" in sql and "WHERE [IsCredit] = 1" in sql:
            return [
                {
                    "credit_count": 3,
                    "credit_total_amount": "-45.00",
                    "cancelled_credit_count": 1,
                }
            ]
        if "FROM dbo.PaymentAllocations WITH (NOLOCK)" in sql and "COUNT(1)" in sql:
            return [
                {
                    "row_count": 6,
                    "total_cost": "100.00",
                    "refund_count": 5,
                    "advanced_payment_count": 2,
                    "linked_payment_count": 6,
                    "charge_ref_count": 0,
                    "missing_charge_ref_count": 6,
                }
            ]
        if "FROM dbo.vwAllocatedPayments WITH (NOLOCK)" in sql and "COUNT(1)" in sql:
            return [
                {
                    "row_count": 6,
                    "total_cost": "100.00",
                    "refund_count": 5,
                    "advanced_payment_count": 2,
                    "linked_payment_count": 6,
                    "charge_ref_count": 0,
                    "missing_charge_ref_count": 6,
                }
            ]
        if "FROM dbo.PaymentAllocations WITH (NOLOCK)" in sql and "SELECT TOP (?)" in sql:
            return [
                {
                    "PaymentID": 8002,
                    "PatientCode": "P006",
                    "Cost": "15.00",
                    "IsRefund": 0,
                    "IsAdvancedPayment": 1,
                    "IsAllocationAdjustment": 0,
                    "IsBalancingEntry": 0,
                    "ChargeTransactionRefID": 0,
                    "ChargeAdjustmentRefID": 0,
                }
            ]
        raise AssertionError(f"unexpected SQL: {sql}")


def test_cancellation_allocation_report_schema_and_cancellation_pairing():
    source = FakeCancellationAllocationSource()

    report = run_cancellation_allocation_reconciliation(source, sample_limit=2)

    assert report["select_only"] is True
    assert set(report) >= {
        "generated_at",
        "cancellation_pairing",
        "cancellation_impact",
        "refund_allocation_mismatch",
        "advanced_payment_credit_allocation",
        "classification_summary",
        "risks",
        "samples",
    }
    pairing = report["cancellation_pairing"]
    assert pairing["vw_payments_cancelled"]["cancelled_row_count"] == 4
    assert pairing["adjustments_cancellation_of"]["cancellation_of_count"] == 3
    assert pairing["adjustments_cancellation_of"]["original_found_count"] == 2
    assert pairing["adjustments_cancellation_of"]["original_missing_count"] == 1
    impact = report["cancellation_impact"]
    assert impact["paired_net_amount"] == "10.00"
    assert impact["paired_net_zero_within_tolerance"] is False
    assert source.ensure_count >= len(source.queries)


def test_refund_mismatch_and_allocation_blockers_are_reported():
    source = FakeCancellationAllocationSource()

    report = run_cancellation_allocation_reconciliation(source, sample_limit=2)

    refund = report["refund_allocation_mismatch"]
    assert refund["vw_payments_refunds"]["refund_count"] == 2
    assert refund["payment_allocations_refunds"]["refund_count"] == 5
    assert refund["overlap_by_payment_id_refid"]["matching_vw_refund_count"] == 1
    assert (
        refund["overlap_by_payment_id_refid"]["without_matching_vw_refund_count"]
        == 4
    )
    assert (
        refund["vw_refunds_without_allocation"][
            "vw_refunds_without_allocation_count"
        ]
        == 1
    )
    advanced = report["advanced_payment_credit_allocation"]
    assert advanced["vw_payments_credits"]["credit_count"] == 3
    assert advanced["payment_allocations"]["advanced_payment_count"] == 2
    assert advanced["payment_allocations"]["missing_charge_ref_count"] == 6
    assert any("refund count differs" in risk for risk in report["risks"])
    assert any("missing charge refs" in risk for risk in report["risks"])


def test_classification_summary_uses_policy_for_bounded_samples():
    source = FakeCancellationAllocationSource()

    report = run_cancellation_allocation_reconciliation(source, sample_limit=2)

    classification = report["classification_summary"]
    assert classification["sample_size"] > 0
    assert classification["classification_counts"]["cancellation_or_reversal"] >= 1
    assert classification["classification_counts"]["refund_candidate"] >= 1
    assert (
        classification["classification_counts"]["allocation_reconciliation_only"]
        >= 1
    )
    assert (
        classification["classification_counts"]["credit_candidate"]
        >= 1
    )
    assert "cancellation_of_present" in classification["reason_counts"]
    assert "allocation_charge_refs_missing" in classification["reason_counts"]
    assert all(
        sample["can_create_finance_record"] is False
        for sample in classification["sample_classifications"]
    )


def test_read_only_query_rejects_non_select_sql():
    source = FakeCancellationAllocationSource()

    with pytest.raises(RuntimeError, match="only permits SELECT"):
        _read_only_query(source, "UPDATE dbo.Adjustments SET Amount = 0")

    with pytest.raises(RuntimeError, match="refused a non-read-only query"):
        _read_only_query(
            source,
            "SELECT * FROM dbo.vwPayments; DELETE FROM dbo.vwPayments",
        )


def test_cancellation_allocation_cli_writes_json_without_pms_db(monkeypatch, tmp_path):
    fake_source = FakeCancellationAllocationSource()

    class FakeConfig:
        def require_enabled(self) -> None:
            pass

        def require_readonly(self) -> None:
            pass

    monkeypatch.setattr(
        r4_finance_cancellation_allocation_reconciliation.R4SqlServerConfig,
        "from_env",
        classmethod(lambda cls: FakeConfig()),
    )
    monkeypatch.setattr(
        r4_finance_cancellation_allocation_reconciliation,
        "R4SqlServerSource",
        lambda _config: fake_source,
    )
    output_path = tmp_path / "cancellation_allocation.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "r4_finance_cancellation_allocation_reconciliation",
            "--sample-limit",
            "2",
            "--output-json",
            str(output_path),
        ],
    )

    assert r4_finance_cancellation_allocation_reconciliation.main() == 0

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["select_only"] is True
    assert payload["cancellation_pairing"]["vw_payments_cancelled"][
        "cancelled_row_count"
    ] == 4
    assert payload["refund_allocation_mismatch"]["vw_payments_refunds"][
        "refund_count"
    ] == 2


def test_cancellation_allocation_files_do_not_contain_pms_db_or_write_paths():
    backend_root = Path(__file__).resolve().parents[2]
    files = [
        backend_root
        / "app/services/r4_import/finance_cancellation_allocation_reconciliation.py",
        backend_root
        / "app/scripts/r4_finance_cancellation_allocation_reconciliation.py",
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
