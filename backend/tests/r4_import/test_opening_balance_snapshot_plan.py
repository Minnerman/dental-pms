from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from app.services.r4_import.opening_balance_snapshot_plan import (
    OpeningBalancePlanDecision,
    OpeningBalancePmsDirection,
    OpeningBalanceRawSign,
    OpeningBalanceSafetyDecision,
    plan_opening_balance_snapshot_row,
    summarize_opening_balance_snapshot_plan,
)


def patient_stats_row(**overrides):
    row = {
        "PatientCode": "R4001",
        "Balance": "125.50",
        "TreatmentBalance": "100.00",
        "SundriesBalance": "25.50",
        "NHSBalance": "0.00",
        "PrivateBalance": "100.00",
        "DPBBalance": "0.00",
        "AgeDebtor30To60": "0.00",
        "AgeDebtor60To90": "0.00",
        "AgeDebtor90Plus": "0.00",
    }
    row.update(overrides)
    return row


def test_positive_patient_stats_balance_with_mapping_is_eligible_increase_debt():
    result = plan_opening_balance_snapshot_row(
        patient_stats_row(),
        {"R4001": 51},
    )

    assert result.decision == OpeningBalancePlanDecision.ELIGIBLE_OPENING_BALANCE
    assert result.safety_decision == OpeningBalanceSafetyDecision.CANDIDATE
    assert result.source_patient_code == "R4001"
    assert result.mapped_patient_id == 51
    assert result.raw_balance == Decimal("125.50")
    assert result.raw_component_fields["TreatmentBalance"] == Decimal("100.00")
    assert result.raw_sign == OpeningBalanceRawSign.POSITIVE
    assert result.amount_pence == 12550
    assert result.proposed_pms_direction == OpeningBalancePmsDirection.INCREASE_DEBT
    assert "eligible_opening_balance_candidate" in result.reason_codes
    assert "positive_balance_increase_debt" in result.reason_codes
    assert result.can_create_finance_record is False


def test_negative_patient_stats_balance_with_mapping_is_eligible_credit_direction():
    result = plan_opening_balance_snapshot_row(
        patient_stats_row(
            Balance="-42.25",
            TreatmentBalance="-40.00",
            SundriesBalance="-2.25",
            NHSBalance="0.00",
            PrivateBalance="-40.00",
            DPBBalance="0.00",
        ),
        {"R4001": 51},
    )

    assert result.decision == OpeningBalancePlanDecision.ELIGIBLE_OPENING_BALANCE
    assert result.raw_sign == OpeningBalanceRawSign.NEGATIVE
    assert result.amount_pence == -4225
    assert (
        result.proposed_pms_direction
        == OpeningBalancePmsDirection.DECREASE_DEBT_OR_CREDIT
    )
    assert "negative_balance_decrease_debt_or_credit" in result.reason_codes


def test_zero_patient_stats_balance_is_no_op_even_without_mapping():
    result = plan_opening_balance_snapshot_row(
        patient_stats_row(
            Balance="0.00",
            TreatmentBalance="0.00",
            SundriesBalance="0.00",
            NHSBalance="0.00",
            PrivateBalance="0.00",
            DPBBalance="0.00",
        ),
        {},
    )

    assert result.decision == OpeningBalancePlanDecision.NO_OP_ZERO_BALANCE
    assert result.safety_decision == OpeningBalanceSafetyDecision.NO_OP
    assert result.amount_pence == 0
    assert result.raw_sign == OpeningBalanceRawSign.ZERO
    assert result.proposed_pms_direction == OpeningBalancePmsDirection.NO_ACTION
    assert result.reason_codes == (
        "zero_balance_no_finance_action",
        "balance_component_check_passed",
        "treatment_split_check_passed",
    )


def test_missing_patient_code_fails_closed():
    result = plan_opening_balance_snapshot_row(
        patient_stats_row(PatientCode=" "),
        {"R4001": 51},
    )

    assert result.decision == OpeningBalancePlanDecision.INVALID_PATIENT_CODE
    assert result.safety_decision == OpeningBalanceSafetyDecision.EXCLUDED
    assert result.source_patient_code is None
    assert result.mapped_patient_id is None
    assert result.reason_codes == ("missing_patient_code",)


