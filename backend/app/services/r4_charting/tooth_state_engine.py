from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Sequence

from app.models.r4_charting_canonical import R4ChartingCanonicalRecord
from app.services.tooth_state_classification import (
    ToothStateType,
    classify_tooth_state_type,
)

_REAL_DOMAIN_NAMES = frozenset({"restorative_treatment", "restorative_treatments"})
_PROXY_DOMAIN_NAMES = frozenset({"treatment_plan_item", "treatment_plan_items"})


@dataclass(frozen=True)
class ToothStateEngineRow:
    tooth: int
    tooth_key: str
    recorded_at: datetime | None
    domain: str
    is_real_domain: bool
    is_proxy_domain: bool
    source_table: str | None
    source_id: str | None
    raw_surface: object | None
    code_id: int | None
    code_label: str | None
    normalized_label: str | None
    restoration_type: ToothStateType
    surfaces: tuple[str, ...]


@dataclass(frozen=True)
class ToothStateProjectedRestoration:
    type: ToothStateType
    surfaces: tuple[str, ...]
    meta: dict[str, object]


@dataclass
class ToothStateProjectedTooth:
    restorations: list[ToothStateProjectedRestoration] = field(default_factory=list)
    missing: bool = False
    extracted: bool = False


def _canonical_payload(record: R4ChartingCanonicalRecord) -> dict[str, object]:
    if isinstance(record.payload, dict):
        return dict(record.payload)
    return {}


def _coerce_optional_int(value: object | None) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def _coerce_optional_bool(value: object | None) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    text = str(value).strip().lower()
    if not text:
        return None
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return None


