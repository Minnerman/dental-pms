from sqlalchemy import delete, func, select

from app.db.session import SessionLocal
from app.models.r4_patient_mapping import R4PatientMapping
from app.models.user import User
from app.services.r4_import.fixture_source import FixtureSource
from app.services.r4_import.mapping_preflight import ensure_mapping_for_patient, mapping_exists


def resolve_actor_id(session) -> int:
    actor_id = session.scalar(select(func.min(User.id)))
    if not actor_id:
        raise RuntimeError("No users found; cannot attribute R4 imports.")
    return int(actor_id)


def clear_mapping(session, legacy_patient_code: int) -> None:
    session.execute(
        delete(R4PatientMapping).where(
            R4PatientMapping.legacy_source == "r4",
            R4PatientMapping.legacy_patient_code == legacy_patient_code,
        )
    )


def test_ensure_mapping_for_patient_creates_mapping():
    session = SessionLocal()
    try:
        clear_mapping(session, 1001)
        session.commit()

        actor_id = resolve_actor_id(session)
        source = FixtureSource()

        created = ensure_mapping_for_patient(session, source, actor_id, 1001)
        session.commit()

        assert created is True
        assert mapping_exists(session, "r4", 1001) is True
    finally:
        session.close()


class EmptyPatientSource(FixtureSource):
    def stream_patients(self, patients_from=None, patients_to=None, limit=None):
        return []


def test_ensure_mapping_for_patient_reports_missing():
    session = SessionLocal()
    try:
        clear_mapping(session, 9999)
        session.commit()

        actor_id = resolve_actor_id(session)
        source = EmptyPatientSource()

        created = ensure_mapping_for_patient(session, source, actor_id, 9999)
        session.commit()

        assert created is False
        assert mapping_exists(session, "r4", 9999) is False
    finally:
        session.close()
