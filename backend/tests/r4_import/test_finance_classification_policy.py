from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from app.services.r4_import.finance_classification_policy import (
    R4FinanceClassification,
    R4FinancePmsDirection,
    R4FinanceRawSign,
    R4FinanceSafetyDecision,
    classify_finance_row,
    summarize_finance_classifications,
)


def test_patient_stats_balance_snapshot_classification_preserves_raw_sign():
    result = classify_finance_row(
        "dbo.PatientStats",
        {"PatientCode": 1001, "Balance": "-125.50"},
    )

    assert result.classification == R4FinanceClassification.BALANCE_SNAPSHOT_CANDIDATE
    assert result.safety_decision == R4FinanceSafetyDecision.RECONCILIATION_ONLY
    assert result.raw_amount == Decimal("-125.50")
    assert result.raw_sign == R4FinanceRawSign.NEGATIVE
    assert result.proposed_pms_direction == R4FinancePmsDirection.DECREASE_DEBT
    assert result.reason_codes == (
        "patient_stats_balance_snapshot",
        "negative_balance_probable_credit",
    )
    assert result.can_create_finance_record is False


def test_patient_stats_zero_balance_is_excluded_no_op():
    result = classify_finance_row(
        "PatientStats",
        {"PatientCode": 1001, "Balance": 0},
    )

    assert result.classification == R4FinanceClassification.EXCLUDED
    assert result.safety_decision == R4FinanceSafetyDecision.EXCLUDED
    assert result.raw_sign == R4FinanceRawSign.ZERO
    assert result.proposed_pms_direction == R4FinancePmsDirection.NO_CHANGE
    assert result.reason_codes == ("zero_balance_no_finance_action",)


def test_vw_payments_payment_row_is_candidate_with_negative_pms_direction():
    result = classify_finance_row(
        "vwPayments",
        {
            "PatientCode": 1001,
            "Amount": "-42.00",
            "Type": "Payment",
            "IsPayment": True,
            "IsRefund": False,
            "IsCredit": False,
            "IsCancelled": False,
        },
    )

    assert result.classification == R4FinanceClassification.PAYMENT_CANDIDATE
    assert result.safety_decision == R4FinanceSafetyDecision.CANDIDATE
    assert result.raw_sign == R4FinanceRawSign.NEGATIVE
    assert result.proposed_pms_direction == R4FinancePmsDirection.DECREASE_DEBT
    assert result.reason_codes == ("payment_candidate",)


def test_vw_payments_refund_row_is_candidate_with_positive_pms_direction():
    result = classify_finance_row(
        "payments",
        {
            "PatientCode": 1001,
            "Amount": "12.34",
            "Type": "Refund",
            "IsPayment": False,
            "IsRefund": 1,
            "IsCredit": False,
            "IsCancelled": False,
        },
    )

    assert result.classification == R4FinanceClassification.REFUND_CANDIDATE
    assert result.safety_decision == R4FinanceSafetyDecision.CANDIDATE
    assert result.raw_sign == R4FinanceRawSign.POSITIVE
    assert result.proposed_pms_direction == R4FinancePmsDirection.INCREASE_DEBT
    assert result.reason_codes == ("refund_candidate",)


def test_vw_payments_credit_row_is_candidate_without_using_sign_alone():
    result = classify_finance_row(
        "dbo.vwPayments",
        {
            "PatientCode": 1001,
            "Amount": "-9.99",
            "Type": "Credit",
            "IsPayment": False,
            "IsRefund": False,
            "IsCredit": "true",
            "IsCancelled": False,
        },
    )

    assert result.classification == R4FinanceClassification.CREDIT_CANDIDATE
    assert result.safety_decision == R4FinanceSafetyDecision.CANDIDATE
    assert result.raw_sign == R4FinanceRawSign.NEGATIVE
    assert result.proposed_pms_direction == R4FinancePmsDirection.DECREASE_DEBT
    assert result.reason_codes == ("credit_candidate",)


def test_vw_payments_cancelled_row_is_manual_review_not_candidate():
    result = classify_finance_row(
        "vwPayments",
        {
            "PatientCode": 1001,
            "Amount": "-42.00",
            "Type": "Payment",
            "IsPayment": True,
            "IsRefund": False,
            "IsCredit": False,
            "IsCancelled": True,
        },
    )

    assert result.classification == R4FinanceClassification.CANCELLATION_OR_REVERSAL
    assert result.safety_decision == R4FinanceSafetyDecision.MANUAL_REVIEW
    assert result.proposed_pms_direction is None
    assert result.reason_codes == ("cancelled_or_reversal_row",)


