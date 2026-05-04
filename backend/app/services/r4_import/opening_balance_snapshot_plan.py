from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, Iterable, Mapping

__all__ = [
    "OpeningBalancePmsDirection",
    "OpeningBalancePlanDecision",
    "OpeningBalancePlanReport",
    "OpeningBalancePlanResult",
    "OpeningBalanceRawSign",
    "OpeningBalanceSafetyDecision",
    "plan_opening_balance_snapshot_row",
    "summarize_opening_balance_snapshot_plan",
]


PENCE_FACTOR = Decimal("100")
COMPONENT_TOLERANCE = Decimal("0.01")

_PATIENT_STATS_SOURCE_ALIASES = {
    "patientstats",
    "patient_stats",
    "dbo.patientstats",
}

_COMPONENT_FIELDS = (
    "TreatmentBalance",
    "SundriesBalance",
    "NHSBalance",
    "PrivateBalance",
    "DPBBalance",
)

_AGED_DEBT_FIELDS = (
    "AgeDebtor30To60",
    "AgeDebtor60To90",
    "AgeDebtor90Plus",
)


class OpeningBalancePlanDecision(str, Enum):
    ELIGIBLE_OPENING_BALANCE = "eligible_opening_balance"
    NO_OP_ZERO_BALANCE = "no_op_zero_balance"
    MISSING_PATIENT_MAPPING = "missing_patient_mapping"
    INVALID_PATIENT_CODE = "invalid_patient_code"
    COMPONENT_MISMATCH = "component_mismatch"
    INVALID_AMOUNT = "invalid_amount"
    AMBIGUOUS_SIGN = "ambiguous_sign"
    MANUAL_REVIEW = "manual_review"
    EXCLUDED = "excluded"


class OpeningBalanceSafetyDecision(str, Enum):
    CANDIDATE = "candidate"
    NO_OP = "no_op"
    MANUAL_REVIEW = "manual_review"
    EXCLUDED = "excluded"


