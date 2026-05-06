from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any
from urllib.parse import urlparse

__all__ = [
    "OPENING_BALANCE_APPLY_CONFIRMATION_TOKEN",
    "OPENING_BALANCE_APPLY_REPRESENTATION",
    "build_opening_balance_snapshot_apply_plan",
]


OPENING_BALANCE_APPLY_CONFIRMATION_TOKEN = "SCRATCH_OPENING_BALANCE_APPLY"
OPENING_BALANCE_APPLY_REPRESENTATION = "patient_ledger_entry_adjustment"
OPENING_BALANCE_REFERENCE_PREFIX = "R4OB"

_BEFORE_COUNT_KEYS = ("patient_ledger_entries", "invoices", "payments")


def build_opening_balance_snapshot_apply_plan(
    *,
    dry_run_report: Mapping[str, Any],
    database_target: str | None,
    confirmation_token: str | None,
    manifest_id: str | None,
    before_finance_counts: Mapping[str, Any] | None,
    representation: str = OPENING_BALANCE_APPLY_REPRESENTATION,
    source_drift_acknowledged: bool = False,
    candidate_rows: Iterable[Mapping[str, Any]] | None = None,
    existing_manifest_rows: Iterable[Mapping[str, Any]] | None = None,
    existing_manifest_ids: Iterable[str] | None = None,
    existing_opening_balance_markers: Iterable[Mapping[str, Any]] | None = None,
    write_intent: Mapping[str, Any] | None = None,
    expected_dry_run_repo_sha: str | None = None,
    sample_limit: int = 5,
) -> dict[str, Any]:
    """Build a fail-closed opening-balance apply preflight plan.

    The helper accepts already parsed JSON-like inputs and intentionally avoids
    database sessions, R4 connections, commands, or executable write objects.
    """

    if not isinstance(dry_run_report, Mapping):
        raise TypeError("dry_run_report must be a mapping.")
    if sample_limit < 1:
        raise RuntimeError("sample_limit must be at least 1.")

    rows = tuple(candidate_rows or ())
    existing_rows = tuple(existing_manifest_rows or ())
    existing_ids = tuple(str(value) for value in existing_manifest_ids or ())
    existing_markers = tuple(existing_opening_balance_markers or ())
    intent = dict(write_intent or {})

    blocking_reasons: list[str] = []
    database_decision = _database_target_decision(database_target, blocking_reasons)
    confirmation_decision = _confirmation_decision(
        confirmation_token,
        blocking_reasons,
    )
    dry_run_decision = _dry_run_report_decision(
        dry_run_report,
        expected_dry_run_repo_sha=expected_dry_run_repo_sha,
        source_drift_acknowledged=source_drift_acknowledged,
        candidate_rows=rows,
        blocking_reasons=blocking_reasons,
    )
    eligibility_decision = _eligibility_decision(dry_run_report, rows)
    mapping_decision = _mapping_decision(dry_run_report, blocking_reasons)
    representation_decision = _representation_decision(
        representation,
        intent,
        blocking_reasons,
    )
    before_counts_decision = _before_counts_decision(
        before_finance_counts,
        blocking_reasons,
    )
    idempotency_plan = _idempotency_plan(
        manifest_id=manifest_id,
        eligible_count=eligibility_decision["eligible_count"],
        existing_manifest_rows=existing_rows,
        existing_manifest_ids=existing_ids,
        existing_opening_balance_markers=existing_markers,
        blocking_reasons=blocking_reasons,
    )
    rollback_plan = _rollback_plan(
        manifest_id=manifest_id,
        write_intent=intent,
        blocking_reasons=blocking_reasons,
    )

    would_skip = idempotency_plan["would_skip_count"]
    would_create = eligibility_decision["eligible_count"] - would_skip
    if idempotency_plan["duplicate_manifest_fails_closed"]:
        would_create = 0
    would_create = max(would_create, 0)

    write_plan_summary = {
        "representation": OPENING_BALANCE_APPLY_REPRESENTATION,
        "requested_representation": representation,
        "representation_supported": representation_decision["supported"],
        "would_create": would_create,
        "would_skip": would_skip,
        "would_refuse": eligibility_decision["refused_count"],
        "would_create_invoices": 0,
        "would_create_payments": 0,
        "would_create_staging_models": 0,
        "would_mutate_balances_outside_selected_representation": False,
        "apply_execution": False,
        "reason_codes": representation_decision["reason_codes"],
    }

    return {
        "is_safe_to_apply_in_scratch": not blocking_reasons,
        "finance_import_ready": False,
        "database_target_decision": database_decision,
        "confirmation_decision": confirmation_decision,
        "dry_run_report_decision": dry_run_decision,
        "eligibility_decision": eligibility_decision,
        "mapping_decision": mapping_decision,
        "before_counts_decision": before_counts_decision,
        "write_plan_summary": write_plan_summary,
        "idempotency_plan": idempotency_plan,
        "rollback_plan": rollback_plan,
        "reason_codes": tuple(dict.fromkeys(blocking_reasons)),
        "sample_planned_rows": _sample_planned_rows(
            dry_run_report,
            manifest_id=manifest_id,
            sample_limit=sample_limit,
        ),
    }


