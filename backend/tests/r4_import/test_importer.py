from sqlalchemy import delete, func, select

from app.db.session import SessionLocal
from app.models.appointment import Appointment
from app.models.patient import Patient
from app.models.user import User
from app.services.r4_import.fixture_source import FixtureSource
from app.services.r4_import.importer import import_r4


def resolve_actor_id(session) -> int:
    actor_id = session.scalar(select(func.min(User.id)))
    if not actor_id:
        raise RuntimeError("No users found; cannot attribute R4 imports.")
    return int(actor_id)


def clear_r4(session) -> None:
    session.execute(delete(Appointment).where(Appointment.legacy_source == "r4"))
    session.execute(delete(Patient).where(Patient.legacy_source == "r4"))


def test_r4_import_idempotent():
    session = SessionLocal()
    try:
        clear_r4(session)
        session.commit()

        actor_id = resolve_actor_id(session)
        source = FixtureSource()

        stats_first = import_r4(session, source, actor_id)
        session.commit()

        assert stats_first.patients_created == 2
        assert stats_first.appts_created == 2
        assert stats_first.appts_unmapped_patient_refs == 1

        stats_second = import_r4(session, source, actor_id)
        session.commit()

        assert stats_second.patients_created == 0
        assert stats_second.patients_updated == 0
        assert stats_second.appts_created == 0
        assert stats_second.appts_updated == 0
        assert stats_second.appts_unmapped_patient_refs == 1

        unmapped = session.scalar(
            select(Appointment).where(Appointment.legacy_id == "A9999-1")
        )
        assert unmapped is not None
        assert unmapped.patient_id is None
    finally:
        session.close()
