from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, Iterable, Mapping

__all__ = [
    "R4FinanceClassification",
    "R4FinanceClassificationReport",
    "R4FinanceClassificationResult",
    "R4FinancePmsDirection",
    "R4FinanceRawSign",
    "R4FinanceSafetyDecision",
    "classify_finance_row",
    "summarize_finance_classifications",
]


class R4FinanceClassification(str, Enum):
    BALANCE_SNAPSHOT_CANDIDATE = "balance_snapshot_candidate"
    PAYMENT_CANDIDATE = "payment_candidate"
    REFUND_CANDIDATE = "refund_candidate"
    CREDIT_CANDIDATE = "credit_candidate"
    CANCELLATION_OR_REVERSAL = "cancellation_or_reversal"
    ALLOCATION_RECONCILIATION_ONLY = "allocation_reconciliation_only"
    TRANSACTION_RECONCILIATION_ONLY = "transaction_reconciliation_only"
    CLASSIFICATION_REFERENCE_ONLY = "classification_reference_only"
    MANUAL_REVIEW = "manual_review"
    EXCLUDED = "excluded"


class R4FinanceSafetyDecision(str, Enum):
    CANDIDATE = "candidate"
    RECONCILIATION_ONLY = "reconciliation_only"
    REFERENCE_ONLY = "reference_only"
    MANUAL_REVIEW = "manual_review"
    EXCLUDED = "excluded"