def _database_target_decision(
    database_target: str | None,
    blocking_reasons: list[str],
) -> dict[str, Any]:
    database_name = _database_name(database_target)
    reason_codes: list[str] = []
    missing = database_name is None
    default_or_live = False
    scratch_or_test = False

    if missing:
        reason_codes.append("missing_database_target")
        blocking_reasons.append("missing_database_target")
    else:
        normalized = _normalize_name(database_name)
        scratch_or_test = "scratch" in normalized or "test" in normalized
        default_or_live = normalized == "dental_pms" or not scratch_or_test
        if normalized == "dental_pms":
            reason_codes.append("default_dental_pms_database_refused")
            blocking_reasons.append("default_dental_pms_database_refused")
        elif not scratch_or_test:
            reason_codes.append("database_target_not_scratch_or_test")
            blocking_reasons.append("database_target_not_scratch_or_test")
        else:
            reason_codes.append("scratch_or_test_database_allowed")

    return {
        "database_target": database_target,
        "database_name": database_name,
        "scratch_or_test_allowed": scratch_or_test and not default_or_live,
        "default_or_live_refused": default_or_live,
        "missing_or_unknown_refused": missing,
        "reason_codes": tuple(reason_codes),
    }


def _confirmation_decision(
    confirmation_token: str | None,
    blocking_reasons: list[str],
) -> dict[str, Any]:
    accepted = confirmation_token == OPENING_BALANCE_APPLY_CONFIRMATION_TOKEN
    reason_codes: list[str] = []
    if accepted:
        reason_codes.append("confirmation_token_accepted")
    elif confirmation_token is None:
        reason_codes.append("missing_confirmation_token")
        blocking_reasons.append("missing_confirmation_token")
    else:
        reason_codes.append("invalid_confirmation_token")
        blocking_reasons.append("invalid_confirmation_token")
    return {
        "token_required": OPENING_BALANCE_APPLY_CONFIRMATION_TOKEN,
        "token_accepted": accepted,
        "reason_codes": tuple(reason_codes),
    }


