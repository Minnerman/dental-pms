from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.capability import Capability, UserCapability
from app.models.user import User

CAPABILITIES: list[tuple[str, str]] = [
    ("appointments.view", "View appointments"),
    ("appointments.write", "Create and edit appointments"),
    ("appointments.cancel", "Cancel appointments"),
    ("appointments.reschedule", "Reschedule appointments"),
    ("patients.view", "View patients"),
    ("patients.write", "Create and manage patients"),
    ("notes.write", "Create and edit clinical notes"),
    ("documents.upload", "Upload patient documents"),
    ("documents.download", "Download patient documents"),
    ("documents.delete", "Delete patient documents"),
    ("billing.view", "View billing information"),
    ("billing.payments.write", "Record billing payments"),
    ("billing.cashup", "Run cashup reports"),
    ("recalls.view", "View recalls"),
    ("recalls.write", "Create and manage recalls"),
    ("recalls.export", "Export recalls"),
    ("admin.users.manage", "Manage users"),
    ("admin.permissions.manage", "Manage user permissions"),
]

DEFAULT_GRANT_FROM: dict[str, str] = {
    "patients.write": "patients.view",
    "recalls.view": "patients.view",
    "recalls.write": "patients.write",
}


def list_capabilities(db: Session) -> list[Capability]:
    return list(db.scalars(select(Capability).order_by(Capability.code)))


def ensure_capabilities(db: Session) -> list[Capability]:
    existing = {
        cap.code: cap
        for cap in db.scalars(select(Capability).where(Capability.code.in_([c[0] for c in CAPABILITIES])))
    }
    created: list[Capability] = []
    updated = False
    for code, description in CAPABILITIES:
        cap = existing.get(code)
        if cap:
            if cap.description != description:
                cap.description = description
                db.add(cap)
                updated = True
            continue
        cap = Capability(code=code, description=description)
        db.add(cap)
        created.append(cap)
    if created:
        db.flush()
        for capability in created:
            source_code = DEFAULT_GRANT_FROM.get(capability.code)
            if not source_code:
                continue
            source_id = db.scalar(
                select(Capability.id).where(Capability.code == source_code)
            )
            if source_id is None:
                continue
            user_ids = list(
                db.scalars(
                    select(UserCapability.user_id).where(
                        UserCapability.capability_id == source_id
                    )
                )
            )
            for user_id in user_ids:
                db.add(
                    UserCapability(
                        user_id=user_id,
                        capability_id=capability.id,
                    )
                )
    if created or updated:
        db.commit()
    if created:
        for cap in created:
            db.refresh(cap)
    return list_capabilities(db)


def grant_all_capabilities(db: Session, user: User, *, commit: bool = True) -> int:
    capability_ids = list(db.scalars(select(Capability.id)))
    if not capability_ids:
        return 0
    existing = set(
        db.scalars(
            select(UserCapability.capability_id).where(UserCapability.user_id == user.id)
        )
    )
    missing = [cap_id for cap_id in capability_ids if cap_id not in existing]
    for cap_id in missing:
        db.add(UserCapability(user_id=user.id, capability_id=cap_id))
    if missing:
        if commit:
            db.commit()
        else:
            db.flush()
    return len(missing)


def backfill_user_capabilities(db: Session) -> int:
    user_ids = list(db.scalars(select(User.id)))
    capability_ids = list(db.scalars(select(Capability.id)))
    if not user_ids or not capability_ids:
        return 0
    existing_pairs = set(
        db.execute(select(UserCapability.user_id, UserCapability.capability_id)).all()
    )
    created = 0
    for user_id in user_ids:
        for cap_id in capability_ids:
            if (user_id, cap_id) in existing_pairs:
                continue
            db.add(UserCapability(user_id=user_id, capability_id=cap_id))
            created += 1
    if created:
        db.commit()
    return created


def get_user_capabilities(db: Session, user_id: int) -> list[Capability]:
    stmt = (
        select(Capability)
        .join(UserCapability, UserCapability.capability_id == Capability.id)
        .where(UserCapability.user_id == user_id)
        .order_by(Capability.code)
    )
    return list(db.scalars(stmt))


def replace_user_capabilities(
    db: Session,
    user_id: int,
    capability_codes: list[str],
    *,
    commit: bool = True,
) -> list[Capability]:
    codes = [code.strip() for code in capability_codes if code.strip()]
    if not codes:
        db.execute(delete(UserCapability).where(UserCapability.user_id == user_id))
        if commit:
            db.commit()
        else:
            db.flush()
        return []
    capabilities = list(
        db.scalars(select(Capability).where(Capability.code.in_(codes)))
    )
    found_codes = {cap.code for cap in capabilities}
    missing = [code for code in codes if code not in found_codes]
    if missing:
        raise ValueError(f"Unknown capability codes: {', '.join(sorted(missing))}")
    db.execute(delete(UserCapability).where(UserCapability.user_id == user_id))
    for cap in capabilities:
        db.add(UserCapability(user_id=user_id, capability_id=cap.id))
    if commit:
        db.commit()
    else:
        db.flush()
    return list(
        db.scalars(
            select(Capability)
            .join(UserCapability, UserCapability.capability_id == Capability.id)
            .where(UserCapability.user_id == user_id)
            .order_by(Capability.code)
        )
    )
