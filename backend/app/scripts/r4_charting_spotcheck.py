from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.r4_charting import (
    R4BPEEntry,
    R4BPEFurcation,
    R4ChartHealingAction,
    R4FixedNote,
    R4PatientNote,
    R4PerioProbe,
    R4TemporaryNote,
    R4ToothSurface,
    R4TreatmentNote,
)
from app.services.r4_import.sqlserver_source import R4SqlServerConfig, R4SqlServerSource


def _format_dt(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        else:
            value = value.astimezone(timezone.utc)
        return value.isoformat()
    return str(value)


def _build_legacy_key(*parts: object) -> str:
    safe_parts = ["null" if part is None else str(part) for part in parts]
    return ":".join(safe_parts)


def _pg_rows(session: Session, stmt: Select, limit: int) -> list[dict[str, object]]:
    rows = session.execute(stmt.limit(limit)).mappings().all()
    normalized = []
    for row in rows:
        payload = {}
        for key, value in row.items():
            payload[key] = _format_dt(value)
        normalized.append(payload)
    return normalized


def _normalize_rows(items: list[object]) -> list[dict[str, object]]:
    normalized = []
    for item in items:
        payload = item.model_dump() if hasattr(item, "model_dump") else dict(item)
        normalized.append({key: _format_dt(value) for key, value in payload.items()})
    return normalized


def _sortable(value) -> str:
    if value is None:
        return ""
    return str(value)


def _sorted_rows(rows: list[dict[str, object]], sort_keys: list[str]) -> list[dict[str, object]]:
    if not sort_keys:
        return list(rows)
    return sorted(rows, key=lambda row: tuple(_sortable(row.get(key)) for key in sort_keys))


def _rows_for_csv(
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


def _write_csv(path: Path, rows: list[dict[str, object]], columns: list[str], sort_keys: list[str]):
    sorted_rows = _sorted_rows(rows, sort_keys)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in sorted_rows:
            writer.writerow({key: row.get(key) for key in columns})


def _date_range(rows: list[dict[str, object]], date_fields: list[str]) -> tuple[str | None, str | None]:
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


def _coerce_int(value) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value))
        except ValueError:
            return None
    return None


def _sqlserver_patient_notes(source: R4SqlServerSource, patient_code: int, limit: int):
    return _normalize_rows(source.list_patient_notes(patient_code, patient_code, limit))


def _sqlserver_temporary_notes(source: R4SqlServerSource, patient_code: int, limit: int):
    return _normalize_rows(source.list_temporary_notes(patient_code, patient_code, limit))


def _sqlserver_treatment_notes(source: R4SqlServerSource, patient_code: int, limit: int):
    return _normalize_rows(source.list_treatment_notes(patient_code, patient_code, limit))


def _sqlserver_chart_actions(source: R4SqlServerSource, patient_code: int, limit: int):
    return _normalize_rows(
        source.list_chart_healing_actions(patient_code, patient_code, limit)
    )


def _sqlserver_bpe_entries(source: R4SqlServerSource, patient_code: int, limit: int):
    return _normalize_rows(source.list_bpe_entries(patient_code, patient_code, limit))


def _sqlserver_bpe_furcations(source: R4SqlServerSource, patient_code: int, limit: int):
    bpe_patient_col = source._pick_column("BPE", ["PatientCode"])
    bpe_id_col = source._pick_column("BPE", ["BPEID", "BPEId", "ID"])
    furcation_bpe_col = source._pick_column("BPEFurcation", ["BPEID", "BPEId"])
    bpe_furcation_patient_col = source._pick_column("BPEFurcation", ["PatientCode"])
    furcation_date_col = source._pick_column(
        "BPEFurcation",
        ["Date", "RecordedDate", "EntryDate"],
    )
    if not (bpe_patient_col and bpe_id_col and furcation_bpe_col):
        return {"status": "unsupported", "reason": "BPE/BPEFurcation linkage columns missing."}
    columns = source._get_columns("BPEFurcation")
    furcation_cols = [col for col in columns if col.lower().startswith("furcation")]
    id_col = source._pick_column("BPEFurcation", ["pKey", "ID", "BPEFurcationID"])
    select_cols = []
    if id_col:
        select_cols.append(f"bf.{id_col} AS furcation_id")
    select_cols.append(f"bf.{furcation_bpe_col} AS bpe_id")
    if bpe_furcation_patient_col:
        select_cols.append(f"bf.{bpe_furcation_patient_col} AS patient_code")
    else:
        select_cols.append(f"b.{bpe_patient_col} AS patient_code")
    if furcation_date_col:
        select_cols.append(f"bf.{furcation_date_col} AS recorded_at")
    for col in furcation_cols:
        select_cols.append(f"bf.{col} AS {col.lower()}")
    query = (
        f"SELECT TOP (?) {', '.join(select_cols)} "
        f"FROM dbo.BPEFurcation bf WITH (NOLOCK) "
        f"JOIN dbo.BPE b WITH (NOLOCK) ON b.{bpe_id_col} = bf.{furcation_bpe_col} "
        f"WHERE b.{bpe_patient_col} = ? "
        f"ORDER BY bf.{furcation_bpe_col} ASC"
    )
    return _normalize_rows(source._query(query, [limit, patient_code]))


