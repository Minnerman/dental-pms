from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

__all__ = [
    "GUARDED_FINANCE_IMPORT_APPLY_CONFIRMATION_TOKEN",
    "GUARDED_FINANCE_IMPORT_PRODUCTION_GATE_TOKEN",
    "GuardedFinanceImportExecutionError",
    "build_guarded_finance_import_execution_packet",
    "load_execution_manifest",
    "write_classification_packet",
]


GUARDED_FINANCE_IMPORT_APPLY_CONFIRMATION_TOKEN = (
    "GUARDED_FINANCE_IMPORT_APPLY"
)
GUARDED_FINANCE_IMPORT_PRODUCTION_GATE_TOKEN = (
    "OWNER_AUTHORISED_PRODUCTION_FINANCE_IMPORT"
)

_SUPPORTED_CATEGORY = "opening-balance"
_UNSUPPORTED_CATEGORY_REASONS = {
    "invoice": "invoice_import_not_supported_by_guarded_path",
    "payment": "payment_import_not_supported_by_guarded_path",
    "staging": "staging_import_not_supported_by_guarded_path",
}
_LIVE_TARGETS = {
    "production",
    "live",
    "default",
    "live-default",
    "live/default",
    "actual-production-postgres",
}
_SAFE_NON_LIVE_TARGETS = {"scratch", "test", "non-live", "nonlive"}


class GuardedFinanceImportExecutionError(RuntimeError):
    pass


