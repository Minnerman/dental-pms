from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
import json
import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.r4_treatment_transaction import R4TreatmentTransaction
from app.services.r4_import.source import R4Source
from app.services.r4_import.types import R4TreatmentTransaction as R4TreatmentTransactionPayload


@dataclass
class TreatmentTransactionImportStats:
    transactions_created: int = 0
    transactions_updated: int = 0
    transactions_skipped: int = 0

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


def import_r4_treatment_transactions(
    session: Session,
    source: R4Source,
    actor_id: int,
    legacy_source: str = "r4",
    patients_from: int | None = None,
    patients_to: int | None = None,
    limit: int | None = None,
    progress_every: int | None = None,
) -> TreatmentTransactionImportStats:
    stats = TreatmentTransactionImportStats()
    processed = 0
    last_transaction_id: int | None = None
    started_at = time.monotonic()
    for tx in source.stream_treatment_transactions(
        patients_from=patients_from,
        patients_to=patients_to,
        limit=limit,
    ):
        processed += 1
        last_transaction_id = tx.transaction_id
        _upsert_transaction(session, tx, actor_id, legacy_source, stats)
        _maybe_emit_checkpoint(
            processed,
            last_transaction_id,
            progress_every,
            started_at,
            limit,
        )
    return stats


def _upsert_transaction(
    session: Session,
    tx: R4TreatmentTransactionPayload,
    actor_id: int,
    legacy_source: str,
    stats: TreatmentTransactionImportStats,
) -> R4TreatmentTransaction:
    legacy_id = tx.transaction_id
    existing = session.scalar(
        select(R4TreatmentTransaction).where(
            R4TreatmentTransaction.legacy_source == legacy_source,
            R4TreatmentTransaction.legacy_transaction_id == legacy_id,
        )
    )
    updates = {
        "patient_code": tx.patient_code,
        "performed_at": _normalize_datetime(tx.performed_at),
        "treatment_code": tx.treatment_code,
        "trans_code": tx.trans_code,
        "patient_cost": _normalize_money(tx.patient_cost),
        "dpb_cost": _normalize_money(tx.dpb_cost),
        "recorded_by": tx.recorded_by,
        "user_code": tx.user_code,
        "tp_number": tx.tp_number,
        "tp_item": tx.tp_item,
        "updated_by_user_id": actor_id,
    }
    if existing:
        updated = _apply_updates(existing, updates)
        if updated:
            stats.transactions_updated += 1
        else:
            stats.transactions_skipped += 1
        return existing

    row = R4TreatmentTransaction(
        legacy_source=legacy_source,
        legacy_transaction_id=legacy_id,
        created_by_user_id=actor_id,
        **updates,
    )
    session.add(row)
    stats.transactions_created += 1
    return row


def _normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    microseconds = (value.microsecond // 1000) * 1000
    return value.replace(microsecond=microseconds)


def _normalize_money(value: float | Decimal | None) -> Decimal | None:
    if value is None:
        return None
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _apply_updates(model, updates: dict) -> bool:
    changed = False
    for field, value in updates.items():
        if getattr(model, field) != value:
            setattr(model, field, value)
            changed = True
    return changed


def _maybe_emit_checkpoint(
    processed: int,
    last_transaction_id: int | None,
    progress_every: int | None,
    started_at: float,
    limit: int | None,
) -> None:
    if not progress_every or progress_every <= 0 or last_transaction_id is None:
        return
    if processed % progress_every != 0:
        return
    elapsed = max(time.monotonic() - started_at, 0.001)
    remaining = None
    if limit is not None:
        remaining = max(limit - processed, 0)
    payload = {
        "event": "r4_import_checkpoint",
        "entity": "treatment_transactions",
        "processed": processed,
        "last_transaction_id": last_transaction_id,
        "elapsed_seconds": round(elapsed, 2),
        "transactions_per_second": round(processed / elapsed, 2),
        "estimated_remaining_transactions": remaining,
        "timestamp": round(time.time(), 3),
    }
    print(json.dumps(payload, sort_keys=True))
