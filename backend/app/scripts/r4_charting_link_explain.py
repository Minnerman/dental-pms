from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone

from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models.r4_charting import R4PerioProbe
from app.models.r4_patient_mapping import R4PatientMapping
from app.models.user import User
from app.services.r4_import.mapping_preflight import ensure_mapping_for_patient, mapping_exists
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


def _resolve_actor_id(session) -> int:
    actor_id = session.scalar(select(func.min(User.id)))
    if not actor_id:
        raise RuntimeError("No users found; cannot attribute R4 imports.")
    return int(actor_id)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Explain charting linkage for a patient (SQL Server vs Postgres)."
    )
    parser.add_argument("--patient-code", type=int, required=True)
    parser.add_argument("--entity", choices=["perio_probes"], default="perio_probes")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument(
        "--ensure-mapping",
        action="store_true",
        help="Auto-create missing patient mapping before explanation.",
    )
    args = parser.parse_args()

    if args.entity != "perio_probes":
        print("Only perio_probes is supported right now.")
        return 2

    config = R4SqlServerConfig.from_env()
    config.require_enabled()
    source = R4SqlServerSource(config)

    session = SessionLocal()
    try:
        mapping_ready = mapping_exists(session, "r4", args.patient_code)
        if not mapping_ready:
            if args.ensure_mapping:
                actor_id = _resolve_actor_id(session)
                mapping_ready = ensure_mapping_for_patient(
                    session,
                    source,
                    actor_id,
                    args.patient_code,
                    legacy_source="r4",
                )
                session.commit()
                if not mapping_ready:
                    print(
                        "Missing patient mapping for patient_code "
                        f"{args.patient_code} after ensure-mapping.",
                        file=sys.stderr,
                    )
                    return 2
            else:
                print(
                    "Missing patient mapping for patient_code "
                    f"{args.patient_code}. Run patients import first or pass --ensure-mapping.",
                    file=sys.stderr,
                )
                return 2

        pipeline = source.perio_probe_pipeline_summary(
            patients_from=args.patient_code,
            patients_to=args.patient_code,
            limit=args.limit,
        )
        patient_summary = source.perio_probe_patient_summary(
            patients_from=args.patient_code,
            patients_to=args.patient_code,
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
        "mapping_exists": mapping_ready,
        "sqlserver_patient_totals": patient_summary,
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