def test_adjustments_cancellation_of_row_is_manual_review():
    result = classify_finance_row(
        "Adjustments",
        {
            "PatientCode": 1001,
            "Amount": "-20.00",
            "AdjustmentType": 1,
            "Status": "CURRENT",
            "CancellationOf": 444,
        },
    )

    assert result.classification == R4FinanceClassification.CANCELLATION_OR_REVERSAL
    assert result.safety_decision == R4FinanceSafetyDecision.MANUAL_REVIEW
    assert result.reason_codes == ("cancellation_of_present",)


def test_adjustments_unknown_adjustment_type_fails_closed():
    result = classify_finance_row(
        "Adjustments",
        {
            "PatientCode": 1001,
            "Amount": "-20.00",
            "AdjustmentType": 99,
            "Status": "CURRENT",
        },
    )

    assert result.classification == R4FinanceClassification.MANUAL_REVIEW
    assert result.safety_decision == R4FinanceSafetyDecision.MANUAL_REVIEW
    assert result.reason_codes == ("unknown_adjustment_type",)


def test_transactions_are_reconciliation_only_not_invoice_truth():
    result = classify_finance_row(
        "Transactions",
        {
            "PatientCode": 1001,
            "PatientCost": "50.00",
            "DPBCost": "0.00",
        },
    )

    assert result.classification == R4FinanceClassification.TRANSACTION_RECONCILIATION_ONLY
    assert result.safety_decision == R4FinanceSafetyDecision.RECONCILIATION_ONLY
    assert result.raw_amount == Decimal("50.00")
    assert result.proposed_pms_direction is None
    assert result.reason_codes == (
        "transactions_not_invoice_truth",
        "transaction_reconciliation_only",
    )


def test_transactions_with_treatment_plan_fields_still_do_not_become_invoice_truth():
    result = classify_finance_row(
        "Transactions",
        {
            "PatientCode": 1001,
            "PatientCost": "75.00",
            "TPNumber": 77,
            "TPItem": 2,
            "PaymentAdjustmentID": 555,
        },
    )

    assert result.classification == R4FinanceClassification.TRANSACTION_RECONCILIATION_ONLY
    assert result.safety_decision == R4FinanceSafetyDecision.RECONCILIATION_ONLY
    assert result.reason_codes == (
        "transactions_not_invoice_truth",
        "transaction_reconciliation_only",
        "treatment_plan_link_present",
        "payment_adjustment_link_present",
    )


def test_payment_allocations_are_reconciliation_only():
    result = classify_finance_row(
        "PaymentAllocations",
        {
            "PatientCode": 1001,
            "Cost": "100.00",
            "PaymentID": 123,
            "ChargeTransactionRefID": 456,
            "IsRefund": False,
            "IsAdvancedPayment": True,
        },
    )

    assert result.classification == R4FinanceClassification.ALLOCATION_RECONCILIATION_ONLY
    assert result.safety_decision == R4FinanceSafetyDecision.RECONCILIATION_ONLY
    assert result.raw_amount == Decimal("100.00")
    assert result.reason_codes == (
        "allocation_reconciliation_only",
        "allocation_charge_refs_present",
        "allocation_advanced_payment_flag",
    )


def test_allocations_missing_charge_refs_fail_closed_for_invoice_application():
    result = classify_finance_row(
        "vwAllocatedPayments",
        {
            "PatientCode": 1001,
            "Cost": "25.00",
            "PaymentID": 123,
            "ChargeTransactionRefID": None,
            "ChargeAdjustmentRefID": None,
            "IsRefund": True,
        },
    )

    assert result.classification == R4FinanceClassification.ALLOCATION_RECONCILIATION_ONLY
    assert result.safety_decision == R4FinanceSafetyDecision.RECONCILIATION_ONLY
    assert "allocation_charge_refs_missing" in result.reason_codes
    assert "allocation_refund_flag" in result.reason_codes
    assert result.proposed_pms_direction is None


