from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable, Mapping

from app.services.r4_import.opening_balance_snapshot_plan import (
    OpeningBalancePlanDecision,
    OpeningBalancePlanReport,
    OpeningBalancePlanResult,
    OpeningBalanceRawSign,
    plan_opening_balance_snapshot_row,
    summarize_opening_balance_snapshot_plan,
)

__all__ = [
    "build_opening_balance_snapshot_dry_run_report",
    "load_patient_mapping_json",
    "load_patient_stats_rows_json",
    "normalize_patient_mapping",
]


SOURCE_MODE_PATIENT_STATS_JSON = "patient_stats_json"

_ALL_DECISIONS = tuple(decision.value for decision in OpeningBalancePlanDecision)
_ALL_RAW_SIGNS = tuple(sign.value for sign in OpeningBalanceRawSign)
_NON_REFUSAL_DECISIONS = {
    OpeningBalancePlanDecision.ELIGIBLE_OPENING_BALANCE.value,
    OpeningBalancePlanDecision.NO_OP_ZERO_BALANCE.value,
}


def build_opening_balance_snapshot_dry_run_report(
    rows: Iterable[Mapping[str, Any] | Any],
    patient_mapping: Mapping[str | int, int | str | None],
    *,
    source_mode: str = SOURCE_MODE_PATIENT_STATS_JSON,
    source_artifact_path: str | None = None,
    repo_sha: str | None = None,
    generated_at: datetime | None = None,
    sample_limit: int = 10,
    dry_run_parameters: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if sample_limit < 1:
        raise RuntimeError("sample_limit must be at least 1.")

    normalized_mapping = normalize_patient_mapping(patient_mapping)
    planned_rows = [
        plan_opening_balance_snapshot_row(row, normalized_mapping) for row in rows
    ]
    plan_report = summarize_opening_balance_snapshot_plan(planned_rows)
    generated = generated_at or datetime.now(timezone.utc).replace(microsecond=0)
    dry_run_params = dict(dry_run_parameters or {})

    return {
        "generated_at": generated.isoformat(),
        "dry_run": True,
        "select_only": False,
        "source_mode": source_mode,
        "import_ready": False,
        "finance_import_ready": False,
        "source_summary": _source_summary(planned_rows, source_mode),
        "mapping_summary": _mapping_summary(planned_rows, normalized_mapping),
        "eligibility_summary": _eligibility_summary(plan_report.decision_counts),
        "sign_summary": _sign_summary(plan_report),
        "component_consistency_summary": _component_summary(planned_rows),
        "aged_debt_summary": _aged_debt_summary(planned_rows),
        "refusal_reasons": _refusal_reasons(planned_rows),
        "samples": _samples(planned_rows, sample_limit=sample_limit),
        "risks": _risks(planned_rows),
        "manifest": {
            "repo_sha": repo_sha or "unknown",
            "source_mode": source_mode,
            "source_artifact_path": source_artifact_path,
            "run_timestamp": generated.isoformat(),
            "dry_run_parameters": dry_run_params,
            "sample_limit": sample_limit,
            "mapping_source": dry_run_params.get("mapping_source"),
            "db_target": "not_used",
            "r4_readonly": "not_used",
            "no_write": True,
            "apply_mode": False,
        },
    }


def load_patient_stats_rows_json(path: str | Path) -> list[Mapping[str, Any]]:
    payload = _load_json(path)
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, Mapping):
        rows = (
            payload.get("patient_stats_rows")
            or payload.get("PatientStats")
            or payload.get("rows")
        )
    else:
        rows = None
    if not isinstance(rows, list):
        raise RuntimeError(
            "PatientStats JSON must be a list or contain patient_stats_rows/rows."
        )
    if not all(isinstance(row, Mapping) for row in rows):
        raise RuntimeError("PatientStats JSON rows must be objects.")
    return [dict(row) for row in rows]


def load_patient_mapping_json(path: str | Path) -> dict[str, int | str]:
    payload = _load_json(path)
    if isinstance(payload, Mapping):
        mapping_payload = payload.get("mappings", payload)
        return normalize_patient_mapping(mapping_payload)
    if isinstance(payload, list):
        mapping: dict[str, int | str | None] = {}
        for item in payload:
            if not isinstance(item, Mapping):
                raise RuntimeError("Patient mapping list entries must be objects.")
            code = _first_present(
                item,
                "PatientCode",
                "patient_code",
                "source_patient_code",
                "r4_patient_code",
            )
            patient_id = _first_present(
                item,
                "patient_id",
                "mapped_patient_id",
                "pms_patient_id",
                "id",
            )
            if code is not None:
                mapping[str(code)] = patient_id
        return normalize_patient_mapping(mapping)
    raise RuntimeError("Patient mapping JSON must be an object or list.")


