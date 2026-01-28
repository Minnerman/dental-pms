from __future__ import annotations

import csv
import io
from datetime import datetime, timezone


def format_dt(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        else:
            value = value.astimezone(timezone.utc)
        return value.isoformat()
    return str(value)


def build_legacy_key(*parts: object) -> str:
    safe_parts = ["null" if part is None else str(part) for part in parts]
    return ":".join(safe_parts)


ENTITY_ALIASES = {
    "patient_notes": "patient_notes",
    "notes": "patient_notes",
    "bpe": "bpe",
    "bpe_entries": "bpe",
    "bpe_furcations": "bpe_furcations",
    "perio_probes": "perio_probes",
    "perio_plaque": "perio_plaque",
    "tooth_surfaces": "tooth_surfaces",
    "fixed_notes": "fixed_notes",
    "note_categories": "note_categories",
}

ENTITY_COLUMNS = {
    "patient_notes": [
        "patient_code",
        "legacy_note_key",
        "note_number",
        "note_date",
        "note",
        "tooth",
        "surface",
        "category_number",
        "fixed_note_code",
        "user_code",
    ],
    "bpe": [
        "patient_code",
        "legacy_bpe_key",
        "legacy_bpe_id",
        "recorded_at",
        "sextant_1",
        "sextant_2",
        "sextant_3",
        "sextant_4",
        "sextant_5",
        "sextant_6",
    ],
    "bpe_furcations": [
        "patient_code",
        "legacy_bpe_furcation_key",
        "legacy_bpe_id",
        "recorded_at",
        "tooth",
        "furcation",
        "sextant",
    ],
    "perio_probes": [
        "patient_code",
        "legacy_probe_key",
        "legacy_trans_id",
        "recorded_at",
        "tooth",
        "probing_point",
        "depth",
        "bleeding",
        "plaque",
    ],
    "perio_plaque": [
        "patient_code",
        "legacy_plaque_key",
        "legacy_trans_id",
        "recorded_at",
        "tooth",
        "plaque",
        "bleeding",
    ],
    "tooth_surfaces": [
        "legacy_tooth_id",
        "legacy_surface_no",
        "label",
        "short_label",
        "sort_order",
    ],
    "fixed_notes": [
        "patient_code",
        "legacy_fixed_note_code",
        "category_number",
        "description",
        "note",
        "tooth",
        "surface",
    ],
    "note_categories": [
        "patient_code",
        "legacy_category_number",
        "description",
    ],
}

ENTITY_SORT_KEYS = {
    "patient_notes": ["patient_code", "note_date", "note_number", "legacy_note_key"],
    "bpe": ["patient_code", "recorded_at", "legacy_bpe_id", "legacy_bpe_key"],
    "bpe_furcations": ["patient_code", "recorded_at", "legacy_bpe_id", "tooth", "furcation"],
    "perio_probes": ["patient_code", "recorded_at", "tooth", "probing_point", "legacy_trans_id"],
    "perio_plaque": ["patient_code", "recorded_at", "tooth", "legacy_trans_id"],
    "tooth_surfaces": ["legacy_tooth_id", "legacy_surface_no"],
    "fixed_notes": ["patient_code", "legacy_fixed_note_code"],
    "note_categories": ["patient_code", "legacy_category_number"],
}

ENTITY_DATE_FIELDS = {
    "patient_notes": ["note_date"],
    "bpe": ["recorded_at"],
    "bpe_furcations": ["recorded_at"],
    "perio_probes": ["recorded_at"],
    "perio_plaque": ["recorded_at"],
}

ENTITY_LINKAGE = {
    "patient_notes": "patient_notes.patient_code",
    "bpe": "bpe.patient_code_or_bpe_id",
    "bpe_furcations": "bpefurcation.bpe_id_join",
    "perio_probes": "transactions.ref_id_join",
    "perio_plaque": "transactions.ref_id_join",
    "tooth_surfaces": "global_lookup",
    "fixed_notes": "fixed_note_code_lookup",
    "note_categories": "note_categories.global_lookup",
}


def parse_entities(raw: str | None, available: dict[str, str]) -> list[str]:
    if not raw:
        return sorted(set(available.values()))
    entities: list[str] = []
    for item in raw.split(","):
        key = item.strip().lower()
        if not key:
            continue
        canonical = available.get(key)
        if canonical and canonical not in entities:
            entities.append(canonical)
    return entities


def normalize_entity_rows(
    entity: str,
    rows: list[dict[str, object]],
    patient_code: int | None,
) -> list[dict[str, object]]:
    normalized: list[dict[str, object]] = []
    for row in rows:
        payload = dict(row)
        if entity == "perio_probes":
            trans_id = payload.get("legacy_trans_id") or payload.get("trans_id") or payload.get("transid")
            payload["legacy_trans_id"] = trans_id
            probing_point = payload.get("probing_point") or payload.get("probingpoint")
            payload["probing_point"] = probing_point
            if payload.get("legacy_probe_key") is None:
                payload["legacy_probe_key"] = build_legacy_key(
                    trans_id,
                    payload.get("tooth"),
                    probing_point,
                )
        elif entity == "bpe":
            bpe_id = payload.get("legacy_bpe_id") or payload.get("bpe_id")
            payload["legacy_bpe_id"] = bpe_id
            if payload.get("legacy_bpe_key") is None:
                payload["legacy_bpe_key"] = str(bpe_id) if bpe_id is not None else build_legacy_key(
                    payload.get("patient_code") or patient_code,
                    payload.get("recorded_at"),
                )
        elif entity == "bpe_furcations":
            bpe_id = payload.get("legacy_bpe_id") or payload.get("bpe_id")
            payload["legacy_bpe_id"] = bpe_id
            furcation_id = payload.get("furcation_id")
            if payload.get("legacy_bpe_furcation_key") is None:
                payload["legacy_bpe_furcation_key"] = (
                    str(furcation_id)
                    if furcation_id is not None
                    else build_legacy_key(
                        bpe_id,
                        payload.get("patient_code") or patient_code,
                        payload.get("tooth"),
                        payload.get("furcation"),
                    )
                )
        elif entity == "patient_notes":
            if payload.get("legacy_note_key") is None:
                payload["legacy_note_key"] = build_legacy_key(
                    payload.get("patient_code") or patient_code,
                    payload.get("note_number") or payload.get("note_date"),
                )
        elif entity == "perio_plaque":
            trans_id = payload.get("legacy_trans_id") or payload.get("trans_id") or payload.get("transid")
            payload["legacy_trans_id"] = trans_id
            if payload.get("legacy_plaque_key") is None:
                payload["legacy_plaque_key"] = build_legacy_key(
                    trans_id,
                    payload.get("tooth"),
                )
        elif entity == "fixed_notes":
            if payload.get("legacy_fixed_note_code") is None and payload.get("fixed_note_code") is not None:
                payload["legacy_fixed_note_code"] = payload.get("fixed_note_code")
        elif entity == "note_categories":
            if payload.get("legacy_category_number") is None and payload.get("category_number") is not None:
                payload["legacy_category_number"] = payload.get("category_number")
        elif entity == "tooth_surfaces":
            if payload.get("legacy_tooth_id") is None and payload.get("tooth_id") is not None:
                payload["legacy_tooth_id"] = payload.get("tooth_id")
            if payload.get("legacy_surface_no") is None and payload.get("surface_no") is not None:
                payload["legacy_surface_no"] = payload.get("surface_no")
        normalized.append(payload)
    return normalized


def _sortable(value) -> str:
    if value is None:
        return ""
    return str(value)


def sorted_rows(rows: list[dict[str, object]], sort_keys: list[str]) -> list[dict[str, object]]:
    if not sort_keys:
        return list(rows)
    return sorted(rows, key=lambda row: tuple(_sortable(row.get(key)) for key in sort_keys))


def rows_for_csv(
    rows: list[dict[str, object]],
    columns: list[str],
    default_patient_code: int | None,
) -> list[dict[str, object]]:
    normalized = []
    for row in rows:
        payload = {col: row.get(col) for col in columns}
        if default_patient_code is not None and "patient_code" in columns:
            if payload.get("patient_code") is None:
                payload["patient_code"] = default_patient_code
        normalized.append(payload)
    return normalized


def csv_text(rows: list[dict[str, object]], columns: list[str], sort_keys: list[str]) -> str:
    sorted_payload = sorted_rows(rows, sort_keys)
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns)
    writer.writeheader()
    for row in sorted_payload:
        writer.writerow({key: row.get(key) for key in columns})
    return buffer.getvalue()


def date_range(
    rows: list[dict[str, object]],
    date_fields: list[str],
) -> tuple[str | None, str | None]:
    if not date_fields:
        return None, None
    values = []
    for row in rows:
        for field in date_fields:
            value = row.get(field)
            if value:
                values.append(value)
                break
    if not values:
        return None, None
    return min(values), max(values)