def _surface_key(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip().upper()
    if text in {"M", "O", "D", "B", "L", "I"}:
        return text
    numeric = _coerce_optional_int(value)
    if numeric is None:
        return None
    return {
        1: "M",
        2: "O",
        3: "D",
        4: "B",
        5: "L",
        6: "I",
    }.get(numeric)


def _surface_keys_from_bitmask(mask: int) -> list[str]:
    if mask <= 0:
        return []
    ordered_bits: tuple[tuple[int, str], ...] = (
        (1, "M"),
        (2, "O"),
        (4, "D"),
        (8, "B"),
        (16, "L"),
        (32, "I"),
    )
    out: list[str] = []
    for bit, key in ordered_bits:
        if mask & bit:
            out.append(key)
    return out


def _extract_surface_keys(
    payload: dict[str, object],
    fallback_surface: object | None,
    *,
    bitmask: bool = False,
) -> list[str]:
    values: list[object] = []
    raw_surfaces = payload.get("surfaces")
    if isinstance(raw_surfaces, list):
        values.extend(raw_surfaces)
    elif raw_surfaces is not None:
        values.append(raw_surfaces)

    raw_surface = payload.get("surface")
    if raw_surface is not None:
        values.append(raw_surface)
    if fallback_surface is not None:
        values.append(fallback_surface)

    surface_keys: list[str] = []
    for value in values:
        if bitmask:
            numeric = _coerce_optional_int(value)
            if numeric is None:
                continue
            for key in _surface_keys_from_bitmask(numeric):
                if key not in surface_keys:
                    surface_keys.append(key)
            continue
        surface_key = _surface_key(value)
        if surface_key is None:
            continue
        if surface_key not in surface_keys:
            surface_keys.append(surface_key)
    return surface_keys


def _normalize_tooth_state_label(value: str | None) -> str | None:
    text = str(value or "").strip().lower()
    if not text:
        return None
    return " ".join(text.split())


def _resolve_tooth_state_label(
    record: R4ChartingCanonicalRecord,
    payload: dict[str, object],
    code_label: str | None,
) -> tuple[int | None, str | None]:
    resolved_code_id = record.code_id
    if resolved_code_id is None:
        resolved_code_id = _coerce_optional_int(payload.get("code_id"))
    resolved_code_label = code_label
    if not resolved_code_label:
        raw_label = payload.get("description") or payload.get("status_description") or record.status
        resolved_code_label = str(raw_label).strip() if raw_label is not None else None
    if resolved_code_label == "":
        resolved_code_label = None
    if not resolved_code_label and resolved_code_id is not None:
        resolved_code_label = "Unknown code"
    return resolved_code_id, resolved_code_label


def build_tooth_state_engine_row(
    record: R4ChartingCanonicalRecord,
    code_label: str | None,
) -> ToothStateEngineRow | None:
    payload = _canonical_payload(record)
    domain = (record.domain or "").strip().lower()
    is_real_domain = domain in _REAL_DOMAIN_NAMES
    is_proxy_domain = domain in _PROXY_DOMAIN_NAMES

    completed = _coerce_optional_bool(payload.get("completed"))
    if completed is None and is_real_domain:
        completed = _coerce_optional_bool(payload.get("complete"))
    if completed is None and is_real_domain:
        completed = True
    if completed is not True:
        return None

    tooth = _coerce_optional_int(payload.get("tooth"))
    if tooth is None:
        tooth = record.tooth
    if tooth is None or tooth <= 0:
        return None

    resolved_code_id, resolved_code_label = _resolve_tooth_state_label(record, payload, code_label)
    normalized_label = _normalize_tooth_state_label(resolved_code_label)
    restoration_type = classify_tooth_state_type(resolved_code_label)
    surfaces = tuple(
        _extract_surface_keys(
            payload,
            record.surface,
            bitmask=is_real_domain,
        )
    )

    return ToothStateEngineRow(
        tooth=tooth,
        tooth_key=str(tooth),
        recorded_at=record.recorded_at,
        domain=domain,
        is_real_domain=is_real_domain,
        is_proxy_domain=is_proxy_domain,
        source_table=record.r4_source,
        source_id=record.r4_source_id,
        raw_surface=payload.get("surface", record.surface),
        code_id=resolved_code_id,
        code_label=resolved_code_label,
        normalized_label=normalized_label,
        restoration_type=restoration_type,
        surfaces=surfaces,
    )


def _row_sort_key(row: ToothStateEngineRow) -> tuple[str, str]:
    recorded_at_key = row.recorded_at.isoformat() if row.recorded_at is not None else ""
    return (recorded_at_key, row.source_id or "")


def project_tooth_state_rows(
    rows: Sequence[ToothStateEngineRow],
) -> dict[str, ToothStateProjectedTooth]:
    real_teeth = {row.tooth_key for row in rows if row.is_real_domain}
    ordered_rows = sorted(rows, key=_row_sort_key, reverse=True)

    teeth: dict[str, ToothStateProjectedTooth] = {}
    seen_restorations: dict[str, set[str]] = {}
    blocked_teeth_after_reset: set[str] = set()

    for row in ordered_rows:
        if row.tooth_key in real_teeth and row.is_proxy_domain:
            continue
        if row.tooth_key in blocked_teeth_after_reset:
            continue
        if row.normalized_label == "reset tooth":
            blocked_teeth_after_reset.add(row.tooth_key)
            continue
        if row.normalized_label == "tooth present":
            continue

        entry = teeth.setdefault(row.tooth_key, ToothStateProjectedTooth())
        if row.restoration_type == "extraction":
            entry.extracted = True

        dedupe_key = "|".join([row.restoration_type, ",".join(row.surfaces)])
        seen = seen_restorations.setdefault(row.tooth_key, set())
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        restoration_meta: dict[str, object] = {
            "source_domain": row.domain,
            "source_table": row.source_table,
            "source_id": row.source_id,
            "completed": True,
            "raw_surface": row.raw_surface,
        }
        if row.code_id is not None:
            restoration_meta["code_id"] = row.code_id
        if row.code_label:
            restoration_meta["code_label"] = row.code_label
        if row.surfaces:
            restoration_meta["mapped_surfaces"] = list(row.surfaces)

        entry.restorations.append(
            ToothStateProjectedRestoration(
                type=row.restoration_type,
                surfaces=row.surfaces,
                meta=restoration_meta,
            )
        )

    return teeth
