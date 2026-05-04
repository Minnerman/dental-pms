from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import pytest

from app.scripts import r4_opening_balance_reconciliation
from app.services.r4_import.opening_balance_reconciliation import (
    _read_only_query,
    run_opening_balance_reconciliation,
)


class FakeOpeningBalanceSource:
    select_only = True

    def __init__(self) -> None:
        self.queries: list[tuple[str, list[object]]] = []
        self.ensure_count = 0
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
            "vwPayments": [
                "Amount",
                "IsPayment",
                "IsRefund",
                "IsCredit",
                "IsCancelled",
            ],
            "Adjustments": ["Amount", "CancellationOf"],
            "Transactions": ["PatientCost", "DPBCost", "PaymentAdjustmentID"],
            "PaymentAllocations": [
                "Cost",
                "IsRefund",
                "IsAdvancedPayment",
                "ChargeTransactionRefID",
                "ChargeAdjustmentRefID",
            ],
            "vwAllocatedPayments": [
                "Cost",
                "IsRefund",
                "IsAdvancedPayment",
                "ChargeTransactionRefID",
                "ChargeAdjustmentRefID",
            ],
        }

    def ensure_select_only(self) -> None:
        self.ensure_count += 1
        if not self.select_only:
            raise RuntimeError("not select-only")

    def _get_columns(self, table: str) -> list[str]:
        return self.columns.get(table, [])

    def _query(self, sql: str, params: list[object] | None = None):
        self.queries.append((sql, params or []))
        if "FROM dbo.PatientStats" in sql:
            if "COUNT(DISTINCT" in sql:
                return [
                    {
                        "row_count": 6,
                        "distinct_patient_codes": 6,
                        "null_blank_patient_code_count": 0,
                        "null_balance_count": 0,
                        "zero_balance_count": 2,
                        "nonzero_balance_count": 4,
                        "debit_count": 2,
                        "credit_count": 2,
                        "total_balance": "-25.00",
                        "total_debit_balance": "175.00",
                        "total_credit_balance_rows": "-200.00",
                        "total_treatment_balance": "-30.00",
                        "total_sundries_balance": "5.00",
                        "total_nhs_balance": "20.00",
                        "total_private_balance": "-50.00",
                        "total_dpb_balance": "0.00",
                        "total_credit_balance": "0.00",
                        "aged_debt_30_to_60": "10.00",
                        "aged_debt_60_to_90": "20.00",
                        "aged_debt_90_plus": "30.00",
                        "total_aged_debt": "60.00",
                        "balance_component_mismatch_count": 1,
                        "max_balance_component_difference": "5.00",
                        "treatment_split_mismatch_count": 1,
                        "max_treatment_split_difference": "10.00",
                    }
                ]
            if "rows_with_aged_debt" in sql:
                return [
                    {
                        "aged_debt_30_to_60": "10.00",
                        "aged_debt_60_to_90": "20.00",
                        "aged_debt_90_plus": "30.00",
                        "total_aged_debt": "60.00",
                        "rows_with_aged_debt": 2,
                        "aged_debt_with_zero_balance_count": 1,
                        "balance_without_aged_debt_count": 2,
                    }
                ]
            if "COUNT(1) AS row_count" in sql and "SUM(CAST(ISNULL([Balance]" in sql:
                return [
                    {
                        "row_count": 6,
                        "total_balance": "-25.00",
                        "nonzero_balance_count": 4,
                    }
                ]
            if "SELECT TOP (?)" in sql:
                if "ISNULL([Balance], 0) > 0" in sql:
                    return [
                        {
                            "PatientCode": 101,
                            "Balance": "125.00",
                            "TreatmentBalance": "100.00",
                            "SundriesBalance": "25.00",
                            "NHSBalance": "0.00",
                            "PrivateBalance": "100.00",
                            "DPBBalance": "0.00",
                            "AgeDebtor30To60": "0.00",
                            "AgeDebtor60To90": "0.00",
                            "AgeDebtor90Plus": "0.00",
                            "OutstandingSince": datetime(2026, 1, 1),
                        }
                    ]
                if "ISNULL([Balance], 0) < 0" in sql:
                    return [
                        {
                            "PatientCode": 102,
                            "Balance": "-200.00",
                            "TreatmentBalance": "-200.00",
                            "SundriesBalance": "0.00",
                            "NHSBalance": "0.00",
                            "PrivateBalance": "-200.00",
                            "DPBBalance": "0.00",
                            "AgeDebtor30To60": "0.00",
                            "AgeDebtor60To90": "0.00",
                            "AgeDebtor90Plus": "0.00",
                            "OutstandingSince": datetime(2026, 2, 1),
                        }
                    ]
                if "[Balance] IS NOT NULL AND [Balance] = 0" in sql:
                    return [
                        {
                            "PatientCode": 103,
                            "Balance": "0.00",
                            "TreatmentBalance": "0.00",
                            "SundriesBalance": "0.00",
                            "NHSBalance": "0.00",
                            "PrivateBalance": "0.00",
                            "DPBBalance": "0.00",
                            "AgeDebtor30To60": "0.00",
                            "AgeDebtor60To90": "0.00",
                            "AgeDebtor90Plus": "0.00",
                            "OutstandingSince": None,
                        }
                    ]
                return [{"PatientCode": 104, "Balance": "5.00"}]
        if "FROM dbo.vwPayments" in sql:
            return [
                {
                    "row_count": 10,
                    "total_amount": "-500.00",
                    "payment_count": 8,
                    "refund_count": 1,
                    "credit_count": 1,
                    "cancellation_count": 1,
                }
            ]
        if "FROM dbo.Adjustments" in sql:
            return [
                {
                    "row_count": 11,
                    "total_amount": "-550.00",
                    "cancellation_of_count": 1,
                }
            ]
        if "FROM dbo.Transactions" in sql:
            return [
                {
                    "row_count": 12,
                    "total_patient_cost": "1000.00",
                    "total_dpb_cost": "5.00",
                    "payment_adjustment_id_count": 0,
                }
            ]
        if "FROM dbo.PaymentAllocations" in sql or "FROM dbo.vwAllocatedPayments" in sql:
            return [
                {
                    "row_count": 3,
                    "total_cost": "20.00",
                    "refund_count": 2,
                    "advanced_payment_count": 1,
                    "charge_transaction_ref_count": 0,
                    "charge_adjustment_ref_count": 0,
                }
            ]
        raise AssertionError(f"unexpected SQL: {sql}")


