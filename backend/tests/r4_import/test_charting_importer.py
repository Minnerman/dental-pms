from sqlalchemy import delete, func, select

from app.db.session import SessionLocal
from app.models.r4_charting import (
    R4BPEEntry,
    R4BPEFurcation,
    R4ChartHealingAction,
    R4FixedNote,
    R4NoteCategory,
    R4OldPatientNote,
    R4PatientNote,
    R4PerioPlaque,
    R4PerioProbe,
    R4TemporaryNote,
    R4ToothSurface,
    R4ToothSystem,
    R4TreatmentNote,
)
from app.models.user import User
from app.services.r4_import.charting_importer import import_r4_charting
from app.services.r4_import.fixture_source import FixtureSource


def resolve_actor_id(session) -> int:
    actor_id = session.scalar(select(func.min(User.id)))
    if not actor_id:
        raise RuntimeError("No users found; cannot attribute R4 imports.")
    return int(actor_id)


def clear_r4_charting(session) -> None:
    session.execute(delete(R4OldPatientNote))
    session.execute(delete(R4TemporaryNote))
    session.execute(delete(R4TreatmentNote))
    session.execute(delete(R4NoteCategory))
    session.execute(delete(R4FixedNote))
    session.execute(delete(R4PatientNote))
    session.execute(delete(R4PerioPlaque))
    session.execute(delete(R4PerioProbe))
    session.execute(delete(R4BPEFurcation))
    session.execute(delete(R4BPEEntry))
    session.execute(delete(R4ChartHealingAction))
    session.execute(delete(R4ToothSurface))
    session.execute(delete(R4ToothSystem))


def test_r4_charting_import_idempotent_and_updates():
    session = SessionLocal()
    try:
        clear_r4_charting(session)
        session.commit()

        actor_id = resolve_actor_id(session)
        source = FixtureSource()

        stats_first = import_r4_charting(session, source, actor_id)
        session.commit()

        assert stats_first.tooth_systems_created == 2
        assert stats_first.tooth_surfaces_created == 3
        assert stats_first.chart_actions_created == 2
        assert stats_first.patient_notes_created == 2
        assert stats_first.patient_notes_null_patients == 1
        assert stats_first.bpe_created == 1
        assert stats_first.bpe_date_min == "2026-01-03T09:00:00+00:00"
        assert stats_first.bpe_date_max == "2026-01-03T09:00:00+00:00"

        system = session.scalar(
            select(R4ToothSystem).where(R4ToothSystem.legacy_tooth_system_id == 1)
        )
        assert system is not None
        system.name = "Legacy"
        system.updated_by_user_id = actor_id
        session.commit()

        stats_second = import_r4_charting(session, source, actor_id)
        session.commit()

        assert stats_second.tooth_systems_updated == 1
        assert stats_second.tooth_systems_created == 0
    finally:
        session.close()


class DuplicatePerioProbeSource(FixtureSource):
    def list_perio_probes(
        self,
        patients_from: int | None = None,
        patients_to: int | None = None,
        limit: int | None = None,
    ):
        items = super().list_perio_probes(patients_from, patients_to, limit)
        if items:
            items.append(items[0])
        return items


def test_r4_charting_import_skips_duplicate_perio_probes():
    session = SessionLocal()
    try:
        clear_r4_charting(session)
        session.commit()

        actor_id = resolve_actor_id(session)
        source = DuplicatePerioProbeSource()

        stats = import_r4_charting(session, source, actor_id)
        session.commit()

        assert stats.perio_probes_created == 1
        assert stats.perio_probes_skipped == 1
    finally:
        session.close()