def _dry_run_report_decision(
    dry_run_report: Mapping[str, Any],
    *,
    expected_dry_run_repo_sha: str | None,
    source_drift_acknowledged: bool,
    candidate_rows: tuple[Mapping[str, Any], ...],
    blocking_reasons: list[str],
) -> dict[str, Any]:
    manifest = _mapping_value(dry_run_report, "manifest")
    reason_codes: list[str] = []

    dry_run = dry_run_report.get("dry_run")
    if dry_run is True:
        reason_codes.append("dry_run_true")
    else:
        reason_codes.append("dry_run_true_required")
        blocking_reasons.append("dry_run_true_required")

    import_ready = dry_run_report.get("import_ready")
    if import_ready is False:
        reason_codes.append("import_ready_false")
    elif import_ready is True:
        reason_codes.append("import_ready_true_refused")
        blocking_reasons.append("import_ready_true_refused")
    else:
        reason_codes.append("import_ready_missing")
        blocking_reasons.append("import_ready_missing")

    finance_import_ready = dry_run_report.get("finance_import_ready")
    if finance_import_ready is False:
        reason_codes.append("finance_import_ready_false")
    elif finance_import_ready is True:
        reason_codes.append("finance_import_ready_true_refused")
        blocking_reasons.append("finance_import_ready_true_refused")

    no_write = manifest.get("no_write")
    if no_write is True:
        reason_codes.append("manifest_no_write_true")
    else:
        reason_codes.append("manifest_no_write_true_required")
        blocking_reasons.append("manifest_no_write_true_required")

    apply_mode = manifest.get("apply_mode")
    if apply_mode is False:
        reason_codes.append("manifest_apply_mode_false")
    elif apply_mode is True:
        reason_codes.append("manifest_apply_mode_true_refused")
        blocking_reasons.append("manifest_apply_mode_true_refused")
    else:
        reason_codes.append("manifest_apply_mode_missing")
        blocking_reasons.append("manifest_apply_mode_missing")

    repo_sha = manifest.get("repo_sha")
    if not repo_sha or repo_sha == "unknown":
        reason_codes.append("dry_run_repo_sha_missing")
        blocking_reasons.append("dry_run_repo_sha_missing")
    elif expected_dry_run_repo_sha and repo_sha != expected_dry_run_repo_sha:
        reason_codes.append("dry_run_repo_sha_mismatch")
        blocking_reasons.append("dry_run_repo_sha_mismatch")
    else:
        reason_codes.append("dry_run_repo_sha_present")

    if _eligible_count(dry_run_report) is None:
        reason_codes.append("eligible_count_missing")
        blocking_reasons.append("eligible_count_missing")

    would_write_mismatches = _component_mismatch_would_write_count(
        dry_run_report,
        candidate_rows,
    )
    if would_write_mismatches:
        reason_codes.append("component_mismatch_among_would_write_rows_refused")
        blocking_reasons.append("component_mismatch_among_would_write_rows_refused")
    else:
        reason_codes.append("no_component_mismatch_among_would_write_rows")

    if _source_drift_present(dry_run_report):
        if source_drift_acknowledged:
            reason_codes.append("source_drift_acknowledged")
        else:
            reason_codes.append("source_drift_acknowledgement_required")
            blocking_reasons.append("source_drift_acknowledgement_required")

    if _ambiguous_would_write_count(dry_run_report, candidate_rows):
        reason_codes.append("ambiguous_would_write_sign_refused")
        blocking_reasons.append("ambiguous_would_write_sign_refused")

    return {
        "dry_run_required": True,
        "dry_run": dry_run,
        "import_ready": import_ready,
        "import_ready_expected_false": True,
        "finance_import_ready": finance_import_ready,
        "manifest_no_write": no_write,
        "manifest_apply_mode": apply_mode,
        "manifest_repo_sha": repo_sha,
        "source_drift_present": _source_drift_present(dry_run_report),
        "source_drift_acknowledged": source_drift_acknowledged,
        "component_mismatch_would_write_count": would_write_mismatches,
        "reason_codes": tuple(reason_codes),
    }


def _eligibility_decision(
    dry_run_report: Mapping[str, Any],
    candidate_rows: tuple[Mapping[str, Any], ...],
) -> dict[str, int]:
    summary = _mapping_value(dry_run_report, "eligibility_summary")
    eligible = _eligible_count(dry_run_report) or 0
    no_op = _int_value(summary.get("no_op_zero_balance")) or 0
    component_mismatch = _int_value(summary.get("component_mismatch")) or 0
    unmapped = _int_value(
        _mapping_value(dry_run_report, "mapping_summary").get(
            "unmapped_nonzero_candidates"
        )
    ) or 0
    refused = _refused_count(summary)
    return {
        "eligible_count": eligible,
        "refused_count": refused,
        "no_op_count": no_op,
        "component_mismatch_count": component_mismatch,
        "component_mismatch_would_write_count": _component_mismatch_would_write_count(
            dry_run_report,
            candidate_rows,
        ),
        "unmapped_nonzero_count": unmapped,
    }


