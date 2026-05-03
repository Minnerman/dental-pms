from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import pytest

from app.scripts import r4_finance_inventory
from app.scripts.r4_finance_inventory import _read_only_query, run_inventory


class FakeFinanceSource:
    select_only = True

    def __init__(self) -> None:
        self.queries: list[tuple[str, list[object]]] = []
        common_payment_columns = [
            "RefId",
            "PatientCode",
            "At",
            "Amount",
            "Type",
            "IsPayment",
            "IsRefund",
            "IsCredit",
            "IsCancelled",
            "PaymentTypeDescription",
            "AdjustmentTypeDescription",
        ]
        allocation_columns = [
            "PatientCode",
            "AllocationDate",
            "PaymentDate",
            "Cost",
            "IsRefund",
            "IsAdvancedPayment",
            "IsAllocationAdjustment",
            "IsBalancingEntry",
            "PaymentID",
            "ChargeTransactionRefID",
            "ChargeAdjustmentRefID",
            "PaymentTypeDesc",
        ]
        self.columns = {
            "PatientStats": [
                "PatientCode",
                "Balance",
                "TreatmentBalance",
                "SundriesBalance",
                "NHSBalance",
                "PrivateBalance",
                "DPBBalance",
                "CreditBalance",
                "AgeDebtor30To60",
                "AgeDebtor60To90",
                "AgeDebtor90Plus",
                "OutstandingSince",
            ],
            "vwPayments": common_payment_columns,
            "Adjustments": [
                "PatientCode",
                "At",
                "Amount",
                "AdjustmentType",
                "PaymentType",
                "Status",
                "CancellationOf",
            ],
            "Transactions": [
                "PatientCode",
                "Date",
                "PatientCost",
                "DPBCost",
                "PaymentAdjustmentID",
                "TPNumber",
                "TPItem",
                "UserCode",
            ],
            "PaymentAllocations": allocation_columns,
            "vwAllocatedPayments": allocation_columns,
            "PaymentTypes": ["PaymentType", "Description"],
            "OtherPaymentTypes": ["OtherPaymentTypeID", "Description"],
            "PaymentCardTypes": ["Id", "CardType", "Description", "Current"],
            "AdjustmentTypes": ["AdjustmentType", "Description"],
            "vwDenplan": ["PatientCode", "PatientStatus", "PaymentStatus", "FeeCode"],
            "DenplanPatients": ["ID", "PatientStatus", "PaymentStatus"],
            "NHSPatientDetails": ["PatientCode", "EthnicityCatID"],
        }

    def ensure_select_only(self) -> None:
        if not self.select_only:
            raise RuntimeError("not select-only")

    def _get_columns(self, table: str) -> list[str]:
        return self.columns.get(table, [])

    def _query(self, sql: str, params: list[object] | None = None):
        self.queries.append((sql, params or []))
        if "FROM dbo.PatientStats" in sql:
            if "balance_bucket" in sql:
                return [{"balance_bucket": "debt", "row_count": 2, "total_balance": 250}]
            if "SELECT TOP (?)" in sql:
                return [
                    {
                        "patient_code": 101,
                        "balance": 200,
                        "treatment_balance": 150,
                        "sundries_balance": 50,
                        "nhs_balance": 0,
                        "private_balance": 200,
                        "outstanding_since": datetime(2026, 1, 2, 9, 0),
                    }
                ]
            return [
                {
                    "row_count": 17,
                    "null_blank_patient_code_count": 0,
                    "nonzero_balance_count": 2,
                    "total_balance": 250,
                    "total_treatment_balance": 200,
                    "total_sundries_balance": 50,
                    "total_nhs_balance": 0,
                    "total_private_balance": 250,
                    "total_dpb_balance": 0,
                    "total_credit_balance": 0,
                    "aged_debt_30_to_60": 10,
                    "aged_debt_60_to_90": 20,
                    "aged_debt_90_plus": 30,
                    "min_outstanding_since": datetime(2025, 1, 1),
                    "max_outstanding_since": datetime(2026, 1, 1),
                }
            ]
        if "FROM dbo.vwPayments" in sql:
            if "GROUP BY [IsPayment]" in sql:
                return [
                    {
                        "is_payment": True,
                        "is_refund": False,
                        "is_credit": False,
                        "is_cancelled": False,
                        "row_count": 8,
                        "total_amount": -800,
                    }
                ]
            if "GROUP BY COALESCE" in sql:
                return [{"value": "Payment", "row_count": 8, "total_amount": -800}]
            if "SELECT TOP (?) [RefId] AS ref_id" in sql:
                return [
                    {
                        "ref_id": 1,
                        "patient_code": 101,
                        "at": datetime(2026, 5, 1, 10, 0),
                        "amount": -100,
                        "type": "Payment",
                        "is_payment": True,
                        "is_refund": False,
                        "is_credit": False,
                        "is_cancelled": True,
                        "payment_type_description": "Cash",
                        "adjustment_type_description": "PRI",
                    }
                ]
            return [
                {
                    "row_count": 12,
                    "null_blank_patient_code_count": 0,
                    "min_at": datetime(2025, 1, 1),
                    "max_at": datetime(2026, 5, 1),
                    "total_amount": -1200,
                    "cancellation_count": 1,
                    "payment_count": 8,
                    "refund_count": 1,
                    "credit_count": 3,
                }
            ]
        if "FROM dbo.Adjustments" in sql:
            if "GROUP BY [AdjustmentType]" in sql:
                return [
                    {
                        "adjustment_type": 1,
                        "payment_type": 1,
                        "status": "CURRENT",
                        "row_count": 8,
                        "total_amount": -800,
                    }
                ]
            return [
                {
                    "row_count": 13,
                    "null_blank_patient_code_count": 0,
                    "min_at": datetime(2025, 1, 1),
                    "max_at": datetime(2026, 5, 1),
                    "total_amount": -1300,
                    "cancellation_of_count": 1,
                }
            ]
        if "FROM dbo.Transactions" in sql:
            if "GROUP BY [UserCode]" in sql:
                return [{"user_code": 77, "row_count": 9, "total_patient_cost": 900, "total_dpb_cost": 0}]
            return [
                {
                    "row_count": 19,
                    "null_blank_patient_code_count": 0,
                    "min_date": datetime(2020, 1, 1),
                    "max_date": datetime(2026, 5, 2),
                    "total_patient_cost": 1900,
                    "total_dpb_cost": 20,
                    "payment_adjustment_id_count": 4,
                    "tp_number_count": 5,
                    "tp_item_count": 5,
                }
            ]
        if "FROM dbo.PaymentAllocations" in sql or "FROM dbo.vwAllocatedPayments" in sql:
            if "GROUP BY COALESCE" in sql:
                return [{"value": "Cash", "row_count": 4, "total_amount": 400}]
            return [
                {
                    "row_count": 4,
                    "null_blank_patient_code_count": 0,
                    "min_allocation_date": datetime(2020, 1, 1),
                    "max_allocation_date": datetime(2020, 2, 1),
                    "min_payment_date": datetime(2020, 1, 1),
                    "max_payment_date": datetime(2020, 2, 1),
                    "total_cost": 400,
                    "refund_count": 2,
                    "advanced_payment_count": 1,
                    "allocation_adjustment_count": 0,
                    "balancing_entry_count": 0,
                    "linked_payment_count": 4,
                    "charge_transaction_ref_count": 1,
                    "charge_adjustment_ref_count": 1,
                }
            ]
        if any(f"FROM dbo.{table}" in sql for table in ("PaymentTypes", "OtherPaymentTypes", "PaymentCardTypes", "AdjustmentTypes")):
            if "SELECT TOP (?)" in sql:
                return [{"lookup_key": 1, "lookup_value": "Cash", "lookup_current": True}]
            return [{"row_count": 3}]
        if "FROM dbo.vwDenplan" in sql:
            if "GROUP BY COALESCE" in sql:
                return [{"value": "1", "row_count": 3}]
            return [{"row_count": 3, "null_blank_patient_code_count": 0, "distinct_patient_codes": 3}]
        if "FROM dbo.DenplanPatients" in sql:
            if "GROUP BY COALESCE" in sql:
                return [{"value": "1", "row_count": 1}]
            return [{"row_count": 1, "distinct_ids": 1}]
        if "FROM dbo.NHSPatientDetails" in sql:
            if "GROUP BY COALESCE" in sql:
                return [{"value": "2", "row_count": 7}]
            return [{"row_count": 7, "null_blank_patient_code_count": 0, "distinct_patient_codes": 7}]
        raise AssertionError(f"unexpected SQL: {sql}")