def test_opening_balance_report_schema_and_patient_stats_checks():
    source = FakeOpeningBalanceSource()

    report = run_opening_balance_reconciliation(source, sample_limit=2)

    assert report["select_only"] is True
    assert set(report) >= {
        "generated_at",
        "patient_stats_consistency",
        "aged_debt",
        "patient_linkage",
        "classification_summary",
        "cross_source_indicators",
        "risks",
        "samples",
    }
    patient_stats = report["patient_stats_consistency"]
    assert patient_stats["summary"]["row_count"] == 6
    assert patient_stats["summary"]["nonzero_balance_count"] == 4
    assert patient_stats["summary"]["total_balance"] == "-25.00"
    assert (
        patient_stats["component_checks"]["balance_equals_treatment_plus_sundries"][
            "mismatch_count"
        ]
        == 1
    )
    assert (
        patient_stats["component_checks"]["treatment_equals_nhs_private_dpb"][
            "passes"
        ]
        is False
    )
    assert report["patient_linkage"]["patient_code_blank_null_count"] == 0
    assert source.ensure_count >= len(source.queries)


def test_opening_balance_report_classifies_patient_stats_signs_and_samples():
    source = FakeOpeningBalanceSource()

    report = run_opening_balance_reconciliation(source, sample_limit=2)

    classification = report["classification_summary"]
    assert classification["classification_counts"] == {
        "balance_snapshot_candidate": 4,
        "excluded": 2,
        "manual_review": 0,
    }
    assert classification["raw_sign_counts"] == {
        "positive": 2,
        "negative": 2,
        "zero": 2,
        "unknown": 0,
    }
    sample_classes = classification["sample_classifications"]
    assert sample_classes[0]["classification"] == "balance_snapshot_candidate"
    assert sample_classes[0]["raw_sign"] == "positive"
    assert sample_classes[1]["proposed_pms_direction"] == "decrease_debt"
    assert sample_classes[2]["classification"] == "excluded"
    assert sample_classes[2]["reason_codes"] == ["zero_balance_no_finance_action"]


