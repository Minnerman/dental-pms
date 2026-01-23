from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.r4_charting import (
    R4BPEEntry,
    R4BPEFurcation,
    R4ChartHealingAction,
    R4PatientNote,
    R4PerioProbe,
    R4TemporaryNote,
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
    if not (bpe_patient_col and bpe_id_col and furcation_bpe_col):
        return {"status": "unsupported", "reason": "BPE/BPEFurcation linkage columns missing."}
    columns = source._get_columns("BPEFurcation")
    furcation_cols = [col for col in columns if col.lower().startswith("furcation")]
    id_col = source._pick_column("BPEFurcation", ["pKey", "ID", "BPEFurcationID"])
    select_cols = []
    if id_col:
        select_cols.append(f"bf.{id_col} AS furcation_id")
    select_cols.append(f"bf.{furcation_bpe_col} AS bpe_id")
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
    trans_ref_col = source._pick_column("Transactions", ["RefId"])
    trans_patient_col = source._pick_column("Transactions", ["PatientCode"])
    if not (probe_trans_col and trans_ref_col and trans_patient_col):
        return {"status": "unsupported", "reason": "PerioProbe/Transactions linkage columns missing."}
    probe_columns = source._get_columns("PerioProbe")
    selected = []
    for name in ("TransId", "Tooth", "ProbingPoint", "PocketDepth", "Depth", "ProbeDepth"):
        if name in probe_columns:
            selected.append(f"pp.{name} AS {name.lower()}")
    for name in ("Bleeding", "BleedingScore"):
        if name in probe_columns:
            selected.append(f"pp.{name} AS {name.lower()}")
    for name in ("SubPlaque", "SupraPlaque", "Plaque", "PlaqueScore"):
        if name in probe_columns:
            selected.append(f"pp.{name} AS {name.lower()}")
    if not selected:
        selected = [f"pp.{probe_trans_col} AS trans_id"]
    query = (
        f"SELECT TOP (?) {', '.join(selected)}, t.{trans_patient_col} AS patient_code "
        f"FROM dbo.PerioProbe pp WITH (NOLOCK) "
        f"JOIN dbo.Transactions t WITH (NOLOCK) ON t.{trans_ref_col} = pp.{probe_trans_col} "
        f"WHERE t.{trans_patient_col} = ? "
        f"ORDER BY pp.{probe_trans_col} ASC"
    )
    return _normalize_rows(source._query(query, [limit, patient_code]))


def main() -> int:
    parser = argparse.ArgumentParser(description="Spot-check R4 charting rows for a patient.")
    parser.add_argument("--patient-code", type=int, required=True)
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    config = R4SqlServerConfig.from_env()
    config.require_enabled()
    source = R4SqlServerSource(config)

    sqlserver = {
        "patient_notes": _sqlserver_patient_notes(source, args.patient_code, args.limit),
        "temporary_notes": _sqlserver_temporary_notes(source, args.patient_code, args.limit),
        "treatment_notes": _sqlserver_treatment_notes(source, args.patient_code, args.limit),
        "chart_healing_actions": _sqlserver_chart_actions(source, args.patient_code, args.limit),
        "bpe_entries": _sqlserver_bpe_entries(source, args.patient_code, args.limit),
        "bpe_furcations": _sqlserver_bpe_furcations(source, args.patient_code, args.limit),
        "perio_probes": _sqlserver_perio_probes(source, args.patient_code, args.limit),
    }

    session = SessionLocal()
    try:
        patient_code = args.patient_code
        postgres = {
            "patient_notes": _pg_rows(
                session,
                select(
                    R4PatientNote.legacy_note_key.label("legacy_note_key"),
                    R4PatientNote.legacy_note_number.label("note_number"),
                    R4PatientNote.note_date.label("note_date"),
                    R4PatientNote.note.label("note"),
                    R4PatientNote.tooth.label("tooth"),
                    R4PatientNote.surface.label("surface"),
                ).where(R4PatientNote.legacy_patient_code == patient_code),
                args.limit,
            ),
            "temporary_notes": _pg_rows(
                session,
                select(
                    R4TemporaryNote.legacy_patient_code.label("patient_code"),
                    R4TemporaryNote.note.label("note"),
                    R4TemporaryNote.legacy_updated_at.label("legacy_updated_at"),
                ).where(R4TemporaryNote.legacy_patient_code == patient_code),
                args.limit,
            ),
            "treatment_notes": _pg_rows(
                session,
                select(
                    R4TreatmentNote.legacy_treatment_note_id.label("note_id"),
                    R4TreatmentNote.note_date.label("note_date"),
                    R4TreatmentNote.note.label("note"),
                ).where(R4TreatmentNote.legacy_patient_code == patient_code),
                args.limit,
            ),
            "chart_healing_actions": _pg_rows(
                session,
                select(
                    R4ChartHealingAction.legacy_action_id.label("action_id"),
                    R4ChartHealingAction.action_date.label("action_date"),
                    R4ChartHealingAction.tooth.label("tooth"),
                    R4ChartHealingAction.surface.label("surface"),
                    R4ChartHealingAction.status.label("status"),
                ).where(R4ChartHealingAction.legacy_patient_code == patient_code),
                args.limit,
            ),
            "bpe_entries": _pg_rows(
                session,
                select(
                    R4BPEEntry.legacy_bpe_id.label("bpe_id"),
                    R4BPEEntry.recorded_at.label("recorded_at"),
                    R4BPEEntry.sextant_1.label("sextant_1"),
                    R4BPEEntry.sextant_2.label("sextant_2"),
                    R4BPEEntry.sextant_3.label("sextant_3"),
                    R4BPEEntry.sextant_4.label("sextant_4"),
                    R4BPEEntry.sextant_5.label("sextant_5"),
                    R4BPEEntry.sextant_6.label("sextant_6"),
                ).where(R4BPEEntry.legacy_patient_code == patient_code),
                args.limit,
            ),
            "bpe_furcations": _pg_rows(
                session,
                select(
                    R4BPEFurcation.legacy_bpe_furcation_key.label("furcation_key"),
                    R4BPEFurcation.legacy_bpe_id.label("bpe_id"),
                    R4BPEFurcation.tooth.label("tooth"),
                    R4BPEFurcation.furcation.label("furcation"),
                    R4BPEFurcation.sextant.label("sextant"),
                ).where(
                    R4BPEFurcation.legacy_bpe_id.in_(
                        select(R4BPEEntry.legacy_bpe_id).where(
                            R4BPEEntry.legacy_patient_code == patient_code
                        )
                    )
                ),
                args.limit,
            ),
            "perio_probes": [],
        }

        sqlserver_probes = sqlserver.get("perio_probes")
        if isinstance(sqlserver_probes, list):
            trans_ids_raw = [row.get("transid") or row.get("trans_id") for row in sqlserver_probes]
            trans_ids = [_coerce_int(value) for value in trans_ids_raw]
            trans_ids = [value for value in trans_ids if value is not None]
            if trans_ids:
                postgres["perio_probes"] = _pg_rows(
                    session,
                    select(
                        R4PerioProbe.legacy_probe_key.label("probe_key"),
                        R4PerioProbe.legacy_trans_id.label("trans_id"),
                        R4PerioProbe.tooth.label("tooth"),
                        R4PerioProbe.probing_point.label("probing_point"),
                        R4PerioProbe.depth.label("depth"),
                        R4PerioProbe.bleeding.label("bleeding"),
                        R4PerioProbe.plaque.label("plaque"),
                    ).where(R4PerioProbe.legacy_trans_id.in_(trans_ids)),
                    args.limit,
                )
    finally:
        session.close()

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