def _mapping_decision(
    dry_run_report: Mapping[str, Any],
    blocking_reasons: list[str],
) -> dict[str, Any]:
    source_summary = _mapping_value(dry_run_report, "source_summary")
    mapping_summary = _mapping_value(dry_run_report, "mapping_summary")
    nonzero = _int_value(source_summary.get("nonzero_count"))
    mapped = _int_value(mapping_summary.get("mapped_nonzero_candidates"))
    unmapped = _int_value(mapping_summary.get("unmapped_nonzero_candidates"))
    coverage = mapping_summary.get("nonzero_mapping_coverage")
    reason_codes: list[str] = []

    complete = (
        nonzero is not None
        and mapped is not None
        and unmapped == 0
        and mapped == nonzero
        and str(coverage) == "1.0000"
    )
    if complete:
        reason_codes.append("all_nonzero_candidates_mapped")
    else:
        reason_codes.append("nonzero_mapping_coverage_incomplete")
        blocking_reasons.append("nonzero_mapping_coverage_incomplete")

    return {
        "all_nonzero_candidates_mapped_required": True,
        "all_nonzero_candidates_mapped": complete,
        "mapped_nonzero_candidates": mapped,
        "unmapped_nonzero_candidates": unmapped,
        "nonzero_candidates": nonzero,
        "nonzero_mapping_coverage": coverage,
        "reason_codes": tuple(reason_codes),
    }


def _representation_decision(
    representation: str,
    write_intent: Mapping[str, Any],
    blocking_reasons: list[str],
) -> dict[str, Any]:
    reason_codes: list[str] = []
    supported = representation == OPENING_BALANCE_APPLY_REPRESENTATION
    if supported:
        reason_codes.append("patient_ledger_entry_adjustment_representation_selected")
    else:
        reason_codes.append("unsupported_write_representation")
        blocking_reasons.append("unsupported_write_representation")

    intent_representation = write_intent.get("representation")
    if intent_representation and intent_representation != OPENING_BALANCE_APPLY_REPRESENTATION:
        reason_codes.append("write_intent_representation_refused")
        blocking_reasons.append("write_intent_representation_refused")

    refused_intents = {
        "create_invoices": "invoice_creation_refused",
        "would_create_invoices": "invoice_creation_refused",
        "create_payments": "payment_creation_refused",
        "would_create_payments": "payment_creation_refused",
        "create_staging_models": "staging_model_creation_refused",
        "would_create_staging_models": "staging_model_creation_refused",
        "mutate_patient_balances": "patient_balance_mutation_refused",
        "balance_mutation": "patient_balance_mutation_refused",
        "would_mutate_balances": "patient_balance_mutation_refused",
        "other_finance_records": "other_finance_record_creation_refused",
    }
    for key, reason in refused_intents.items():
        if _truthy_intent(write_intent.get(key)):
            reason_codes.append(reason)
            blocking_reasons.append(reason)

    return {"supported": supported, "reason_codes": tuple(dict.fromkeys(reason_codes))}


def _before_counts_decision(
    before_finance_counts: Mapping[str, Any] | None,
    blocking_reasons: list[str],
) -> dict[str, Any]:
    reason_codes: list[str] = []
    counts: dict[str, int | None] = {}
    if not isinstance(before_finance_counts, Mapping):
        reason_codes.append("before_finance_counts_missing")
        blocking_reasons.append("before_finance_counts_missing")
        return {
            "required": _BEFORE_COUNT_KEYS,
            "counts": {key: None for key in _BEFORE_COUNT_KEYS},
            "reason_codes": tuple(reason_codes),
        }

    for key in _BEFORE_COUNT_KEYS:
        value = _int_value(before_finance_counts.get(key))
        counts[key] = value
        if value is None or value < 0:
            reason_codes.append(f"{key}_before_count_missing")
            blocking_reasons.append(f"{key}_before_count_missing")

    if not reason_codes:
        reason_codes.append("before_finance_counts_present")
    return {
        "required": _BEFORE_COUNT_KEYS,
        "counts": counts,
        "reason_codes": tuple(reason_codes),
    }


