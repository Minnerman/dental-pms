from sqlalchemy import delete

from app.db.session import SessionLocal
from app.models.r4_charting_canonical import R4ChartingCanonicalRecord
from app.services.r4_charting.canonical_importer import import_r4_charting_canonical
from app.services.r4_import.fixture_source import FixtureSource


def clear_canonical(session) -> None:
    session.execute(delete(R4ChartingCanonicalRecord))


def test_canonical_import_idempotent():
    session = SessionLocal()
    try:
        clear_canonical(session)
        session.commit()

        source = FixtureSource()
        stats_first = import_r4_charting_canonical(session, source)
        session.commit()

        assert stats_first.total > 0
        assert stats_first.created == stats_first.total
        assert stats_first.updated == 0
        assert stats_first.skipped == 0

        stats_second = import_r4_charting_canonical(session, source)
        session.commit()

        assert stats_second.total == stats_first.total
        assert stats_second.created == 0
        assert stats_second.updated == 0
        assert stats_second.skipped == stats_second.total
    finally:
        session.close()