def _sqlserver_perio_probes(source: R4SqlServerSource, patient_code: int, limit: int):
    probe_trans_col = source._pick_column("PerioProbe", ["TransId", "TransID"])
    probe_tooth_col = source._pick_column("PerioProbe", ["Tooth"])
    probe_point_col = source._pick_column("PerioProbe", ["ProbingPoint", "Point"])
    probe_depth_col = source._pick_column("PerioProbe", ["PocketDepth", "Depth", "ProbeDepth"])
    probe_bleed_col = source._pick_column("PerioProbe", ["Bleeding", "BleedingScore"])
    probe_plaque_col = source._pick_column("PerioProbe", ["Plaque", "PlaqueScore"])
    probe_date_col = source._pick_column("PerioProbe", ["Date", "RecordedDate", "ProbeDate"])
    trans_ref_col = source._pick_column("Transactions", ["RefId"])
    trans_patient_col = source._pick_column("Transactions", ["PatientCode"])
    if not (probe_trans_col and probe_tooth_col and probe_point_col and trans_ref_col and trans_patient_col):
        return {"status": "unsupported", "reason": "PerioProbe/Transactions linkage columns missing."}
    selected = [
        f"pp.{probe_trans_col} AS trans_id",
        f"pp.{probe_tooth_col} AS tooth",
        f"pp.{probe_point_col} AS probing_point",
    ]
    if probe_depth_col:
        selected.append(f"pp.{probe_depth_col} AS depth")
    if probe_bleed_col:
        selected.append(f"pp.{probe_bleed_col} AS bleeding")
    if probe_plaque_col:
        selected.append(f"pp.{probe_plaque_col} AS plaque")
    if probe_date_col:
        selected.append(f"pp.{probe_date_col} AS recorded_at")
    query = (
        f"SELECT TOP (?) {', '.join(selected)}, t.{trans_patient_col} AS patient_code "
        f"FROM dbo.PerioProbe pp WITH (NOLOCK) "
        f"JOIN dbo.Transactions t WITH (NOLOCK) ON t.{trans_ref_col} = pp.{probe_trans_col} "
        f"WHERE t.{trans_patient_col} = ? "
        f"ORDER BY pp.{probe_trans_col} ASC"
    )
    return _normalize_rows(source._query(query, [limit, patient_code]))


def _sqlserver_tooth_surfaces(source: R4SqlServerSource, limit: int):
    return _normalize_rows(source.list_tooth_surfaces(limit))


def _sqlserver_fixed_notes_for_codes(
    source: R4SqlServerSource,
    codes: list[int],
    limit: int,
):
    if not codes:
        return []
    code_col = source._pick_column("FixedNotes", ["FixedNoteCode"])
    if not code_col:
        return {"status": "unsupported", "reason": "FixedNotes missing FixedNoteCode column."}
    category_col = source._pick_column("FixedNotes", ["CategoryNumber", "CategoryNo"])
    desc_col = source._pick_column("FixedNotes", ["Description", "NoteDesc"])
    note_col = source._pick_column("FixedNotes", ["Note", "Notes", "NoteText"])
    tooth_col = source._pick_column("FixedNotes", ["Tooth"])
    surface_col = source._pick_column("FixedNotes", ["Surface"])
    placeholders = ", ".join("?" for _ in codes)
    select_cols = [f"{code_col} AS fixed_note_code"]
    if category_col:
        select_cols.append(f"{category_col} AS category_number")
    if desc_col:
        select_cols.append(f"{desc_col} AS description")
    if note_col:
        select_cols.append(f"{note_col} AS note")
    if tooth_col:
        select_cols.append(f"{tooth_col} AS tooth")
    if surface_col:
        select_cols.append(f"{surface_col} AS surface")
    query = (
        f"SELECT TOP (?) {', '.join(select_cols)} "
        f"FROM dbo.FixedNotes WITH (NOLOCK) "
        f"WHERE {code_col} IN ({placeholders}) "
        f"ORDER BY {code_col} ASC"
    )
    return _normalize_rows(source._query(query, [limit, *codes]))