def load_execution_manifest(path: str | Path) -> Mapping[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise GuardedFinanceImportExecutionError(
            "Execution manifest is missing or unreadable."
        ) from exc
    except json.JSONDecodeError as exc:
        raise GuardedFinanceImportExecutionError(
            "Execution manifest JSON is invalid."
        ) from exc
    if not isinstance(payload, Mapping):
        raise GuardedFinanceImportExecutionError(
            "Execution manifest JSON must contain an object."
        )
    return payload


def build_guarded_finance_import_execution_packet(
    *,
    manifest: Mapping[str, Any] | None,
    import_category: str | None,
    target_classification: str | None,
    apply_requested: bool = False,
    apply_confirmation: str | None = None,
    production_execution_gate: str | None = None,
    no_secrets_exposed: bool = False,
    no_patient_data_exposed: bool = False,
    no_private_paths_exposed: bool = False,
    no_backup_contents_exposed: bool = False,
) -> dict[str, Any]:
    """Build a classification-only finance/import execution readiness packet.

    This helper is intentionally pure: it does not open databases, read R4,
    inspect production, or execute import work. It validates the operator's
    future execution inputs and fails closed before any later writer can run.
    """

    reasons: list[str] = []
    blockers: list[str] = []
    manifest_obj = manifest if isinstance(manifest, Mapping) else {}
    if not manifest_obj:
        blockers.append("manifest_missing_or_unclear")

    category = _normalize(import_category) or _manifest_category(manifest_obj)
    if category is None:
        blockers.append("import_category_missing_or_unclear")
    elif category != _SUPPORTED_CATEGORY:
        blockers.append(
            _UNSUPPORTED_CATEGORY_REASONS.get(
                category,
                "unsupported_import_category",
            )
        )
    else:
        reasons.append("opening_balance_category_supported")

    manifest_id = _manifest_id(manifest_obj)
    if manifest_obj and manifest_id is None:
        blockers.append("manifest_id_missing_or_unclear")

    if _manifest_declares_sensitive_committed_data(manifest_obj):
        blockers.append("manifest_declares_sensitive_committed_data")

    target = _normalize(target_classification) or _manifest_target(manifest_obj)
    if target is None:
        blockers.append("target_classification_missing_or_unclear")
    elif target in _LIVE_TARGETS:
        if production_execution_gate == GUARDED_FINANCE_IMPORT_PRODUCTION_GATE_TOKEN:
            reasons.append("production_execution_gate_accepted")
        else:
            blockers.append("production_execution_gate_required")
    elif target in _SAFE_NON_LIVE_TARGETS:
        reasons.append("non_live_target_classification_accepted")
    else:
        blockers.append("target_classification_unclear")

    if apply_requested:
        if apply_confirmation == GUARDED_FINANCE_IMPORT_APPLY_CONFIRMATION_TOKEN:
            reasons.append("apply_confirmation_accepted")
        else:
            blockers.append("apply_confirmation_required")
    else:
        reasons.append("default_dry_run_no_write")

    safety_confirmations = {
        "No secrets exposed": _yes_no(no_secrets_exposed),
        "No patient data exposed": _yes_no(no_patient_data_exposed),
        "No private paths exposed": _yes_no(no_private_paths_exposed),
        "No backup contents exposed": _yes_no(no_backup_contents_exposed),
    }
    for label, value in safety_confirmations.items():
        if value != "yes":
            blockers.append(_safety_blocker(label))

    opening_balance_ready = (
        "ready"
        if category == _SUPPORTED_CATEGORY and not blockers
        else "blocked"
    )
    invoice_payment_staging_ready = "blocked"

    if blockers:
        blocker_classification = "; ".join(dict.fromkeys(blockers))
    else:
        blocker_classification = (
            "invoice/payment/staging import remains blocked by this guarded "
            "path; import execution has not run"
        )

    if reasons:
        reason_classification = "; ".join(dict.fromkeys(reasons))
    else:
        reason_classification = "guarded finance/import execution gate failed closed"

    return {
        "Guarded finance/import process available": "yes",
        "Opening-balance/live finance import execution readiness": (
            opening_balance_ready
        ),
        "Invoice/payment/staging import execution readiness": (
            invoice_payment_staging_ready
        ),
        "finance_import_ready": False,
        "Apply/write mode requested": _yes_no(apply_requested),
        "Execution performed": "no",
        "Reason classification": reason_classification,
        "Blocker classification": blocker_classification,
        **safety_confirmations,
    }


def write_classification_packet(path: str | Path, packet: Mapping[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(dict(packet), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _manifest_category(manifest: Mapping[str, Any]) -> str | None:
    for value in (
        manifest.get("import_category"),
        manifest.get("category"),
        _nested(manifest, "execution", "import_category"),
        _nested(manifest, "evidence_requirements", "import_category"),
    ):
        normalized = _normalize(value)
        if normalized:
            return normalized
    return None


def _manifest_id(manifest: Mapping[str, Any]) -> str | None:
    for value in (
        manifest.get("manifest_id"),
        _nested(manifest, "fixture", "manifest_id"),
        _nested(manifest, "evidence_requirements", "manifest_id"),
        _nested(manifest, "manifest", "manifest_id"),
    ):
        text = _clean_text(value)
        if text:
            return text
    return None


def _manifest_target(manifest: Mapping[str, Any]) -> str | None:
    for value in (
        manifest.get("target_classification"),
        _nested(manifest, "target", "classification"),
        _nested(manifest, "evidence_requirements", "target_classification"),
    ):
        normalized = _normalize(value)
        if normalized:
            return normalized.replace("_", "-")
    return None


def _manifest_declares_sensitive_committed_data(manifest: Mapping[str, Any]) -> bool:
    sensitive_policy = _mapping(manifest.get("sensitive_data_policy"))
    safety = _mapping(manifest.get("safety"))
    return any(
        value is True
        for value in (
            sensitive_policy.get("committed_fixture_contains_real_r4_data"),
            sensitive_policy.get("committed_fixture_contains_real_patient_data"),
            safety.get("real_patient_data"),
            safety.get("real_r4_artifact"),
        )
    )


def _nested(mapping: Mapping[str, Any], *keys: str) -> Any:
    current: Any = mapping
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _normalize(value: Any) -> str | None:
    text = _clean_text(value)
    return text.lower().replace("_", "-") if text else None


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _safety_blocker(label: str) -> str:
    return label.lower().replace(" ", "_") + "_not_confirmed"