def test_missing_patient_mapping_for_nonzero_balance_fails_closed():
    result = plan_opening_balance_snapshot_row(
        patient_stats_row(),
        {"OTHER": 99},
    )

    assert result.decision == OpeningBalancePlanDecision.MISSING_PATIENT_MAPPING
    assert result.safety_decision == OpeningBalanceSafetyDecision.MANUAL_REVIEW
    assert result.amount_pence == 12550
    assert result.reason_codes == ("missing_patient_mapping",)


def test_component_checks_pass_for_balance_and_treatment_splits():
    result = plan_opening_balance_snapshot_row(
        patient_stats_row(),
        {"R4001": 51},
    )

    assert result.decision == OpeningBalancePlanDecision.ELIGIBLE_OPENING_BALANCE
    assert "balance_component_check_passed" in result.reason_codes
    assert "treatment_split_check_passed" in result.reason_codes


def test_balance_component_mismatch_fails_closed():
    result = plan_opening_balance_snapshot_row(
        patient_stats_row(SundriesBalance="20.00"),
        {"R4001": 51},
    )

    assert result.decision == OpeningBalancePlanDecision.COMPONENT_MISMATCH
    assert result.safety_decision == OpeningBalanceSafetyDecision.MANUAL_REVIEW
    assert result.reason_codes == ("balance_component_mismatch",)


def test_treatment_component_mismatch_fails_closed():
    result = plan_opening_balance_snapshot_row(
        patient_stats_row(PrivateBalance="99.00"),
        {"R4001": 51},
    )

    assert result.decision == OpeningBalancePlanDecision.COMPONENT_MISMATCH
    assert result.reason_codes == ("treatment_split_mismatch",)


def test_decimal_to_pence_exact_conversion_accepts_cents():
    result = plan_opening_balance_snapshot_row(
        patient_stats_row(Balance="125.50"),
        {"R4001": 51},
    )

    assert result.amount_pence == 12550


def test_decimal_rounding_risk_fails_closed():
    result = plan_opening_balance_snapshot_row(
        patient_stats_row(Balance="125.505"),
        {"R4001": 51},
    )

    assert result.decision == OpeningBalancePlanDecision.INVALID_AMOUNT
    assert result.safety_decision == OpeningBalanceSafetyDecision.MANUAL_REVIEW
    assert result.amount_pence is None
    assert result.reason_codes == ("balance_amount_not_exact_pence",)


def test_invalid_non_numeric_amount_fails_closed():
    result = plan_opening_balance_snapshot_row(
        patient_stats_row(Balance="not money"),
        {"R4001": 51},
    )

    assert result.decision == OpeningBalancePlanDecision.INVALID_AMOUNT
    assert result.raw_sign == OpeningBalanceRawSign.UNKNOWN
    assert result.reason_codes == ("balance_amount_missing_or_invalid",)


def test_aged_debt_metadata_is_preserved_but_not_required_for_eligibility():
    result = plan_opening_balance_snapshot_row(
        patient_stats_row(AgeDebtor30To60="10.00", AgeDebtor60To90="5.00"),
        {"R4001": 51},
    )

    assert result.decision == OpeningBalancePlanDecision.ELIGIBLE_OPENING_BALANCE
    assert result.raw_aged_debt_fields["AgeDebtor30To60"] == Decimal("10.00")
    assert result.raw_aged_debt_fields["AgeDebtor60To90"] == Decimal("5.00")


def test_balance_without_aged_debt_remains_eligible_when_other_checks_pass():
    result = plan_opening_balance_snapshot_row(
        patient_stats_row(
            AgeDebtor30To60="0.00",
            AgeDebtor60To90="0.00",
            AgeDebtor90Plus="0.00",
        ),
        {"R4001": 51},
    )

    assert result.decision == OpeningBalancePlanDecision.ELIGIBLE_OPENING_BALANCE
    assert "balance_without_aged_debt_metadata_only" in result.reason_codes


