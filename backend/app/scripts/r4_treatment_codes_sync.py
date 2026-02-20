from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.r4_treatment_plan import R4Treatment
from app.models.user import User
from app.services.r4_import.sqlserver_source import R4SqlServerConfig, R4SqlServerSource
from app.services.r4_import.types import R4Treatment as R4TreatmentPayload


def _resolve_actor_id(session: Session) -> int:
    actor_id = session.scalar(select(User.id).order_by(User.id.asc()).limit(1))
    if not actor_id:
        raise RuntimeError("No users found; cannot attribute R4 sync writes.")
    return int(actor_id)


def _parse_code_ids(path: Path) -> list[int]:
    if not path.exists():
        raise RuntimeError(f"Code ID file not found: {path}")
    tokens: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        line = line.replace(",", " ")
        tokens.extend(part.strip() for part in line.split())
    out: list[int] = []
    seen: set[int] = set()
    for token in tokens:
        lower = token.lower()
        if lower in {"code_id", "code", "legacy_code_id"}:
            continue
        try:
            value = int(token)
        except ValueError as exc:
            raise RuntimeError(f"Invalid code ID token: {token}") from exc
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


@dataclass
class SyncStats:
    requested_codes_total: int = 0
    fetched_total: int = 0
    missing_codes_total: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0

    def as_dict(
        self,
        *,
        requested_codes: list[int],
        fetched_codes: list[int],
        missing_codes: list[int],
        apply: bool,
    ) -> dict[str, object]:
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "apply": apply,
            "source_table": "dbo.Codes (fallback: dbo.Treatments)",
            "requested_codes_total": self.requested_codes_total,
            "requested_codes_sample": requested_codes[:20],
            "fetched_total": self.fetched_total,
            "fetched_codes_sample": fetched_codes[:20],
            "missing_codes_total": self.missing_codes_total,
            "missing_codes_sample": missing_codes[:20],
            "created": self.created,
            "updated": self.updated,
            "skipped": self.skipped,
        }


def _upsert_treatment_code(
    session: Session,
    *,
    treatment: R4TreatmentPayload,
    actor_id: int,
    stats: SyncStats,
    apply: bool,
) -> None:
    existing = session.scalar(
        select(R4Treatment).where(
            R4Treatment.legacy_source == "r4",
            R4Treatment.legacy_treatment_code == int(treatment.treatment_code),
        )
    )
    updates = {
        "description": treatment.description,
        "short_code": treatment.short_code,
        "default_time": treatment.default_time_minutes,
        "exam": treatment.exam,
        "patient_required": treatment.patient_required,
    }
    if existing:
        changed = False
        for field, value in updates.items():
            if getattr(existing, field) != value:
                changed = True
                if apply:
                    setattr(existing, field, value)
        if changed:
            stats.updated += 1
            if apply:
                existing.updated_by_user_id = actor_id
        else:
            stats.skipped += 1
        return
    stats.created += 1
    if not apply:
        return
    session.add(
        R4Treatment(
            legacy_source="r4",
            legacy_treatment_code=int(treatment.treatment_code),
            description=treatment.description,
            short_code=treatment.short_code,
            default_time=treatment.default_time_minutes,
            exam=treatment.exam,
            patient_required=treatment.patient_required,
            created_by_user_id=actor_id,
            updated_by_user_id=actor_id,
        )
    )


def _sync_codes(
    *,
    source: R4SqlServerSource,
    session: Session,
    code_ids: list[int],
    apply: bool,
) -> tuple[SyncStats, list[int], list[int]]:
    stats = SyncStats(requested_codes_total=len(code_ids))
    rows = source.list_treatments_by_codes(code_ids)
    fetched_codes = sorted({int(row.treatment_code) for row in rows})
    missing_codes = sorted(set(code_ids) - set(fetched_codes))
    stats.fetched_total = len(rows)
    stats.missing_codes_total = len(missing_codes)

    actor_id = _resolve_actor_id(session)
    rows_by_code = {int(row.treatment_code): row for row in rows}
    for code_id in code_ids:
        row = rows_by_code.get(int(code_id))
        if row is None:
            continue
        _upsert_treatment_code(
            session,
            treatment=row,
            actor_id=actor_id,
            stats=stats,
            apply=apply,
        )
    return stats, fetched_codes, missing_codes


def _write_stats(path: str | None, payload: dict[str, object]) -> None:
    if not path:
        return
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sync selected R4 treatment code labels into Postgres cache table."
    )
    parser.add_argument(
        "--code-ids-file",
        required=True,
        help="Newline/comma-separated treatment code IDs.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Persist upserts to Postgres (default is dry-run).",
    )
    parser.add_argument("--stats-out", help="Optional JSON path to write sync stats.")
    args = parser.parse_args()

    code_ids = _parse_code_ids(Path(args.code_ids_file))
    config = R4SqlServerConfig.from_env()
    config.require_enabled()
    config.require_readonly()
    source = R4SqlServerSource(config)
    source.ensure_select_only()

    session = SessionLocal()
    try:
        stats, fetched_codes, missing_codes = _sync_codes(
            source=source,
            session=session,
            code_ids=code_ids,
            apply=args.apply,
        )
        if args.apply:
            session.commit()
        payload = stats.as_dict(
            requested_codes=code_ids,
            fetched_codes=fetched_codes,
            missing_codes=missing_codes,
            apply=args.apply,
        )
    finally:
        session.close()

    _write_stats(args.stats_out, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