def test_opening_balance_report_aged_debt_and_cross_source_risks():
    source = FakeOpeningBalanceSource()

    report = run_opening_balance_reconciliation(source, sample_limit=2)

    aged = report["aged_debt"]
    assert aged["summary"]["total_aged_debt"] == "60.00"
    assert aged["summary"]["aged_debt_with_zero_balance_count"] == 1
    assert (
        aged["obvious_reconciliation"]["against_total_balance"][
            "matches_within_tolerance"
        ]
        is False
    )
    indicators = report["cross_source_indicators"]
    assert indicators["interpretation"].startswith("These are aggregate indicators only")
    assert indicators["payments"]["total_amount"] == "-500.00"
    assert indicators["transactions"]["total_patient_cost"] == "1000.00"
    assert (
        indicators["comparisons"]["patient_stats_balance_minus_vw_payments_amount"]
        == "475.00"
    )
    assert any("refund counts differ" in risk for risk in report["risks"])


def test_read_only_query_rejects_non_select_sql():
    source = FakeOpeningBalanceSource()

    with pytest.raises(RuntimeError, match="only permits SELECT"):
        _read_only_query(source, "UPDATE dbo.PatientStats SET Balance = 0")

    with pytest.raises(RuntimeError, match="refused a non-read-only query"):
        _read_only_query(
            source,
            "SELECT * FROM dbo.PatientStats; DELETE FROM dbo.PatientStats",
        )


def test_opening_balance_cli_writes_json_without_pms_db(monkeypatch, tmp_path):
    fake_source = FakeOpeningBalanceSource()

    class FakeConfig:
        def require_enabled(self) -> None:
            pass

        def require_readonly(self) -> None:
            pass

    monkeypatch.setattr(
        r4_opening_balance_reconciliation.R4SqlServerConfig,
        "from_env",
        classmethod(lambda cls: FakeConfig()),
    )
    monkeypatch.setattr(
        r4_opening_balance_reconciliation,
        "R4SqlServerSource",
        lambda _config: fake_source,
    )
    output_path = tmp_path / "opening_balance.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "r4_opening_balance_reconciliation",
            "--sample-limit",
            "2",
            "--output-json",
            str(output_path),
        ],
    )

    assert r4_opening_balance_reconciliation.main() == 0

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["select_only"] is True
    assert payload["patient_stats_consistency"]["summary"]["row_count"] == 6
    assert payload["patient_linkage"]["patient_code_present_count"] == 6


def test_opening_balance_files_do_not_contain_pms_db_or_write_paths():
    backend_root = Path(__file__).resolve().parents[2]
    files = [
        backend_root / "app/services/r4_import/opening_balance_reconciliation.py",
        backend_root / "app/scripts/r4_opening_balance_reconciliation.py",
    ]

    combined = "\n".join(path.read_text(encoding="utf-8") for path in files)

    assert "SessionLocal" not in combined
    assert "get_db" not in combined
    assert "PatientLedgerEntry(" not in combined
    assert "Invoice(" not in combined
    assert "Payment(" not in combined
    assert "commit(" not in combined
    assert "flush(" not in combined