def test_finance_inventory_report_schema_and_select_only_queries():
    source = FakeFinanceSource()

    report = run_inventory(source, sample_limit=2, top_limit=3)

    assert report["select_only"] is True
    assert set(report) >= {
        "generated_at",
        "select_only",
        "patient_stats",
        "payments",
        "adjustments",
        "transactions",
        "allocations",
        "lookup_tables",
        "scheme_classification",
        "risks",
    }
    assert report["patient_stats"]["summary"]["row_count"] == 17
    assert report["payments"]["summary"]["refund_count"] == 1
    assert report["adjustments"]["summary"]["cancellation_of_count"] == 1
    assert report["transactions"]["summary"]["payment_adjustment_id_count"] == 4
    assert report["allocations"]["payment_allocations"]["summary"]["refund_count"] == 2
    assert report["lookup_tables"]["payment_types"]["samples"][0]["lookup_value"] == "Cash"
    assert report["scheme_classification"]["vw_denplan"]["summary"]["row_count"] == 3
    assert "PatientStats" in report["query_shape"]["sources"].values()
    assert "vwPayments" in report["query_shape"]["sources"].values()

    assert source.queries
    for sql, _params in source.queries:
        normalized = sql.lstrip().upper()
        assert normalized.startswith("SELECT ")
        assert " WITH (NOLOCK)" in sql
        assert "INSERT" not in normalized
        assert "UPDATE" not in normalized
        assert "DELETE" not in normalized


