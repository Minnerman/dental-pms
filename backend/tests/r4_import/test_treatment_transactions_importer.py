from decimal import Decimal

from sqlalchemy import delete, select

from app.db.session import SessionLocal
from app.models.r4_treatment_transaction import R4TreatmentTransaction
from app.models.user import User
from app.services.r4_import.fixture_source import FixtureSource
from app.services.r4_import.treatment_transactions_importer import (
    import_r4_treatment_transactions,
    TreatmentTransactionImportStats,
)
from app.services.r4_import.types import R4TreatmentTransaction as R4TreatmentTransactionPayload


def resolve_actor_id(session) -> int:
    actor_id = session.scalar(select(User.id).order_by(User.id).limit(1))
    if not actor_id:
        raise RuntimeError("No users found; cannot attribute R4 imports.")
    return int(actor_id)


def clear_r4_transactions(session) -> None:
    session.execute(delete(R4TreatmentTransaction))


def test_r4_treatment_transactions_idempotent_and_updates():
    session = SessionLocal()
    try:
        clear_r4_transactions(session)
        session.commit()

        actor_id = resolve_actor_id(session)
        source = FixtureSource()

        stats_first = import_r4_treatment_transactions(session, source, actor_id)
        session.commit()

        assert stats_first.transactions_created == 2
        assert stats_first.transactions_updated == 0
        assert "updated_transaction_ids_sample" not in stats_first.as_dict()

        tx = session.scalar(
            select(R4TreatmentTransaction).where(
                R4TreatmentTransaction.legacy_transaction_id == 9001
            )
        )
        assert tx is not None
        tx.patient_cost = Decimal("12.34")
        tx.updated_by_user_id = actor_id
        session.commit()

        stats_second = import_r4_treatment_transactions(session, source, actor_id)
        session.commit()

        assert stats_second.transactions_created == 0
        assert stats_second.transactions_updated == 1
        assert stats_second.transactions_skipped == 1
        assert stats_second.as_dict()["updated_transaction_ids_sample"] == [9001]
    finally:
        session.close()


def test_treatment_transactions_updated_ids_sample_capped():
    stats = TreatmentTransactionImportStats()
    stats.updated_transaction_ids = set(range(1, 30))
    sample = stats.as_dict()["updated_transaction_ids_sample"]
    assert sample == list(range(1, 21))


def test_treatment_transactions_updated_ids_scoped_to_run():
    session = SessionLocal()
    try:
        clear_r4_transactions(session)
        session.commit()

        actor_id = resolve_actor_id(session)

        class OneUpdateSource:
            def stream_treatment_transactions(self, **_kwargs):
                return [
                    R4TreatmentTransactionPayload(
                        transaction_id=1,
                        patient_code=1000101,
                        performed_at="2026-01-02T00:00:00",
                        treatment_code=None,
                        trans_code=1,
                        patient_cost=0,
                        dpb_cost=0,
                    )
                ]

        class NoUpdateSource:
            def stream_treatment_transactions(self, **_kwargs):
                return [
                    R4TreatmentTransactionPayload(
                        transaction_id=1,
                        patient_code=1000101,
                        performed_at="2026-01-02T00:00:00",
                        treatment_code=None,
                        trans_code=1,
                        patient_cost=0,
                        dpb_cost=0,
                    )
                ]

        stats_first = import_r4_treatment_transactions(session, OneUpdateSource(), actor_id)
        session.commit()
        assert stats_first.transactions_created == 1

        # Force an update by changing the stored cost.
        tx = session.scalar(
            select(R4TreatmentTransaction).where(
                R4TreatmentTransaction.legacy_transaction_id == 1
            )
        )
        tx.patient_cost = Decimal("10.00")
        tx.updated_by_user_id = actor_id
        session.commit()

        stats_update = import_r4_treatment_transactions(session, OneUpdateSource(), actor_id)
        session.commit()
        assert stats_update.transactions_updated == 1
        assert stats_update.as_dict()["updated_transaction_ids_sample"] == [1]

        stats_second = import_r4_treatment_transactions(session, NoUpdateSource(), actor_id)
        session.commit()
        assert stats_second.transactions_updated == 0
        assert "updated_transaction_ids_sample" not in stats_second.as_dict()
    finally:
        session.close()