class R4FinanceRawSign(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    ZERO = "zero"
    UNKNOWN = "unknown"


class R4FinancePmsDirection(str, Enum):
    INCREASE_DEBT = "increase_debt"
    DECREASE_DEBT = "decrease_debt"
    NO_CHANGE = "no_change"


@dataclass(frozen=True)
class R4FinanceClassificationResult:
    source_name: str
    classification: R4FinanceClassification
    safety_decision: R4FinanceSafetyDecision
    reason_codes: tuple[str, ...]
    raw_amount: Decimal | None
    raw_sign: R4FinanceRawSign
    proposed_pms_direction: R4FinancePmsDirection | None
    patient_code_present: bool

    @property
    def can_create_finance_record(self) -> bool:
        return False


@dataclass(frozen=True)
class R4FinanceClassificationReport:
    rows: tuple[R4FinanceClassificationResult, ...]
    classification_counts: dict[str, int]
    safety_decision_counts: dict[str, int]
    reason_counts: dict[str, int]

    @property
    def total(self) -> int:
        return len(self.rows)


_SOURCE_ALIASES = {
    "patientstats": "PatientStats",
    "patient_stats": "PatientStats",
    "vwpayments": "vwPayments",
    "payments": "vwPayments",
    "adjustments": "Adjustments",
    "transactions": "Transactions",
    "paymentallocations": "PaymentAllocations",
    "payment_allocations": "PaymentAllocations",
    "vwallocatedpayments": "vwAllocatedPayments",
    "allocated_payments_view": "vwAllocatedPayments",
    "paymenttypes": "PaymentTypes",
    "payment_types": "PaymentTypes",
    "otherpaymenttypes": "OtherPaymentTypes",
    "other_payment_types": "OtherPaymentTypes",
    "paymentcardtypes": "PaymentCardTypes",
    "payment_card_types": "PaymentCardTypes",
    "adjustmenttypes": "AdjustmentTypes",
    "adjustment_types": "AdjustmentTypes",
    "vwdenplan": "vwDenplan",
    "denplan_view": "vwDenplan",
    "denplanpatients": "DenplanPatients",
    "denplan_patients": "DenplanPatients",
    "nhspatientdetails": "NHSPatientDetails",
    "nhs_patient_details": "NHSPatientDetails",
}

_PATIENT_REQUIRED_SOURCES = {
    "PatientStats",
    "vwPayments",
    "Adjustments",
    "Transactions",
    "PaymentAllocations",
    "vwAllocatedPayments",
}

_REFERENCE_SOURCES = {
    "PaymentTypes",
    "OtherPaymentTypes",
    "PaymentCardTypes",
    "AdjustmentTypes",
}

_CLASSIFICATION_SOURCES = {
    "vwDenplan",
    "DenplanPatients",
    "NHSPatientDetails",
}

_KNOWN_PAYMENT_TYPES = {"payment", "refund", "credit"}
_KNOWN_ADJUSTMENT_TYPES = {"1", "2", "3"}


def classify_finance_row(
    source_name: str,
    row: Mapping[str, Any] | Any,
) -> R4FinanceClassificationResult:
    source = _normalize_source_name(source_name)
    if source is None:
        return _result(
            source_name=source_name,
            classification=R4FinanceClassification.MANUAL_REVIEW,
            safety_decision=R4FinanceSafetyDecision.MANUAL_REVIEW,
            reason_codes=("unknown_source",),
            raw_amount=None,
            patient_code_present=False,
        )

    if source in _REFERENCE_SOURCES:
        return _reference_result(source, row, reason="lookup_reference_only")
    if source in _CLASSIFICATION_SOURCES:
        return _reference_result(source, row, reason="scheme_classification_only")

    patient_code_present = _has_value(_field(row, "PatientCode", "patient_code"))
    if source in _PATIENT_REQUIRED_SOURCES and not patient_code_present:
        return _result(
            source_name=source,
            classification=R4FinanceClassification.EXCLUDED,
            safety_decision=R4FinanceSafetyDecision.EXCLUDED,
            reason_codes=("missing_patient_code",),
            raw_amount=_raw_amount_for_source(source, row),
            patient_code_present=False,
        )

    if source == "PatientStats":
        return _classify_patient_stats(source, row)
    if source == "vwPayments":
        return _classify_vw_payments(source, row)
    if source == "Adjustments":
        return _classify_adjustments(source, row)
    if source == "Transactions":
        return _classify_transactions(source, row)
    if source in {"PaymentAllocations", "vwAllocatedPayments"}:
        return _classify_allocations(source, row)

    return _result(
        source_name=source,
        classification=R4FinanceClassification.MANUAL_REVIEW,
        safety_decision=R4FinanceSafetyDecision.MANUAL_REVIEW,
        reason_codes=("unhandled_source",),
        raw_amount=_raw_amount_for_source(source, row),
        patient_code_present=patient_code_present,
    )


def summarize_finance_classifications(
    results: Iterable[R4FinanceClassificationResult],
) -> R4FinanceClassificationReport:
    rows = tuple(results)
    classification_counts = Counter(row.classification.value for row in rows)
    safety_decision_counts = Counter(row.safety_decision.value for row in rows)
    reason_counts: Counter[str] = Counter()
    for row in rows:
        reason_counts.update(row.reason_codes)
    return R4FinanceClassificationReport(
        rows=rows,
        classification_counts=dict(sorted(classification_counts.items())),
        safety_decision_counts=dict(sorted(safety_decision_counts.items())),
        reason_counts=dict(sorted(reason_counts.items())),
    )


def _classify_patient_stats(
    source: str,
    row: Mapping[str, Any] | Any,
) -> R4FinanceClassificationResult:
    amount = _amount(_field(row, "Balance", "balance"))
    sign = _raw_sign(amount)
    if sign == R4FinanceRawSign.UNKNOWN:
        return _result(
            source_name=source,
            classification=R4FinanceClassification.MANUAL_REVIEW,
            safety_decision=R4FinanceSafetyDecision.MANUAL_REVIEW,
            reason_codes=("balance_amount_missing_or_invalid",),
            raw_amount=amount,
            patient_code_present=True,
        )
    if sign == R4FinanceRawSign.ZERO:
        return _result(
            source_name=source,
            classification=R4FinanceClassification.EXCLUDED,
            safety_decision=R4FinanceSafetyDecision.EXCLUDED,
            reason_codes=("zero_balance_no_finance_action",),
            raw_amount=amount,
            proposed_pms_direction=R4FinancePmsDirection.NO_CHANGE,
            patient_code_present=True,
        )
    direction = (
        R4FinancePmsDirection.INCREASE_DEBT
        if sign == R4FinanceRawSign.POSITIVE
        else R4FinancePmsDirection.DECREASE_DEBT
    )
    reason = (
        "positive_balance_probable_debt"
        if sign == R4FinanceRawSign.POSITIVE
        else "negative_balance_probable_credit"
    )
    return _result(
        source_name=source,
        classification=R4FinanceClassification.BALANCE_SNAPSHOT_CANDIDATE,
        safety_decision=R4FinanceSafetyDecision.RECONCILIATION_ONLY,
        reason_codes=("patient_stats_balance_snapshot", reason),
        raw_amount=amount,
        proposed_pms_direction=direction,
        patient_code_present=True,
    )


def _classify_vw_payments(
    source: str,
    row: Mapping[str, Any] | Any,
) -> R4FinanceClassificationResult:
    amount = _amount(_field(row, "Amount", "amount"))
    reasons: list[str] = []
    if _bool_field(row, "IsCancelled", "is_cancelled") or _has_value(
        _field(row, "CancellationOf", "cancellation_of")
    ):
        return _result(
            source_name=source,
            classification=R4FinanceClassification.CANCELLATION_OR_REVERSAL,
            safety_decision=R4FinanceSafetyDecision.MANUAL_REVIEW,
            reason_codes=("cancelled_or_reversal_row",),
            raw_amount=amount,
            patient_code_present=True,
        )

    row_type = _normalized_text(_field(row, "Type", "type"))
    if row_type and row_type not in _KNOWN_PAYMENT_TYPES:
        return _result(
            source_name=source,
            classification=R4FinanceClassification.MANUAL_REVIEW,
            safety_decision=R4FinanceSafetyDecision.MANUAL_REVIEW,
            reason_codes=("unknown_payment_type",),
            raw_amount=amount,
            patient_code_present=True,
        )

    flag_kinds = _payment_flag_kinds(row)
    if len(flag_kinds) > 1:
        return _result(
            source_name=source,
            classification=R4FinanceClassification.MANUAL_REVIEW,
            safety_decision=R4FinanceSafetyDecision.MANUAL_REVIEW,
            reason_codes=("ambiguous_payment_refund_credit_flags",),
            raw_amount=amount,
            patient_code_present=True,
        )

    kind = next(iter(flag_kinds), None)
    if kind is None:
        kind = row_type
        if kind:
            reasons.append("classified_from_type_only")
    elif row_type and row_type != kind:
        return _result(
            source_name=source,
            classification=R4FinanceClassification.MANUAL_REVIEW,
            safety_decision=R4FinanceSafetyDecision.MANUAL_REVIEW,
            reason_codes=("payment_type_flag_conflict",),
            raw_amount=amount,
            patient_code_present=True,
        )

    if kind == "payment":
        return _payment_like_result(
            source=source,
            classification=R4FinanceClassification.PAYMENT_CANDIDATE,
            expected_sign=R4FinanceRawSign.NEGATIVE,
            amount=amount,
            reason_codes=tuple(reasons + ["payment_candidate"]),
            proposed_pms_direction=R4FinancePmsDirection.DECREASE_DEBT,
            unexpected_reason="payment_amount_sign_unexpected",
        )
    if kind == "refund":
        return _payment_like_result(
            source=source,
            classification=R4FinanceClassification.REFUND_CANDIDATE,
            expected_sign=R4FinanceRawSign.POSITIVE,
            amount=amount,
            reason_codes=tuple(reasons + ["refund_candidate"]),
            proposed_pms_direction=R4FinancePmsDirection.INCREASE_DEBT,
            unexpected_reason="refund_amount_sign_unexpected",
        )
    if kind == "credit":
        return _payment_like_result(
            source=source,
            classification=R4FinanceClassification.CREDIT_CANDIDATE,
            expected_sign=R4FinanceRawSign.NEGATIVE,
            amount=amount,
            reason_codes=tuple(reasons + ["credit_candidate"]),
            proposed_pms_direction=R4FinancePmsDirection.DECREASE_DEBT,
            unexpected_reason="credit_amount_sign_unexpected",
        )

    return _result(
        source_name=source,
        classification=R4FinanceClassification.MANUAL_REVIEW,
        safety_decision=R4FinanceSafetyDecision.MANUAL_REVIEW,
        reason_codes=("missing_payment_type_flags",),
        raw_amount=amount,
        patient_code_present=True,
    )


def _classify_adjustments(
    source: str,
    row: Mapping[str, Any] | Any,
) -> R4FinanceClassificationResult:
    amount = _amount(_field(row, "Amount", "amount"))
    if _has_value(_field(row, "CancellationOf", "cancellation_of")):
        return _result(
            source_name=source,
            classification=R4FinanceClassification.CANCELLATION_OR_REVERSAL,
            safety_decision=R4FinanceSafetyDecision.MANUAL_REVIEW,
            reason_codes=("cancellation_of_present",),
            raw_amount=amount,
            patient_code_present=True,
        )
    status = _normalized_text(_field(row, "Status", "status"))
    if status and status != "current":
        return _result(
            source_name=source,
            classification=R4FinanceClassification.MANUAL_REVIEW,
            safety_decision=R4FinanceSafetyDecision.MANUAL_REVIEW,
            reason_codes=("adjustment_status_not_current",),
            raw_amount=amount,
            patient_code_present=True,
        )
    adjustment_type = _normalize_key(_field(row, "AdjustmentType", "adjustment_type"))
    if adjustment_type not in _KNOWN_ADJUSTMENT_TYPES:
        return _result(
            source_name=source,
            classification=R4FinanceClassification.MANUAL_REVIEW,
            safety_decision=R4FinanceSafetyDecision.MANUAL_REVIEW,
            reason_codes=("unknown_adjustment_type",),
            raw_amount=amount,
            patient_code_present=True,
        )
    return _result(
        source_name=source,
        classification=R4FinanceClassification.MANUAL_REVIEW,
        safety_decision=R4FinanceSafetyDecision.MANUAL_REVIEW,
        reason_codes=("adjustment_type_requires_policy",),
        raw_amount=amount,
        patient_code_present=True,
    )


def _classify_transactions(
    source: str,
    row: Mapping[str, Any] | Any,
) -> R4FinanceClassificationResult:
    patient_cost = _amount(_field(row, "PatientCost", "patient_cost"))
    dpb_cost = _amount(_field(row, "DPBCost", "dpb_cost"))
    amount = patient_cost if patient_cost is not None else dpb_cost
    reasons = ["transactions_not_invoice_truth", "transaction_reconciliation_only"]
    if _has_value(_field(row, "TPNumber", "tp_number")) or _has_value(
        _field(row, "TPItem", "tp_item")
    ):
        reasons.append("treatment_plan_link_present")
    if _has_value(_field(row, "PaymentAdjustmentID", "payment_adjustment_id")):
        reasons.append("payment_adjustment_link_present")
    return _result(
        source_name=source,
        classification=R4FinanceClassification.TRANSACTION_RECONCILIATION_ONLY,
        safety_decision=R4FinanceSafetyDecision.RECONCILIATION_ONLY,
        reason_codes=tuple(reasons),
        raw_amount=amount,
        patient_code_present=True,
    )


def _classify_allocations(
    source: str,
    row: Mapping[str, Any] | Any,
) -> R4FinanceClassificationResult:
    amount = _amount(_field(row, "Cost", "cost"))
    reasons = ["allocation_reconciliation_only"]
    has_charge_ref = _has_value(
        _field(row, "ChargeTransactionRefID", "charge_transaction_ref_id")
    ) or _has_value(_field(row, "ChargeAdjustmentRefID", "charge_adjustment_ref_id"))
    if has_charge_ref:
        reasons.append("allocation_charge_refs_present")
    else:
        reasons.append("allocation_charge_refs_missing")
    if not _has_value(_field(row, "PaymentID", "payment_id")):
        reasons.append("allocation_payment_link_missing")
    if _bool_field(row, "IsRefund", "is_refund"):
        reasons.append("allocation_refund_flag")
    if _bool_field(row, "IsAdvancedPayment", "is_advanced_payment"):
        reasons.append("allocation_advanced_payment_flag")
    if _bool_field(row, "IsAllocationAdjustment", "is_allocation_adjustment"):
        reasons.append("allocation_adjustment_flag")
    if _bool_field(row, "IsBalancingEntry", "is_balancing_entry"):
        reasons.append("allocation_balancing_entry_flag")
    return _result(
        source_name=source,
        classification=R4FinanceClassification.ALLOCATION_RECONCILIATION_ONLY,
        safety_decision=R4FinanceSafetyDecision.RECONCILIATION_ONLY,
        reason_codes=tuple(reasons),
        raw_amount=amount,
        patient_code_present=True,
    )


def _payment_like_result(
    *,
    source: str,
    classification: R4FinanceClassification,
    expected_sign: R4FinanceRawSign,
    amount: Decimal | None,
    reason_codes: tuple[str, ...],
    proposed_pms_direction: R4FinancePmsDirection,
    unexpected_reason: str,
) -> R4FinanceClassificationResult:
    sign = _raw_sign(amount)
    if sign != expected_sign:
        return _result(
            source_name=source,
            classification=R4FinanceClassification.MANUAL_REVIEW,
            safety_decision=R4FinanceSafetyDecision.MANUAL_REVIEW,
            reason_codes=(unexpected_reason,),
            raw_amount=amount,
            patient_code_present=True,
        )
    return _result(
        source_name=source,
        classification=classification,
        safety_decision=R4FinanceSafetyDecision.CANDIDATE,
        reason_codes=reason_codes,
        raw_amount=amount,
        proposed_pms_direction=proposed_pms_direction,
        patient_code_present=True,
    )


def _reference_result(
    source: str,
    row: Mapping[str, Any] | Any,
    *,
    reason: str,
) -> R4FinanceClassificationResult:
    return _result(
        source_name=source,
        classification=R4FinanceClassification.CLASSIFICATION_REFERENCE_ONLY,
        safety_decision=R4FinanceSafetyDecision.REFERENCE_ONLY,
        reason_codes=(reason,),
        raw_amount=_raw_amount_for_source(source, row),
        patient_code_present=_has_value(_field(row, "PatientCode", "patient_code")),
    )


def _result(
    *,
    source_name: str,
    classification: R4FinanceClassification,
    safety_decision: R4FinanceSafetyDecision,
    reason_codes: tuple[str, ...],
    raw_amount: Decimal | None,
    patient_code_present: bool,
    proposed_pms_direction: R4FinancePmsDirection | None = None,
) -> R4FinanceClassificationResult:
    return R4FinanceClassificationResult(
        source_name=source_name,
        classification=classification,
        safety_decision=safety_decision,
        reason_codes=tuple(reason_codes),
        raw_amount=raw_amount,
        raw_sign=_raw_sign(raw_amount),
        proposed_pms_direction=proposed_pms_direction,
        patient_code_present=patient_code_present,
    )


def _raw_amount_for_source(source: str, row: Mapping[str, Any] | Any) -> Decimal | None:
    if source == "PatientStats":
        return _amount(_field(row, "Balance", "balance"))
    if source in {"vwPayments", "Adjustments"}:
        return _amount(_field(row, "Amount", "amount"))
    if source == "Transactions":
        patient_cost = _amount(_field(row, "PatientCost", "patient_cost"))
        if patient_cost is not None:
            return patient_cost
        return _amount(_field(row, "DPBCost", "dpb_cost"))
    if source in {"PaymentAllocations", "vwAllocatedPayments"}:
        return _amount(_field(row, "Cost", "cost"))
    return None


def _payment_flag_kinds(row: Mapping[str, Any] | Any) -> set[str]:
    kinds: set[str] = set()
    if _bool_field(row, "IsPayment", "is_payment"):
        kinds.add("payment")
    if _bool_field(row, "IsRefund", "is_refund"):
        kinds.add("refund")
    if _bool_field(row, "IsCredit", "is_credit"):
        kinds.add("credit")
    return kinds


def _normalize_source_name(source_name: str) -> str | None:
    cleaned = source_name.strip()
    if cleaned.lower().startswith("dbo."):
        cleaned = cleaned[4:]
    key = cleaned.replace(" ", "").replace("-", "").lower()
    return _SOURCE_ALIASES.get(key)


def _field(row: Mapping[str, Any] | Any, *names: str) -> Any | None:
    for name in names:
        if isinstance(row, Mapping):
            if name in row:
                return row[name]
        elif hasattr(row, name):
            return getattr(row, name)
    return None


def _amount(value: Any | None) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError, AttributeError):
        return None


def _raw_sign(amount: Decimal | None) -> R4FinanceRawSign:
    if amount is None:
        return R4FinanceRawSign.UNKNOWN
    if amount > 0:
        return R4FinanceRawSign.POSITIVE
    if amount < 0:
        return R4FinanceRawSign.NEGATIVE
    return R4FinanceRawSign.ZERO


def _bool_field(row: Mapping[str, Any] | Any, *names: str) -> bool:
    return _coerce_bool(_field(row, *names))


def _coerce_bool(value: Any | None) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _has_value(value: Any | None) -> bool:
    return _normalize_key(value) is not None


def _normalize_key(value: Any | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalized_text(value: Any | None) -> str | None:
    normalized = _normalize_key(value)
    return normalized.lower() if normalized is not None else None