def test_aged_debt_with_zero_balance_remains_no_op_metadata_only():
    result = plan_opening_balance_snapshot_row(
        patient_stats_row(
            Balance="0.00",
            TreatmentBalance="0.00",
            SundriesBalance="0.00",
            NHSBalance="0.00",
            PrivateBalance="0.00",
            DPBBalance="0.00",
            AgeDebtor30To60="5.00",
        ),
        {},
    )

    assert result.decision == OpeningBalancePlanDecision.NO_OP_ZERO_BALANCE
    assert result.safety_decision == OpeningBalanceSafetyDecision.NO_OP
    assert "aged_debt_present_zero_balance_metadata_only" in result.reason_codes


def test_explicit_raw_sign_conflict_is_ambiguous_sign():
    result = plan_opening_balance_snapshot_row(
        patient_stats_row(RawSign="negative"),
        {"R4001": 51},
    )

    assert result.decision == OpeningBalancePlanDecision.AMBIGUOUS_SIGN
    assert result.safety_decision == OpeningBalanceSafetyDecision.MANUAL_REVIEW
    assert result.reason_codes == ("raw_sign_conflicts_with_balance",)


def test_unsupported_source_is_excluded():
    result = plan_opening_balance_snapshot_row(
        patient_stats_row(source_name="Transactions"),
        {"R4001": 51},
    )

    assert result.decision == OpeningBalancePlanDecision.EXCLUDED
    assert result.safety_decision == OpeningBalanceSafetyDecision.EXCLUDED
    assert result.reason_codes == ("unsupported_source",)


@dataclass(frozen=True)
class PatientStatsObject:
    PatientCode: str
    Balance: str
    TreatmentBalance: str
    SundriesBalance: str
    NHSBalance: str
    PrivateBalance: str
    DPBBalance: str
    AgeDebtor30To60: str = "0.00"
    AgeDebtor60To90: str = "0.00"
    AgeDebtor90Plus: str = "0.00"


def test_row_like_objects_are_supported_without_db_access():
    result = plan_opening_balance_snapshot_row(
        PatientStatsObject(
            PatientCode="OBJ1",
            Balance="1.00",
            TreatmentBalance="1.00",
            SundriesBalance="0.00",
            NHSBalance="0.00",
            PrivateBalance="1.00",
            DPBBalance="0.00",
        ),
        {"OBJ1": 7},
    )

    assert result.decision == OpeningBalancePlanDecision.ELIGIBLE_OPENING_BALANCE
    assert result.mapped_patient_id == 7
    assert result.amount_pence == 100


def test_summary_aggregates_decisions_reasons_signs_and_directions():
    rows = [
        plan_opening_balance_snapshot_row(patient_stats_row(), {"R4001": 51}),
        plan_opening_balance_snapshot_row(
            patient_stats_row(
                PatientCode="R4002",
                Balance="0.00",
                TreatmentBalance="0.00",
                SundriesBalance="0.00",
                NHSBalance="0.00",
                PrivateBalance="0.00",
                DPBBalance="0.00",
            ),
            {},
        ),
        plan_opening_balance_snapshot_row(
            patient_stats_row(PatientCode="R4003"),
            {},
        ),
    ]

    report = summarize_opening_balance_snapshot_plan(rows)

    assert report.total == 3
    assert report.decision_counts == {
        "eligible_opening_balance": 1,
        "missing_patient_mapping": 1,
        "no_op_zero_balance": 1,
    }
    assert report.safety_decision_counts == {
        "candidate": 1,
        "manual_review": 1,
        "no_op": 1,
    }
    assert report.raw_sign_counts == {"positive": 2, "zero": 1}
    assert report.proposed_pms_direction_counts == {
        "increase_debt": 2,
        "no_action": 1,
    }
    assert report.reason_counts["missing_patient_mapping"] == 1
    assert report.reason_counts["eligible_opening_balance_candidate"] == 1


def test_opening_balance_snapshot_plan_helper_has_no_db_or_r4_dependency():
    backend_root = Path(__file__).resolve().parents[2]
    source_text = (
        backend_root / "app/services/r4_import/opening_balance_snapshot_plan.py"
    ).read_text(encoding="utf-8")

    assert "SessionLocal" not in source_text
    assert "get_db" not in source_text
    assert "R4SqlServerSource" not in source_text
    assert "sqlalchemy" not in source_text.lower()
    assert "PatientLedgerEntry(" not in source_text
    assert "Invoice(" not in source_text
    assert "Payment(" not in source_text
    assert "commit(" not in source_text
    assert "flush(" not in source_text
