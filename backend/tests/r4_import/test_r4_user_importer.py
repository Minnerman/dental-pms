from sqlalchemy import delete, select

from app.db.session import SessionLocal
from app.models.r4_user import R4User
from app.models.user import User
from app.services.r4_import.fixture_source import FixtureSource
from app.services.r4_import.r4_user_importer import import_r4_users


def resolve_actor_id(session) -> int:
    actor_id = session.scalar(select(User.id).order_by(User.id).limit(1))
    if not actor_id:
        raise RuntimeError("No users found; cannot attribute R4 imports.")
    return int(actor_id)


def clear_r4_users(session) -> None:
    session.execute(delete(R4User))


def test_r4_users_idempotent_and_updates():
    session = SessionLocal()
    try:
        clear_r4_users(session)
        session.commit()

        actor_id = resolve_actor_id(session)
        source = FixtureSource()

        stats_first = import_r4_users(session, source, actor_id)
        session.commit()

        assert stats_first.users_created == 3
        assert stats_first.users_updated == 0
        assert stats_first.users_skipped == 0

        user = session.scalar(
            select(R4User).where(R4User.legacy_user_code == 10000002)
        )
        assert user is not None
        user.full_name = "Arthur Dentist Updated"
        user.updated_by_user_id = actor_id
        session.commit()

        stats_second = import_r4_users(session, source, actor_id)
        session.commit()

        assert stats_second.users_created == 0
        assert stats_second.users_updated == 1
        assert stats_second.users_skipped == 2
    finally:
        session.close()