def test_lookup_reference_rows_are_reference_only():
    result = classify_finance_row(
        "PaymentTypes",
        {"PaymentType": 1, "Description": "Cash"},
    )

    assert result.classification == R4FinanceClassification.CLASSIFICATION_REFERENCE_ONLY
    assert result.safety_decision == R4FinanceSafetyDecision.REFERENCE_ONLY
    assert result.reason_codes == ("lookup_reference_only",)
    assert result.patient_code_present is False


def test_scheme_classification_rows_are_classification_only():
    result = classify_finance_row(
        "dbo.vwDenplan",
        {"PatientCode": 1001, "PatientStatus": "Active"},
    )

    assert result.classification == R4FinanceClassification.CLASSIFICATION_REFERENCE_ONLY
    assert result.safety_decision == R4FinanceSafetyDecision.REFERENCE_ONLY
    assert result.reason_codes == ("scheme_classification_only",)
    assert result.patient_code_present is True


def test_unknown_source_fails_closed():
    result = classify_finance_row(
        "dbo.UnknownFinanceTable",
        {"PatientCode": 1001, "Amount": "-10.00"},
    )

    assert result.classification == R4FinanceClassification.MANUAL_REVIEW
    assert result.safety_decision == R4FinanceSafetyDecision.MANUAL_REVIEW
    assert result.reason_codes == ("unknown_source",)


def test_missing_patient_code_fails_closed_for_ledger_candidate_sources():
    result = classify_finance_row(
        "vwPayments",
        {
            "PatientCode": " ",
            "Amount": "-42.00",
            "Type": "Payment",
            "IsPayment": True,
        },
    )

    assert result.classification == R4FinanceClassification.EXCLUDED
    assert result.safety_decision == R4FinanceSafetyDecision.EXCLUDED
    assert result.patient_code_present is False
    assert result.reason_codes == ("missing_patient_code",)


def test_ambiguous_payment_flags_are_manual_review():
    result = classify_finance_row(
        "vwPayments",
        {
            "PatientCode": 1001,
            "Amount": "-42.00",
            "Type": "Payment",
            "IsPayment": True,
            "IsRefund": True,
            "IsCredit": False,
        },
    )

    assert result.classification == R4FinanceClassification.MANUAL_REVIEW
    assert result.safety_decision == R4FinanceSafetyDecision.MANUAL_REVIEW
    assert result.reason_codes == ("ambiguous_payment_refund_credit_flags",)


def test_unexpected_payment_sign_is_manual_review():
    result = classify_finance_row(
        "vwPayments",
        {
            "PatientCode": 1001,
            "Amount": "42.00",
            "Type": "Payment",
            "IsPayment": True,
            "IsRefund": False,
            "IsCredit": False,
        },
    )

    assert result.classification == R4FinanceClassification.MANUAL_REVIEW
    assert result.safety_decision == R4FinanceSafetyDecision.MANUAL_REVIEW
    assert result.raw_sign == R4FinanceRawSign.POSITIVE
    assert result.reason_codes == ("payment_amount_sign_unexpected",)


def test_summary_aggregates_reason_codes_and_decisions():
    results = [
        classify_finance_row("PatientStats", {"PatientCode": 1001, "Balance": 10}),
        classify_finance_row("PatientStats", {"PatientCode": 1002, "Balance": 0}),
        classify_finance_row(
            "vwPayments",
            {"PatientCode": 1003, "Amount": "-5.00", "Type": "Payment", "IsPayment": True},
        ),
    ]

    report = summarize_finance_classifications(results)

    assert report.total == 3
    assert report.classification_counts == {
        "balance_snapshot_candidate": 1,
        "excluded": 1,
        "payment_candidate": 1,
    }
    assert report.safety_decision_counts == {
        "candidate": 1,
        "excluded": 1,
        "reconciliation_only": 1,
    }
    assert report.reason_counts == {
        "patient_stats_balance_snapshot": 1,
        "payment_candidate": 1,
        "positive_balance_probable_debt": 1,
        "zero_balance_no_finance_action": 1,
    }


def test_finance_classification_helper_has_no_db_session_or_r4_source_import():
    backend_root = Path(__file__).resolve().parents[2]
    source_text = (
        backend_root / "app/services/r4_import/finance_classification_policy.py"
    ).read_text(encoding="utf-8")

    assert "SessionLocal" not in source_text
    assert "get_db" not in source_text
    assert "R4SqlServerSource" not in source_text