class OpeningBalanceRawSign(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    ZERO = "zero"
    UNKNOWN = "unknown"


class OpeningBalancePmsDirection(str, Enum):
    INCREASE_DEBT = "increase_debt"
    DECREASE_DEBT_OR_CREDIT = "decrease_debt_or_credit"
    NO_ACTION = "no_action"


@dataclass(frozen=True)
class OpeningBalancePlanResult:
    source_name: str
    source_patient_code: str | None
    mapped_patient_id: int | str | None
    decision: OpeningBalancePlanDecision
    safety_decision: OpeningBalanceSafetyDecision
    reason_codes: tuple[str, ...]
    raw_balance: Decimal | None
    raw_component_fields: dict[str, Decimal | None]
    raw_aged_debt_fields: dict[str, Decimal | None]
    raw_sign: OpeningBalanceRawSign
    amount_pence: int | None
    proposed_pms_direction: OpeningBalancePmsDirection

    @property
    def can_create_finance_record(self) -> bool:
        return False


@dataclass(frozen=True)
class OpeningBalancePlanReport:
    rows: tuple[OpeningBalancePlanResult, ...]
    decision_counts: dict[str, int]
    safety_decision_counts: dict[str, int]
    raw_sign_counts: dict[str, int]
    proposed_pms_direction_counts: dict[str, int]
    reason_counts: dict[str, int]

    @property
    def total(self) -> int:
        return len(self.rows)


def plan_opening_balance_snapshot_row(
    row: Mapping[str, Any] | Any,
    patient_mapping: Mapping[str | int, int | str | None],
) -> OpeningBalancePlanResult:
    source_name = _normalize_source(_field(row, "source_name", "SourceName", "source"))
    patient_code = _normalize_patient_code(_field(row, "PatientCode", "patient_code"))
    mapped_patient_id = _mapped_patient_id(patient_mapping, patient_code)
    raw_components = _raw_component_fields(row)
    raw_aged_debt = _raw_aged_debt_fields(row)

    if source_name != "PatientStats":
        return _result(
            source_name=source_name or "unknown",
            source_patient_code=patient_code,
            mapped_patient_id=mapped_patient_id,
            decision=OpeningBalancePlanDecision.EXCLUDED,
            safety_decision=OpeningBalanceSafetyDecision.EXCLUDED,
            reason_codes=("unsupported_source",),
            raw_balance=_parse_decimal(_field(row, "Balance", "balance")),
            raw_component_fields=raw_components,
            raw_aged_debt_fields=raw_aged_debt,
            amount_pence=None,
        )

    if patient_code is None:
        return _result(
            source_name=source_name,
            source_patient_code=None,
            mapped_patient_id=None,
            decision=OpeningBalancePlanDecision.INVALID_PATIENT_CODE,
            safety_decision=OpeningBalanceSafetyDecision.EXCLUDED,
            reason_codes=("missing_patient_code",),
            raw_balance=_parse_decimal(_field(row, "Balance", "balance")),
            raw_component_fields=raw_components,
            raw_aged_debt_fields=raw_aged_debt,
            amount_pence=None,
        )

    balance = _parse_decimal(_field(row, "Balance", "balance"))
    if balance is None:
        return _result(
            source_name=source_name,
            source_patient_code=patient_code,
            mapped_patient_id=mapped_patient_id,
            decision=OpeningBalancePlanDecision.INVALID_AMOUNT,
            safety_decision=OpeningBalanceSafetyDecision.MANUAL_REVIEW,
            reason_codes=("balance_amount_missing_or_invalid",),
            raw_balance=None,
            raw_component_fields=raw_components,
            raw_aged_debt_fields=raw_aged_debt,
            amount_pence=None,
        )

    amount_pence = _decimal_to_pence(balance)
    if amount_pence is None:
        return _result(
            source_name=source_name,
            source_patient_code=patient_code,
            mapped_patient_id=mapped_patient_id,
            decision=OpeningBalancePlanDecision.INVALID_AMOUNT,
            safety_decision=OpeningBalanceSafetyDecision.MANUAL_REVIEW,
            reason_codes=("balance_amount_not_exact_pence",),
            raw_balance=balance,
            raw_component_fields=raw_components,
            raw_aged_debt_fields=raw_aged_debt,
            amount_pence=None,
        )

    sign = _raw_sign(balance)
    explicit_sign = _explicit_raw_sign(row)
    if explicit_sign == OpeningBalanceRawSign.UNKNOWN:
        return _result(
            source_name=source_name,
            source_patient_code=patient_code,
            mapped_patient_id=mapped_patient_id,
            decision=OpeningBalancePlanDecision.AMBIGUOUS_SIGN,
            safety_decision=OpeningBalanceSafetyDecision.MANUAL_REVIEW,
            reason_codes=("raw_sign_unknown",),
            raw_balance=balance,
            raw_component_fields=raw_components,
            raw_aged_debt_fields=raw_aged_debt,
            amount_pence=amount_pence,
        )
    if explicit_sign is not None and explicit_sign != sign:
        return _result(
            source_name=source_name,
            source_patient_code=patient_code,
            mapped_patient_id=mapped_patient_id,
            decision=OpeningBalancePlanDecision.AMBIGUOUS_SIGN,
            safety_decision=OpeningBalanceSafetyDecision.MANUAL_REVIEW,
            reason_codes=("raw_sign_conflicts_with_balance",),
            raw_balance=balance,
            raw_component_fields=raw_components,
            raw_aged_debt_fields=raw_aged_debt,
            amount_pence=amount_pence,
        )

    component_error = _component_error(balance, raw_components)
    if component_error is not None:
        return _result(
            source_name=source_name,
            source_patient_code=patient_code,
            mapped_patient_id=mapped_patient_id,
            decision=OpeningBalancePlanDecision.COMPONENT_MISMATCH,
            safety_decision=OpeningBalanceSafetyDecision.MANUAL_REVIEW,
            reason_codes=(component_error,),
            raw_balance=balance,
            raw_component_fields=raw_components,
            raw_aged_debt_fields=raw_aged_debt,
            amount_pence=amount_pence,
        )

    if sign == OpeningBalanceRawSign.ZERO:
        reasons = [
            "zero_balance_no_finance_action",
            "balance_component_check_passed",
            "treatment_split_check_passed",
        ]
        if _aged_debt_total(raw_aged_debt) != Decimal("0"):
            reasons.append("aged_debt_present_zero_balance_metadata_only")
        return _result(
            source_name=source_name,
            source_patient_code=patient_code,
            mapped_patient_id=mapped_patient_id,
            decision=OpeningBalancePlanDecision.NO_OP_ZERO_BALANCE,
            safety_decision=OpeningBalanceSafetyDecision.NO_OP,
            reason_codes=tuple(reasons),
            raw_balance=balance,
            raw_component_fields=raw_components,
            raw_aged_debt_fields=raw_aged_debt,
            amount_pence=0,
            proposed_pms_direction=OpeningBalancePmsDirection.NO_ACTION,
        )

    if mapped_patient_id is None:
        return _result(
            source_name=source_name,
            source_patient_code=patient_code,
            mapped_patient_id=None,
            decision=OpeningBalancePlanDecision.MISSING_PATIENT_MAPPING,
            safety_decision=OpeningBalanceSafetyDecision.MANUAL_REVIEW,
            reason_codes=("missing_patient_mapping",),
            raw_balance=balance,
            raw_component_fields=raw_components,
            raw_aged_debt_fields=raw_aged_debt,
            amount_pence=amount_pence,
        )

    direction = (
        OpeningBalancePmsDirection.INCREASE_DEBT
        if sign == OpeningBalanceRawSign.POSITIVE
        else OpeningBalancePmsDirection.DECREASE_DEBT_OR_CREDIT
    )
    sign_reason = (
        "positive_balance_increase_debt"
        if sign == OpeningBalanceRawSign.POSITIVE
        else "negative_balance_decrease_debt_or_credit"
    )
    reasons = [
        "eligible_opening_balance_candidate",
        "patient_mapping_present",
        "balance_component_check_passed",
        "treatment_split_check_passed",
        sign_reason,
    ]
    if _aged_debt_total(raw_aged_debt) == Decimal("0"):
        reasons.append("balance_without_aged_debt_metadata_only")

    return _result(
        source_name=source_name,
        source_patient_code=patient_code,
        mapped_patient_id=mapped_patient_id,
        decision=OpeningBalancePlanDecision.ELIGIBLE_OPENING_BALANCE,
        safety_decision=OpeningBalanceSafetyDecision.CANDIDATE,
        reason_codes=tuple(reasons),
        raw_balance=balance,
        raw_component_fields=raw_components,
        raw_aged_debt_fields=raw_aged_debt,
        amount_pence=amount_pence,
        proposed_pms_direction=direction,
    )


def summarize_opening_balance_snapshot_plan(
    results: Iterable[OpeningBalancePlanResult],
) -> OpeningBalancePlanReport:
    rows = tuple(results)
    reason_counts: Counter[str] = Counter()
    for row in rows:
        reason_counts.update(row.reason_codes)
    return OpeningBalancePlanReport(
        rows=rows,
        decision_counts=dict(sorted(Counter(row.decision.value for row in rows).items())),
        safety_decision_counts=dict(
            sorted(Counter(row.safety_decision.value for row in rows).items())
        ),
        raw_sign_counts=dict(sorted(Counter(row.raw_sign.value for row in rows).items())),
        proposed_pms_direction_counts=dict(
            sorted(Counter(row.proposed_pms_direction.value for row in rows).items())
        ),
        reason_counts=dict(sorted(reason_counts.items())),
    )


def _result(
    *,
    source_name: str,
    source_patient_code: str | None,
    mapped_patient_id: int | str | None,
    decision: OpeningBalancePlanDecision,
    safety_decision: OpeningBalanceSafetyDecision,
    reason_codes: tuple[str, ...],
    raw_balance: Decimal | None,
    raw_component_fields: dict[str, Decimal | None],
    raw_aged_debt_fields: dict[str, Decimal | None],
    amount_pence: int | None,
    proposed_pms_direction: OpeningBalancePmsDirection | None = None,
) -> OpeningBalancePlanResult:
    direction = proposed_pms_direction or _direction_for_amount(raw_balance)
    return OpeningBalancePlanResult(
        source_name=source_name,
        source_patient_code=source_patient_code,
        mapped_patient_id=mapped_patient_id,
        decision=decision,
        safety_decision=safety_decision,
        reason_codes=tuple(reason_codes),
        raw_balance=raw_balance,
        raw_component_fields=dict(raw_component_fields),
        raw_aged_debt_fields=dict(raw_aged_debt_fields),
        raw_sign=_raw_sign(raw_balance),
        amount_pence=amount_pence,
        proposed_pms_direction=direction,
    )


def _component_error(
    balance: Decimal,
    raw_components: Mapping[str, Decimal | None],
) -> str | None:
    components = [raw_components[field] for field in _COMPONENT_FIELDS]
    if any(component is None for component in components):
        return "component_amount_missing_or_invalid"
    if any(_decimal_to_pence(component) is None for component in components):
        return "component_amount_not_exact_pence"

    treatment = raw_components["TreatmentBalance"]
    sundries = raw_components["SundriesBalance"]
    nhs = raw_components["NHSBalance"]
    private = raw_components["PrivateBalance"]
    dpb = raw_components["DPBBalance"]
    if (
        treatment is None
        or sundries is None
        or nhs is None
        or private is None
        or dpb is None
    ):
        return "component_amount_missing_or_invalid"
    if abs(balance - (treatment + sundries)) > COMPONENT_TOLERANCE:
        return "balance_component_mismatch"
    if abs(treatment - (nhs + private + dpb)) > COMPONENT_TOLERANCE:
        return "treatment_split_mismatch"
    return None


def _raw_component_fields(row: Mapping[str, Any] | Any) -> dict[str, Decimal | None]:
    return {
        field: _parse_decimal(_field(row, field, _snake(field)))
        for field in _COMPONENT_FIELDS
    }


def _raw_aged_debt_fields(row: Mapping[str, Any] | Any) -> dict[str, Decimal | None]:
    return {
        field: _parse_decimal(_field(row, field, _snake(field)))
        for field in _AGED_DEBT_FIELDS
    }


def _aged_debt_total(raw_aged_debt: Mapping[str, Decimal | None]) -> Decimal:
    total = Decimal("0")
    for amount in raw_aged_debt.values():
        if amount is not None:
            total += amount
    return total


def _mapped_patient_id(
    patient_mapping: Mapping[str | int, int | str | None],
    patient_code: str | None,
) -> int | str | None:
    if patient_code is None:
        return None
    normalized_mapping = {
        normalized_key: value
        for key, value in patient_mapping.items()
        if (normalized_key := _normalize_patient_code(key)) is not None
    }
    return normalized_mapping.get(patient_code)


def _direction_for_amount(amount: Decimal | None) -> OpeningBalancePmsDirection:
    sign = _raw_sign(amount)
    if sign == OpeningBalanceRawSign.POSITIVE:
        return OpeningBalancePmsDirection.INCREASE_DEBT
    if sign == OpeningBalanceRawSign.NEGATIVE:
        return OpeningBalancePmsDirection.DECREASE_DEBT_OR_CREDIT
    return OpeningBalancePmsDirection.NO_ACTION


def _raw_sign(amount: Decimal | None) -> OpeningBalanceRawSign:
    if amount is None:
        return OpeningBalanceRawSign.UNKNOWN
    if amount > 0:
        return OpeningBalanceRawSign.POSITIVE
    if amount < 0:
        return OpeningBalanceRawSign.NEGATIVE
    return OpeningBalanceRawSign.ZERO


def _explicit_raw_sign(row: Mapping[str, Any] | Any) -> OpeningBalanceRawSign | None:
    value = _field(row, "RawSign", "raw_sign")
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if normalized == "positive":
        return OpeningBalanceRawSign.POSITIVE
    if normalized == "negative":
        return OpeningBalanceRawSign.NEGATIVE
    if normalized == "zero":
        return OpeningBalanceRawSign.ZERO
    return OpeningBalanceRawSign.UNKNOWN


def _decimal_to_pence(amount: Decimal) -> int | None:
    if not amount.is_finite():
        return None
    scaled = amount * PENCE_FACTOR
    integral = scaled.to_integral_value()
    if scaled != integral:
        return None
    return int(integral)


def _parse_decimal(value: Any | None) -> Decimal | None:
    if value is None:
        return None
    try:
        amount = Decimal(str(value).strip())
    except (InvalidOperation, ValueError, AttributeError):
        return None
    if not amount.is_finite():
        return None
    return amount


def _normalize_source(value: Any | None) -> str:
    if value is None:
        return "PatientStats"
    normalized = str(value).strip().replace(" ", "").replace("-", "_").lower()
    if normalized in _PATIENT_STATS_SOURCE_ALIASES:
        return "PatientStats"
    return str(value).strip() or "unknown"


def _normalize_patient_code(value: Any | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _field(row: Mapping[str, Any] | Any, *names: str) -> Any | None:
    for name in names:
        if isinstance(row, Mapping):
            if name in row:
                return row[name]
        elif hasattr(row, name):
            return getattr(row, name)
    return None


def _snake(name: str) -> str:
    chars: list[str] = []
    for index, char in enumerate(name):
        if char.isupper() and index > 0:
            chars.append("_")
        chars.append(char.lower())
    return "".join(chars)