def normalize_patient_mapping(
    patient_mapping: Mapping[str | int, int | str | None],
) -> dict[str, int | str]:
    normalized: dict[str, int | str] = {}
    for key, value in patient_mapping.items():
        patient_code = _normalize_patient_code(key)
        if patient_code is None or value is None:
            continue
        normalized[patient_code] = value
    return normalized


def _source_summary(
    rows: list[OpeningBalancePlanResult],
    source_mode: str,
) -> dict[str, Any]:
    known_totals = _known_totals(rows)
    return {
        "source_mode": source_mode,
        "row_count": len(rows),
        "nonzero_count": _count_nonzero(rows),
        "zero_no_op_count": _count_decision(
            rows, OpeningBalancePlanDecision.NO_OP_ZERO_BALANCE
        ),
        "known_totals": known_totals,
    }


def _mapping_summary(
    rows: list[OpeningBalancePlanResult],
    patient_mapping: Mapping[str, int | str],
) -> dict[str, Any]:
    nonzero_rows = [row for row in rows if _is_nonzero(row)]
    mapped_nonzero = sum(1 for row in nonzero_rows if row.mapped_patient_id is not None)
    unmapped_nonzero = len(nonzero_rows) - mapped_nonzero
    return {
        "mappings_supplied": len(patient_mapping),
        "mapped_nonzero_candidates": mapped_nonzero,
        "unmapped_nonzero_candidates": unmapped_nonzero,
        "nonzero_mapping_coverage": _coverage(mapped_nonzero, len(nonzero_rows)),
        "total_patient_codes_seen": len(
            {row.source_patient_code for row in rows if row.source_patient_code}
        ),
    }


def _eligibility_summary(decision_counts: Mapping[str, int]) -> dict[str, int]:
    return {decision: int(decision_counts.get(decision, 0)) for decision in _ALL_DECISIONS}


def _sign_summary(plan_report: OpeningBalancePlanReport) -> dict[str, int]:
    raw_counts = {
        sign: int(plan_report.raw_sign_counts.get(sign, 0)) for sign in _ALL_RAW_SIGNS
    }
    direction_counts = {
        direction: int(plan_report.proposed_pms_direction_counts.get(direction, 0))
        for direction in (
            "increase_debt",
            "decrease_debt_or_credit",
            "no_action",
        )
    }
    return {**raw_counts, **direction_counts}


def _component_summary(rows: list[OpeningBalancePlanResult]) -> dict[str, int]:
    mismatch_count = _count_decision(rows, OpeningBalancePlanDecision.COMPONENT_MISMATCH)
    pass_count = sum(
        1
        for row in rows
        if row.decision
        in {
            OpeningBalancePlanDecision.ELIGIBLE_OPENING_BALANCE,
            OpeningBalancePlanDecision.NO_OP_ZERO_BALANCE,
            OpeningBalancePlanDecision.MISSING_PATIENT_MAPPING,
        }
    )
    return {
        "component_pass_count": pass_count,
        "mismatch_count": mismatch_count,
        "not_evaluated_count": max(len(rows) - pass_count - mismatch_count, 0),
    }


def _aged_debt_summary(rows: list[OpeningBalancePlanResult]) -> dict[str, Any]:
    aged_debt_present = 0
    balance_without_aged = 0
    aged_with_zero = 0
    total_aged = Decimal("0")
    for row in rows:
        aged_total = _aged_debt_total(row)
        total_aged += aged_total
        if aged_total != Decimal("0"):
            aged_debt_present += 1
        if _is_nonzero(row) and aged_total == Decimal("0"):
            balance_without_aged += 1
        if row.raw_sign == OpeningBalanceRawSign.ZERO and aged_total != Decimal("0"):
            aged_with_zero += 1
    return {
        "aged_debt_present_count": aged_debt_present,
        "balance_without_aged_debt_count": balance_without_aged,
        "aged_debt_with_zero_balance_count": aged_with_zero,
        "total_aged_debt": _decimal_str(total_aged),
    }