def _idempotency_plan(
    *,
    manifest_id: str | None,
    eligible_count: int,
    existing_manifest_rows: tuple[Mapping[str, Any], ...],
    existing_manifest_ids: tuple[str, ...],
    existing_opening_balance_markers: tuple[Mapping[str, Any], ...],
    blocking_reasons: list[str],
) -> dict[str, Any]:
    reason_codes: list[str] = []
    manifest = _clean_text(manifest_id)
    if manifest is None:
        reason_codes.append("manifest_id_missing")
        blocking_reasons.append("manifest_id_missing")

    row_shape_errors = _existing_row_shape_errors(manifest, existing_manifest_rows)
    for reason in row_shape_errors:
        reason_codes.append(reason)
        blocking_reasons.append(reason)

    if existing_opening_balance_markers:
        reason_codes.append("existing_opening_balance_marker_refused")
        blocking_reasons.append("existing_opening_balance_marker_refused")

    existing_count = len(existing_manifest_rows)
    duplicate_without_rows = manifest in existing_manifest_ids and existing_count == 0
    partial_duplicate = existing_count not in {0, eligible_count}
    duplicate_fails_closed = bool(
        existing_opening_balance_markers
        or duplicate_without_rows
        or partial_duplicate
        or row_shape_errors
    )

    if duplicate_without_rows:
        reason_codes.append("duplicate_manifest_without_row_evidence_refused")
        blocking_reasons.append("duplicate_manifest_without_row_evidence_refused")
    if partial_duplicate:
        reason_codes.append("partial_existing_manifest_rows_refused")
        blocking_reasons.append("partial_existing_manifest_rows_refused")

    would_skip = eligible_count if existing_count == eligible_count and not row_shape_errors else 0
    if would_skip:
        reason_codes.append("existing_manifest_rows_plan_skip")
    elif not duplicate_fails_closed:
        reason_codes.append("new_manifest_rows_plan_create")

    return {
        "manifest_id_required": True,
        "manifest_id": manifest,
        "existing_manifest_rows_supplied": existing_count,
        "would_skip_count": would_skip,
        "duplicate_manifest_fails_closed": duplicate_fails_closed,
        "duplicate_policy": (
            "skip only when supplied existing manifest rows match the eligible "
            "count; partial or mismatched duplicates fail closed"
        ),
        "rerun_expectation": {
            "created": 0,
            "updated": 0,
            "skipped": eligible_count,
        },
        "reason_codes": tuple(dict.fromkeys(reason_codes)),
    }


def _rollback_plan(
    *,
    manifest_id: str | None,
    write_intent: Mapping[str, Any],
    blocking_reasons: list[str],
) -> dict[str, Any]:
    reason_codes = ["manifest_scoped_rollback_only"]
    broad_deletion = _truthy_intent(write_intent.get("broad_ledger_deletion")) or _truthy_intent(
        write_intent.get("delete_ledger_broadly")
    )
    if broad_deletion:
        reason_codes.append("broad_ledger_deletion_refused")
        blocking_reasons.append("broad_ledger_deletion_refused")
    return {
        "manifest_scoped_only": True,
        "no_broad_ledger_deletion": not broad_deletion,
        "target_reference_prefix": (
            f"{OPENING_BALANCE_REFERENCE_PREFIX}:{manifest_id}:"
            if _clean_text(manifest_id)
            else None
        ),
        "reason_codes": tuple(reason_codes),
    }


def _sample_planned_rows(
    dry_run_report: Mapping[str, Any],
    *,
    manifest_id: str | None,
    sample_limit: int,
) -> tuple[dict[str, Any], ...]:
    samples = _mapping_value(dry_run_report, "samples").get(
        "eligible_opening_balance",
        (),
    )
    if not isinstance(samples, Iterable) or isinstance(samples, (str, bytes)):
        return ()
    planned: list[dict[str, Any]] = []
    for sample in samples:
        if not isinstance(sample, Mapping):
            continue
        patient_code = _clean_text(sample.get("source_patient_code"))
        planned.append(
            {
                "representation": OPENING_BALANCE_APPLY_REPRESENTATION,
                "source_name": sample.get("source_name", "PatientStats"),
                "source_patient_code": patient_code,
                "mapped_patient_id": sample.get("mapped_patient_id"),
                "amount_pence": sample.get("amount_pence"),
                "proposed_pms_direction": sample.get("proposed_pms_direction"),
                "ledger_entry_type": "adjustment",
                "ledger_method": None,
                "related_invoice_id": None,
                "reference": (
                    f"{OPENING_BALANCE_REFERENCE_PREFIX}:{manifest_id}:{patient_code}"
                    if _clean_text(manifest_id) and patient_code
                    else None
                ),
            }
        )
        if len(planned) >= sample_limit:
            break
    return tuple(planned)


def _database_name(database_target: str | None) -> str | None:
    target = _clean_text(database_target)
    if target is None:
        return None
    parsed = urlparse(target)
    if parsed.scheme and parsed.path and parsed.path != "/":
        return parsed.path.rsplit("/", 1)[-1].split("?", 1)[0] or None
    return target


