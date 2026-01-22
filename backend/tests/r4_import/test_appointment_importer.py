from datetime import date

from sqlalchemy import delete, select

from app.db.session import SessionLocal
from app.models.r4_appointment import R4Appointment
from app.models.user import User
from app.services.r4_import.appointment_importer import import_r4_appointments
from app.services.r4_import.fixture_source import FixtureSource


def test_r4_appointments_idempotent():
    session = SessionLocal()
    try:
        session.execute(delete(R4Appointment))
        session.commit()
        actor = session.scalar(select(User).order_by(User.id.asc()).limit(1))
        assert actor is not None
        source = FixtureSource()

        stats_first = import_r4_appointments(session, source, actor.id)
        session.commit()
        assert stats_first.appointments_created == 4
        assert stats_first.appointments_updated == 0
        assert stats_first.appointments_skipped == 0

        stats_second = import_r4_appointments(session, source, actor.id)
        session.commit()
        assert stats_second.appointments_created == 0
        assert stats_second.appointments_updated == 0
        assert stats_second.appointments_skipped == 4
    finally:
        session.execute(delete(R4Appointment))
        session.commit()
        session.close()


def test_r4_appointments_date_filter():
    session = SessionLocal()
    try:
        session.execute(delete(R4Appointment))
        session.commit()
        actor = session.scalar(select(User).order_by(User.id.asc()).limit(1))
        assert actor is not None
        source = FixtureSource()

        stats = import_r4_appointments(
            session,
            source,
            actor.id,
            date_from=date(2024, 2, 1),
            date_to=date(2024, 2, 28),
        )
        session.commit()
        assert stats.appointments_created == 1
        assert stats.appointments_patient_null == 1
    finally:
        session.execute(delete(R4Appointment))
        session.commit()
        session.close()
