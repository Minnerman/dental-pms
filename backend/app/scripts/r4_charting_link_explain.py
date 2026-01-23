from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models.r4_charting import R4PerioProbe
from app.models.r4_patient_mapping import R4PatientMapping
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


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Explain charting linkage for a patient (SQL Server vs Postgres)."
    )
    parser.add_argument("--patient-code", type=int, required=True)
    parser.add_argument("--entity", choices=["perio_probes"], default="perio_probes")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    if args.entity != "perio_probes":
        print("Only perio_probes is supported right now.")
        return 2

    config = R4SqlServerConfig.from_env()
    config.require_enabled()
    source = R4SqlServerSource(config)

    pipeline = source.perio_probe_pipeline_summary(
        patients_from=args.patient_code,
        patients_to=args.patient_code,
        limit=args.limit,
    )
    probes = list(
        source.list_perio_probes(
            patients_from=args.patient_code,
            patients_to=args.patient_code,
            limit=args.limit,
        )
    )
    probe_sample = [
        {
            "trans_id": probe.trans_id,
            "patient_code": probe.patient_code,
            "tooth": probe.tooth,
            "probing_point": probe.probing_point,
            "depth": probe.depth,
            "bleeding": probe.bleeding,
            "plaque": probe.plaque,
            "recorded_at": _format_dt(probe.recorded_at),
        }
        for probe in probes
    ]

    session = SessionLocal()
    try:
        mapping_exists = (
            session.scalar(
                select(R4PatientMapping.id).where(
                    R4PatientMapping.legacy_source == "r4",
                    R4PatientMapping.legacy_patient_code == args.patient_code,
                )
            )
            is not None
        )
        postgres_count = session.scalar(
            select(func.count(R4PerioProbe.id)).where(
                R4PerioProbe.legacy_patient_code == args.patient_code
            )
        ) or 0
        postgres_rows = session.execute(
            select(
                R4PerioProbe.legacy_probe_key.label("legacy_probe_key"),
                R4PerioProbe.legacy_trans_id.label("legacy_trans_id"),
                R4PerioProbe.tooth.label("tooth"),
                R4PerioProbe.probing_point.label("probing_point"),
                R4PerioProbe.depth.label("depth"),
                R4PerioProbe.bleeding.label("bleeding"),
                R4PerioProbe.plaque.label("plaque"),
                R4PerioProbe.recorded_at.label("recorded_at"),
            )
            .where(R4PerioProbe.legacy_patient_code == args.patient_code)
            .order_by(R4PerioProbe.legacy_probe_key.asc())
            .limit(args.limit)
        ).mappings()
        postgres_sample = [
            {key: _format_dt(value) for key, value in row.items()}
            for row in postgres_rows
        ]
    finally:
        session.close()

    payload = {
        "patient_code": args.patient_code,
        "entity": args.entity,
        "mapping_exists": mapping_exists,
        "sqlserver_pipeline": pipeline,
        "sqlserver_list_perio_probes_count": len(probes),
        "sqlserver_list_perio_probes_sample": probe_sample,
        "postgres_perio_probes_count": postgres_count,
        "postgres_perio_probes_sample": postgres_sample,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }

    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