def _normalize_name(value: str) -> str:
    return value.strip().lower()


def _mapping_value(mapping: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = mapping.get(key)
    return value if isinstance(value, Mapping) else {}


def _eligible_count(dry_run_report: Mapping[str, Any]) -> int | None:
    return _int_value(
        _mapping_value(dry_run_report, "eligibility_summary").get(
            "eligible_opening_balance"
        )
    )


def _refused_count(summary: Mapping[str, Any]) -> int:
    total = 0
    for decision, value in summary.items():
        if decision in {"eligible_opening_balance", "no_op_zero_balance"}:
            continue
        count = _int_value(value)
        if count is not None:
            total += count
    return total


def _component_mismatch_would_write_count(
    dry_run_report: Mapping[str, Any],
    candidate_rows: tuple[Mapping[str, Any], ...],
) -> int:
    summary = _mapping_value(dry_run_report, "eligibility_summary")
    component_summary = _mapping_value(dry_run_report, "component_consistency_summary")
    explicit = (
        _int_value(summary.get("component_mismatch_would_write"))
        or _int_value(summary.get("component_mismatch_would_write_count"))
        or _int_value(component_summary.get("would_write_mismatch_count"))
    )
    if explicit is not None:
        return explicit
    return sum(
        1
        for row in candidate_rows
        if _row_decision(row) == "component_mismatch" and _row_nonzero(row)
    )


def _ambiguous_would_write_count(
    dry_run_report: Mapping[str, Any],
    candidate_rows: tuple[Mapping[str, Any], ...],
) -> int:
    summary = _mapping_value(dry_run_report, "eligibility_summary")
    explicit = _int_value(summary.get("ambiguous_sign_would_write_count"))
    if explicit is not None:
        return explicit
    return sum(
        1
        for row in candidate_rows
        if _row_decision(row) == "ambiguous_sign" and _row_nonzero(row)
    )


def _source_drift_present(dry_run_report: Mapping[str, Any]) -> bool:
    for key in ("source_drift", "source_drift_summary", "drift", "drift_summary"):
        value = dry_run_report.get(key)
        if value:
            return True
    manifest = _mapping_value(dry_run_report, "manifest")
    for key in ("source_drift", "source_drift_summary", "drift"):
        if manifest.get(key):
            return True
    risks = dry_run_report.get("risks")
    if isinstance(risks, Iterable) and not isinstance(risks, (str, bytes)):
        return any("drift" in str(risk).lower() for risk in risks)
    return False


def _existing_row_shape_errors(
    manifest_id: str | None,
    existing_manifest_rows: tuple[Mapping[str, Any], ...],
) -> tuple[str, ...]:
    reasons: list[str] = []
    expected_prefix = (
        f"{OPENING_BALANCE_REFERENCE_PREFIX}:{manifest_id}:"
        if manifest_id
        else None
    )
    for row in existing_manifest_rows:
        row_manifest = _clean_text(row.get("manifest_id"))
        if row_manifest and manifest_id and row_manifest != manifest_id:
            reasons.append("existing_manifest_row_manifest_mismatch")
        entry_type = _clean_text(row.get("entry_type"))
        if entry_type and entry_type != "adjustment":
            reasons.append("existing_manifest_row_entry_type_mismatch")
        representation = _clean_text(row.get("representation"))
        if representation and representation != OPENING_BALANCE_APPLY_REPRESENTATION:
            reasons.append("existing_manifest_row_representation_mismatch")
        reference = _clean_text(row.get("reference"))
        if expected_prefix and reference and not reference.startswith(expected_prefix):
            reasons.append("existing_manifest_row_reference_mismatch")
    return tuple(dict.fromkeys(reasons))


def _row_decision(row: Mapping[str, Any]) -> str | None:
    return _clean_text(row.get("decision"))


def _row_nonzero(row: Mapping[str, Any]) -> bool:
    raw_sign = _clean_text(row.get("raw_sign"))
    if raw_sign in {"positive", "negative"}:
        return True
    amount_pence = _int_value(row.get("amount_pence"))
    return amount_pence is not None and amount_pence != 0


def _truthy_intent(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().lower() not in {"", "0", "false", "no", "none"}
    return bool(value)


def _int_value(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _clean_text(value: Any | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
