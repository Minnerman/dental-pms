from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.r4_user import R4User
from app.services.r4_import.source import R4Source
from app.services.r4_import.types import R4User as R4UserPayload


@dataclass
class R4UserImportStats:
    users_created: int = 0
    users_updated: int = 0
    users_skipped: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "users_created": self.users_created,
            "users_updated": self.users_updated,
            "users_skipped": self.users_skipped,
        }


def import_r4_users(
    session: Session,
    source: R4Source,
    actor_id: int,
    legacy_source: str = "r4",
    limit: int | None = None,
) -> R4UserImportStats:
    stats = R4UserImportStats()
    for user in source.stream_users(limit=limit):
        _upsert_user(session, user, actor_id, legacy_source, stats)
    return stats


def _upsert_user(
    session: Session,
    user: R4UserPayload,
    actor_id: int,
    legacy_source: str,
    stats: R4UserImportStats,
) -> None:
    existing = session.scalar(
        select(R4User).where(
            R4User.legacy_source == legacy_source,
            R4User.legacy_user_code == user.user_code,
        )
    )
    display_name = _build_display_name(
        title=user.title,
        forename=user.forename,
        surname=user.surname,
        full_name=user.full_name,
        initials=user.initials,
    )
    updates = {
        "legacy_user_code": user.user_code,
        "full_name": _clean_text(user.full_name),
        "title": _clean_text(user.title),
        "forename": _clean_text(user.forename),
        "surname": _clean_text(user.surname),
        "initials": _clean_text(user.initials),
        "display_name": display_name,
        "is_current": bool(user.is_current),
        "updated_by_user_id": actor_id,
    }
    if existing:
        updated = _apply_updates(existing, updates)
        if updated:
            stats.users_updated += 1
        else:
            stats.users_skipped += 1
        return

    row = R4User(
        legacy_source=legacy_source,
        created_by_user_id=actor_id,
        **updates,
    )
    session.add(row)
    stats.users_created += 1


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _build_display_name(
    *,
    title: str | None,
    forename: str | None,
    surname: str | None,
    full_name: str | None,
    initials: str | None,
) -> str | None:
    preferred_parts = [_clean_text(title), _clean_text(forename), _clean_text(surname)]
    preferred = " ".join(part for part in preferred_parts if part)
    if preferred:
        return preferred
    full = _clean_text(full_name)
    if full:
        return full
    alt_parts = [_clean_text(forename), _clean_text(surname)]
    alt = " ".join(part for part in alt_parts if part)
    if alt:
        return alt
    return _clean_text(initials)


def _apply_updates(model, updates: dict[str, object]) -> bool:
    changed = False
    for field, value in updates.items():
        if getattr(model, field) != value:
            setattr(model, field, value)
            changed = True
    return changed