def test_finance_inventory_rejects_non_select_query():
    source = FakeFinanceSource()

    with pytest.raises(RuntimeError, match="SELECT"):
        _read_only_query(source, "UPDATE dbo.PatientStats SET Balance = 0")


def test_finance_inventory_main_requires_readonly_and_writes_json(monkeypatch, tmp_path, capsys):
    source = FakeFinanceSource()
    calls: list[str] = []

    class FakeConfig:
        def require_enabled(self):
            calls.append("enabled")

        def require_readonly(self):
            calls.append("readonly")

    monkeypatch.setattr(
        r4_finance_inventory.R4SqlServerConfig,
        "from_env",
        staticmethod(lambda: FakeConfig()),
    )
    monkeypatch.setattr(r4_finance_inventory, "R4SqlServerSource", lambda _config: source)
    output_path = tmp_path / "finance_inventory.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "r4_finance_inventory",
            "--sample-limit",
            "2",
            "--top-limit",
            "3",
            "--output-json",
            str(output_path),
        ],
    )

    assert r4_finance_inventory.main() == 0

    assert calls == ["enabled", "readonly"]
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["select_only"] is True
    assert payload["payments"]["summary"]["row_count"] == 12
    stdout = json.loads(capsys.readouterr().out)
    assert stdout["output_json"] == str(output_path)


def test_finance_inventory_has_no_pms_db_session_import():
    source_text = Path(r4_finance_inventory.__file__).read_text(encoding="utf-8")

    assert "SessionLocal" not in source_text
    assert "app.db.session" not in source_text