def _parse_entities(raw: str | None, available: dict[str, str]) -> list[str]:
    if not raw:
        return sorted(set(available.values()))
    entities = []
    for item in raw.split(","):
        key = item.strip().lower()
        if not key:
            continue
        canonical = available.get(key)
        if canonical and canonical not in entities:
            entities.append(canonical)
    return entities


ENTITY_ALIASES = {
    "patient_notes": "patient_notes",
    "temporary_notes": "temporary_notes",
    "treatment_notes": "treatment_notes",
    "chart_healing_actions": "chart_healing_actions",
    "chart_actions": "chart_healing_actions",
    "bpe": "bpe",
    "bpe_entries": "bpe",
    "bpe_furcations": "bpe_furcations",
    "perio_probes": "perio_probes",
    "tooth_surfaces": "tooth_surfaces",
    "fixed_notes": "fixed_notes",
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
    "temporary_notes": ["patient_code", "note", "legacy_updated_at", "user_code"],
    "treatment_notes": ["patient_code", "legacy_treatment_note_id", "note_date", "note", "user_code"],
    "chart_healing_actions": [
        "patient_code",
        "legacy_action_id",
        "action_date",
        "action_type",
        "tooth",
        "surface",
        "status",
        "notes",
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
}

ENTITY_SORT_KEYS = {
    "patient_notes": ["patient_code", "note_date", "note_number", "legacy_note_key"],
    "temporary_notes": ["patient_code", "legacy_updated_at"],
    "treatment_notes": ["patient_code", "note_date", "legacy_treatment_note_id"],
    "chart_healing_actions": ["patient_code", "action_date", "legacy_action_id"],
    "bpe": ["patient_code", "recorded_at", "legacy_bpe_id", "legacy_bpe_key"],
    "bpe_furcations": ["patient_code", "recorded_at", "legacy_bpe_id", "tooth", "furcation"],
    "perio_probes": ["patient_code", "recorded_at", "tooth", "probing_point", "legacy_trans_id"],
    "tooth_surfaces": ["legacy_tooth_id", "legacy_surface_no"],
    "fixed_notes": ["patient_code", "legacy_fixed_note_code"],
}

ENTITY_DATE_FIELDS = {
    "patient_notes": ["note_date"],
    "temporary_notes": ["legacy_updated_at"],
    "treatment_notes": ["note_date"],
    "chart_healing_actions": ["action_date"],
    "bpe": ["recorded_at"],
    "bpe_furcations": ["recorded_at"],
    "perio_probes": ["recorded_at"],
}

ENTITY_LINKAGE = {
    "patient_notes": "patient_notes.patient_code",
    "temporary_notes": "temporary_notes.patient_code",
    "treatment_notes": "treatment_notes.patient_code",
    "chart_healing_actions": "chart_healing_actions.patient_code",
    "bpe": "bpe.patient_code_or_bpe_id",
    "bpe_furcations": "bpefurcation.bpe_id_join",
    "perio_probes": "transactions.ref_id_join",
    "tooth_surfaces": "global_lookup",
    "fixed_notes": "fixed_note_code_lookup",
}


def _collect_fixed_note_codes(rows: list[dict[str, object]]) -> list[int]:
    codes = []
    seen = set()
    for row in rows:
        raw = row.get("fixed_note_code") or row.get("legacy_fixed_note_code")
        code = _coerce_int(raw)
        if code is None or code in seen:
            continue
        seen.add(code)
        codes.append(code)
    return codes


def _extract_rows(payload: object) -> tuple[list[dict[str, object]], dict[str, object]]:
    if isinstance(payload, dict) and payload.get("status") == "unsupported":
        return [], payload
    if isinstance(payload, list):
        return payload, {"status": "ok"}
    return [], {"status": "unsupported", "reason": "Unexpected payload type."}


def _normalize_entity_rows(
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
                payload["legacy_probe_key"] = _build_legacy_key(
                    trans_id,
                    payload.get("tooth"),
                    probing_point,
                )
        elif entity == "bpe":
            bpe_id = payload.get("legacy_bpe_id") or payload.get("bpe_id")
            payload["legacy_bpe_id"] = bpe_id
            if payload.get("legacy_bpe_key") is None:
                payload["legacy_bpe_key"] = str(bpe_id) if bpe_id is not None else _build_legacy_key(
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
                    else _build_legacy_key(
                        bpe_id,
                        payload.get("patient_code") or patient_code,
                        payload.get("tooth"),
                        payload.get("furcation"),
                    )
                )
        elif entity == "chart_healing_actions":
            if payload.get("legacy_action_id") is None and payload.get("action_id") is not None:
                payload["legacy_action_id"] = payload.get("action_id")
        elif entity == "treatment_notes":
            if payload.get("legacy_treatment_note_id") is None and payload.get("note_id") is not None:
                payload["legacy_treatment_note_id"] = payload.get("note_id")
        elif entity == "patient_notes":
            if payload.get("legacy_note_key") is None:
                payload["legacy_note_key"] = _build_legacy_key(
                    payload.get("patient_code") or patient_code,
                    payload.get("note_number") or payload.get("note_date"),
                )
        elif entity == "fixed_notes":
            if payload.get("legacy_fixed_note_code") is None and payload.get("fixed_note_code") is not None:
                payload["legacy_fixed_note_code"] = payload.get("fixed_note_code")
        elif entity == "tooth_surfaces":
            if payload.get("legacy_tooth_id") is None and payload.get("tooth_id") is not None:
                payload["legacy_tooth_id"] = payload.get("tooth_id")
            if payload.get("legacy_surface_no") is None and payload.get("surface_no") is not None:
                payload["legacy_surface_no"] = payload.get("surface_no")
        normalized.append(payload)
    return normalized


def main() -> int:
    parser = argparse.ArgumentParser(description="Spot-check R4 charting rows for a patient.")
    parser.add_argument("--patient-code", type=int, required=True)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--out-dir", type=Path)
    parser.add_argument("--format", choices=["json", "csv"], default="json")
    parser.add_argument("--entities", type=str)
    args = parser.parse_args()

    entities = _parse_entities(args.entities, ENTITY_ALIASES)
    if args.format == "csv" and args.out_dir is None:
        parser.error("--out-dir is required when --format=csv.")

    config = R4SqlServerConfig.from_env()
    config.require_enabled()
    source = R4SqlServerSource(config)

    sqlserver: dict[str, object] = {}

    session = SessionLocal()
    try:
        patient_code = args.patient_code
        postgres: dict[str, object] = {}
        sqlserver_patient_notes = None
        postgres_patient_notes = None
        if "patient_notes" in entities or "fixed_notes" in entities:
            sqlserver_patient_notes = _sqlserver_patient_notes(source, patient_code, args.limit)
            postgres_patient_notes = _pg_rows(
                session,
                select(
                    R4PatientNote.legacy_patient_code.label("patient_code"),
                    R4PatientNote.legacy_note_key.label("legacy_note_key"),
                    R4PatientNote.legacy_note_number.label("note_number"),
                    R4PatientNote.note_date.label("note_date"),
                    R4PatientNote.note.label("note"),
                    R4PatientNote.tooth.label("tooth"),
                    R4PatientNote.surface.label("surface"),
                    R4PatientNote.category_number.label("category_number"),
                    R4PatientNote.fixed_note_code.label("fixed_note_code"),
                    R4PatientNote.user_code.label("user_code"),
                ).where(R4PatientNote.legacy_patient_code == patient_code),
                args.limit,
            )
            if "patient_notes" in entities:
                sqlserver["patient_notes"] = sqlserver_patient_notes
                postgres["patient_notes"] = postgres_patient_notes

        if "temporary_notes" in entities:
            sqlserver["temporary_notes"] = _sqlserver_temporary_notes(source, patient_code, args.limit)
            postgres["temporary_notes"] = _pg_rows(
                session,
                select(
                    R4TemporaryNote.legacy_patient_code.label("patient_code"),
                    R4TemporaryNote.note.label("note"),
                    R4TemporaryNote.legacy_updated_at.label("legacy_updated_at"),
                    R4TemporaryNote.user_code.label("user_code"),
                ).where(R4TemporaryNote.legacy_patient_code == patient_code),
                args.limit,
            )

        if "treatment_notes" in entities:
            sqlserver["treatment_notes"] = _sqlserver_treatment_notes(source, patient_code, args.limit)
            postgres["treatment_notes"] = _pg_rows(
                session,
                select(
                    R4TreatmentNote.legacy_patient_code.label("patient_code"),
                    R4TreatmentNote.legacy_treatment_note_id.label("legacy_treatment_note_id"),
                    R4TreatmentNote.note_date.label("note_date"),
                    R4TreatmentNote.note.label("note"),
                    R4TreatmentNote.user_code.label("user_code"),
                ).where(R4TreatmentNote.legacy_patient_code == patient_code),
                args.limit,
            )

        if "chart_healing_actions" in entities:
            sqlserver["chart_healing_actions"] = _sqlserver_chart_actions(source, patient_code, args.limit)
            postgres["chart_healing_actions"] = _pg_rows(
                session,
                select(
                    R4ChartHealingAction.legacy_patient_code.label("patient_code"),
                    R4ChartHealingAction.legacy_action_id.label("legacy_action_id"),
                    R4ChartHealingAction.action_date.label("action_date"),
                    R4ChartHealingAction.action_type.label("action_type"),
                    R4ChartHealingAction.tooth.label("tooth"),
                    R4ChartHealingAction.surface.label("surface"),
                    R4ChartHealingAction.status.label("status"),
                    R4ChartHealingAction.notes.label("notes"),
                    R4ChartHealingAction.user_code.label("user_code"),
                ).where(R4ChartHealingAction.legacy_patient_code == patient_code),
                args.limit,
            )

        if "bpe" in entities:
            sqlserver["bpe"] = _sqlserver_bpe_entries(source, patient_code, args.limit)
            postgres["bpe"] = _pg_rows(
                session,
                select(
                    R4BPEEntry.legacy_patient_code.label("patient_code"),
                    R4BPEEntry.legacy_bpe_key.label("legacy_bpe_key"),
                    R4BPEEntry.legacy_bpe_id.label("legacy_bpe_id"),
                    R4BPEEntry.recorded_at.label("recorded_at"),
                    R4BPEEntry.sextant_1.label("sextant_1"),
                    R4BPEEntry.sextant_2.label("sextant_2"),
                    R4BPEEntry.sextant_3.label("sextant_3"),
                    R4BPEEntry.sextant_4.label("sextant_4"),
                    R4BPEEntry.sextant_5.label("sextant_5"),
                    R4BPEEntry.sextant_6.label("sextant_6"),
                ).where(R4BPEEntry.legacy_patient_code == patient_code),
                args.limit,
            )

        if "bpe_furcations" in entities:
            sqlserver["bpe_furcations"] = _sqlserver_bpe_furcations(source, patient_code, args.limit)
            postgres["bpe_furcations"] = _pg_rows(
                session,
                select(
                    R4BPEFurcation.legacy_patient_code.label("patient_code"),
                    R4BPEFurcation.legacy_bpe_furcation_key.label("legacy_bpe_furcation_key"),
                    R4BPEFurcation.legacy_bpe_id.label("legacy_bpe_id"),
                    R4BPEFurcation.recorded_at.label("recorded_at"),
                    R4BPEFurcation.tooth.label("tooth"),
                    R4BPEFurcation.furcation.label("furcation"),
                    R4BPEFurcation.sextant.label("sextant"),
                ).where(R4BPEFurcation.legacy_patient_code == patient_code),
                args.limit,
            )

        if "perio_probes" in entities:
            sqlserver["perio_probes"] = _sqlserver_perio_probes(source, patient_code, args.limit)
            postgres["perio_probes"] = []
            sqlserver_probes, _ = _extract_rows(sqlserver["perio_probes"])
            trans_ids_raw = [row.get("trans_id") for row in sqlserver_probes]
            trans_ids = [_coerce_int(value) for value in trans_ids_raw]
            trans_ids = [value for value in trans_ids if value is not None]
            if trans_ids:
                postgres["perio_probes"] = _pg_rows(
                    session,
                    select(
                        R4PerioProbe.legacy_patient_code.label("patient_code"),
                        R4PerioProbe.legacy_probe_key.label("legacy_probe_key"),
                        R4PerioProbe.legacy_trans_id.label("legacy_trans_id"),
                        R4PerioProbe.recorded_at.label("recorded_at"),
                        R4PerioProbe.tooth.label("tooth"),
                        R4PerioProbe.probing_point.label("probing_point"),
                        R4PerioProbe.depth.label("depth"),
                        R4PerioProbe.bleeding.label("bleeding"),
                        R4PerioProbe.plaque.label("plaque"),
                    ).where(R4PerioProbe.legacy_trans_id.in_(trans_ids)),
                    args.limit,
                )

        if "tooth_surfaces" in entities:
            sqlserver["tooth_surfaces"] = _sqlserver_tooth_surfaces(source, args.limit)
            postgres["tooth_surfaces"] = _pg_rows(
                session,
                select(
                    R4ToothSurface.legacy_tooth_id.label("legacy_tooth_id"),
                    R4ToothSurface.legacy_surface_no.label("legacy_surface_no"),
                    R4ToothSurface.label.label("label"),
                    R4ToothSurface.short_label.label("short_label"),
                    R4ToothSurface.sort_order.label("sort_order"),
                ),
                args.limit,
            )

        if "fixed_notes" in entities:
            fixed_note_rows = []
            if isinstance(sqlserver_patient_notes, list):
                fixed_note_rows.extend(sqlserver_patient_notes)
            if postgres_patient_notes:
                fixed_note_rows.extend(postgres_patient_notes)
            fixed_note_codes = _collect_fixed_note_codes(fixed_note_rows)
            sqlserver["fixed_notes"] = _sqlserver_fixed_notes_for_codes(
                source,
                fixed_note_codes,
                args.limit,
            )
            postgres["fixed_notes"] = _pg_rows(
                session,
                select(
                    R4FixedNote.legacy_fixed_note_code.label("legacy_fixed_note_code"),
                    R4FixedNote.category_number.label("category_number"),
                    R4FixedNote.description.label("description"),
                    R4FixedNote.note.label("note"),
                    R4FixedNote.tooth.label("tooth"),
                    R4FixedNote.surface.label("surface"),
                ).where(R4FixedNote.legacy_fixed_note_code.in_(fixed_note_codes)),
                args.limit,
            )
    finally:
        session.close()

    if args.format == "csv":
        out_dir = args.out_dir
        assert out_dir is not None
        out_dir.mkdir(parents=True, exist_ok=True)
        index_rows = []
        for entity in entities:
            sqlserver_rows, sqlserver_meta = _extract_rows(sqlserver.get(entity, []))
            postgres_rows, _ = _extract_rows(postgres.get(entity, []))
            sqlserver_rows = _normalize_entity_rows(entity, sqlserver_rows, patient_code)
            postgres_rows = _normalize_entity_rows(entity, postgres_rows, patient_code)
            csv_columns = ENTITY_COLUMNS[entity]
            sqlserver_csv = _rows_for_csv(sqlserver_rows, csv_columns, patient_code)
            postgres_csv = _rows_for_csv(postgres_rows, csv_columns, patient_code)
            _write_csv(
                out_dir / f"sqlserver_{entity}.csv",
                sqlserver_csv,
                csv_columns,
                ENTITY_SORT_KEYS.get(entity, []),
            )
            _write_csv(
                out_dir / f"postgres_{entity}.csv",
                postgres_csv,
                csv_columns,
                ENTITY_SORT_KEYS.get(entity, []),
            )
            sqlserver_min, sqlserver_max = _date_range(sqlserver_rows, ENTITY_DATE_FIELDS.get(entity, []))
            postgres_min, postgres_max = _date_range(postgres_rows, ENTITY_DATE_FIELDS.get(entity, []))
            index_rows.append(
                {
                    "entity": entity,
                    "linkage_method": ENTITY_LINKAGE.get(entity),
                    "sqlserver_status": sqlserver_meta.get("status"),
                    "sqlserver_reason": sqlserver_meta.get("reason"),
                    "sqlserver_count": len(sqlserver_rows),
                    "sqlserver_date_min": sqlserver_min,
                    "sqlserver_date_max": sqlserver_max,
                    "postgres_count": len(postgres_rows),
                    "postgres_date_min": postgres_min,
                    "postgres_date_max": postgres_max,
                }
            )
        index_columns = [
            "entity",
            "linkage_method",
            "sqlserver_status",
            "sqlserver_reason",
            "sqlserver_count",
            "sqlserver_date_min",
            "sqlserver_date_max",
            "postgres_count",
            "postgres_date_min",
            "postgres_date_max",
        ]
        _write_csv(out_dir / "index.csv", index_rows, index_columns, ["entity"])
    else:
        payload = {
            "patient_code": args.patient_code,
            "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "sqlserver": sqlserver,
            "postgres": postgres,
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