def _refusal_reasons(rows: list[OpeningBalancePlanResult]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for row in rows:
        if row.decision.value not in _NON_REFUSAL_DECISIONS:
            counter.update(row.reason_codes)
    return dict(sorted(counter.items()))


def _samples(
    rows: list[OpeningBalancePlanResult],
    *,
    sample_limit: int,
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        bucket = grouped[row.decision.value]
        if len(bucket) < sample_limit:
            bucket.append(_result_json(row))
    return {decision: grouped.get(decision, []) for decision in _ALL_DECISIONS}


def _risks(rows: list[OpeningBalancePlanResult]) -> list[str]:
    risks = [
        "dry-run report only; no PMS finance records are authorised",
        "finance_import_ready remains false",
    ]
    if _count_decision(rows, OpeningBalancePlanDecision.MISSING_PATIENT_MAPPING):
        risks.append("nonzero PatientStats rows are missing patient mappings")
    if _count_decision(rows, OpeningBalancePlanDecision.COMPONENT_MISMATCH):
        risks.append("PatientStats component mismatches block opening-balance planning")
    if _count_decision(rows, OpeningBalancePlanDecision.INVALID_PATIENT_CODE):
        risks.append("PatientStats rows with missing PatientCode are refused")
    if _count_decision(rows, OpeningBalancePlanDecision.INVALID_AMOUNT):
        risks.append("PatientStats rows with invalid or non-pence amounts are refused")
    if _count_decision(rows, OpeningBalancePlanDecision.AMBIGUOUS_SIGN):
        risks.append("PatientStats rows with ambiguous signs are refused")
    if _count_decision(rows, OpeningBalancePlanDecision.EXCLUDED):
        risks.append("unsupported source rows are excluded")
    if _aged_debt_summary(rows)["balance_without_aged_debt_count"]:
        risks.append("some nonzero balances have no aged-debt metadata")
    return risks


def _result_json(row: OpeningBalancePlanResult) -> dict[str, Any]:
    return {
        "source_name": row.source_name,
        "source_patient_code": row.source_patient_code,
        "mapped_patient_id": row.mapped_patient_id,
        "decision": row.decision.value,
        "safety_decision": row.safety_decision.value,
        "reason_codes": list(row.reason_codes),
        "raw_balance": _decimal_str(row.raw_balance),
        "raw_component_fields": {
            key: _decimal_str(value) for key, value in row.raw_component_fields.items()
        },
        "raw_aged_debt_fields": {
            key: _decimal_str(value) for key, value in row.raw_aged_debt_fields.items()
        },
        "raw_sign": row.raw_sign.value,
        "amount_pence": row.amount_pence,
        "proposed_pms_direction": row.proposed_pms_direction.value,
        "can_create_finance_record": row.can_create_finance_record,
    }


def _known_totals(rows: list[OpeningBalancePlanResult]) -> dict[str, str]:
    total_balance = Decimal("0")
    component_totals = {
        "TreatmentBalance": Decimal("0"),
        "SundriesBalance": Decimal("0"),
        "NHSBalance": Decimal("0"),
        "PrivateBalance": Decimal("0"),
        "DPBBalance": Decimal("0"),
    }
    for row in rows:
        if row.raw_balance is not None:
            total_balance += row.raw_balance
        for field in component_totals:
            value = row.raw_component_fields.get(field)
            if value is not None:
                component_totals[field] += value
    return {
        "total_balance": _decimal_str(total_balance),
        "total_treatment_balance": _decimal_str(component_totals["TreatmentBalance"]),
        "total_sundries_balance": _decimal_str(component_totals["SundriesBalance"]),
        "total_nhs_balance": _decimal_str(component_totals["NHSBalance"]),
        "total_private_balance": _decimal_str(component_totals["PrivateBalance"]),
        "total_dpb_balance": _decimal_str(component_totals["DPBBalance"]),
    }


def _count_decision(
    rows: list[OpeningBalancePlanResult],
    decision: OpeningBalancePlanDecision,
) -> int:
    return sum(1 for row in rows if row.decision == decision)


def _count_nonzero(rows: list[OpeningBalancePlanResult]) -> int:
    return sum(1 for row in rows if _is_nonzero(row))


def _is_nonzero(row: OpeningBalancePlanResult) -> bool:
    return row.raw_sign in {OpeningBalanceRawSign.POSITIVE, OpeningBalanceRawSign.NEGATIVE}


def _aged_debt_total(row: OpeningBalancePlanResult) -> Decimal:
    total = Decimal("0")
    for value in row.raw_aged_debt_fields.values():
        if value is not None:
            total += value
    return total


def _coverage(mapped: int, total: int) -> str:
    if total == 0:
        return "not_applicable"
    return f"{Decimal(mapped) / Decimal(total):.4f}"


def _decimal_str(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return f"{value:.2f}"


def _first_present(row: Mapping[str, Any], *keys: str) -> Any | None:
    for key in keys:
        if key in row:
            return row[key]
    return None


def _normalize_patient_code(value: Any | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))
