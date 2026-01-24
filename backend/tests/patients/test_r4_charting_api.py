from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import delete, func, select

from app.db.session import SessionLocal
from app.models.patient import Patient
from app.models.r4_charting import (
    R4BPEEntry,
    R4BPEFurcation,
    R4ChartingImportState,
    R4PatientNote,
    R4PerioProbe,
)
from app.models.user import User


def resolve_actor_id(session) -> int:
    actor_id = session.scalar(select(func.min(User.id)))
    if not actor_id:
        raise RuntimeError("No users found; cannot attribute R4 imports.")
    return int(actor_id)


def _create_patient(session, legacy_code: int, actor_id: int) -> Patient:
    patient = Patient(
        legacy_source="r4",
        legacy_id=str(legacy_code),
        first_name="Chart",
        last_name="Viewer",
        created_by_user_id=actor_id,
        updated_by_user_id=actor_id,
    )
    session.add(patient)
    session.flush()
    return patient


def _cleanup(session, patient_id: int | None, legacy_code: int) -> None:
    session.execute(
        delete(R4PerioProbe).where(R4PerioProbe.legacy_patient_code == legacy_code)
    )
    session.execute(
        delete(R4BPEFurcation).where(R4BPEFurcation.legacy_patient_code == legacy_code)
    )
    session.execute(
        delete(R4BPEEntry).where(R4BPEEntry.legacy_patient_code == legacy_code)
    )
    session.execute(
        delete(R4PatientNote).where(R4PatientNote.legacy_patient_code == legacy_code)
    )
    if patient_id is not None:
        session.execute(
            delete(R4ChartingImportState).where(
                R4ChartingImportState.patient_id == patient_id
            )
        )
    if patient_id is not None:
        session.execute(delete(Patient).where(Patient.id == patient_id))


def _charting_enabled(api_client) -> bool:
    res = api_client.get("/config")
    if res.status_code != 200:
        return False
    payload = res.json()
    return bool(payload.get("feature_flags", {}).get("charting_viewer"))


def test_charting_endpoints_return_ordered_rows(api_client, auth_headers):
    session = SessionLocal()
    patient_id = None
    legacy_code: int | None = None
    try:
        if not _charting_enabled(api_client):
            return
        actor_id = resolve_actor_id(session)
        legacy_code = 990000000 + (uuid4().int % 100000)
        patient = _create_patient(session, legacy_code, actor_id)
        patient_id = patient.id
        created_at = datetime(2025, 1, 2, tzinfo=timezone.utc)
        probe_key_newer = f"{legacy_code}:3:1:{uuid4().hex[:6]}"
        probe_key_older = f"{legacy_code}:2:1:{uuid4().hex[:6]}"
        bpe_key = f"bpe-{legacy_code}-{uuid4().hex[:6]}"
        furcation_key = f"furc-{legacy_code}-{uuid4().hex[:6]}"
        note_key = f"{legacy_code}:{uuid4().hex[:6]}"

        session.add(
            R4PerioProbe(
                legacy_source="r4",
                legacy_probe_key=probe_key_newer,
                legacy_trans_id=200,
                legacy_patient_code=legacy_code,
                tooth=3,
                probing_point=1,
                depth=4,
                bleeding=1,
                plaque=0,
                recorded_at=created_at,
                created_by_user_id=actor_id,
            )
        )
        session.add(
            R4PerioProbe(
                legacy_source="r4",
                legacy_probe_key=probe_key_older,
                legacy_trans_id=100,
                legacy_patient_code=legacy_code,
                tooth=2,
                probing_point=1,
                depth=3,
                bleeding=0,
                plaque=1,
                recorded_at=datetime(2024, 1, 2, tzinfo=timezone.utc),
                created_by_user_id=actor_id,
            )
        )
        session.add(
            R4BPEEntry(
                legacy_source="r4",
                legacy_bpe_key=bpe_key,
                legacy_bpe_id=3001,
                legacy_patient_code=legacy_code,
                recorded_at=datetime(2024, 6, 1, tzinfo=timezone.utc),
                sextant_1=2,
                sextant_2=1,
                sextant_3=0,
                sextant_4=2,
                sextant_5=1,
                sextant_6=0,
                created_by_user_id=actor_id,
            )
        )
        session.add(
            R4BPEFurcation(
                legacy_source="r4",
                legacy_bpe_furcation_key=furcation_key,
                legacy_bpe_id=3001,
                legacy_patient_code=legacy_code,
                tooth=11,
                furcation=2,
                recorded_at=datetime(2024, 6, 1, tzinfo=timezone.utc),
                created_by_user_id=actor_id,
            )
        )
        session.add(
            R4PatientNote(
                legacy_source="r4",
                legacy_note_key=note_key,
                legacy_patient_code=legacy_code,
                legacy_note_number=1,
                note_date=datetime(2024, 5, 1, tzinfo=timezone.utc),
                note="First note",
                created_by_user_id=actor_id,
            )
        )
        session.commit()

        res = api_client.get(
            f"/patients/{patient.id}/charting/perio-probes", headers=auth_headers
        )
        assert res.status_code == 200, res.text
        probes = res.json()
        assert probes["total"] == 2
        assert probes["items"][0]["legacy_probe_key"] == probe_key_older
        assert probes["items"][1]["legacy_probe_key"] == probe_key_newer
        limited = api_client.get(
            f"/patients/{patient.id}/charting/perio-probes?limit=1", headers=auth_headers
        )
        assert limited.status_code == 200, limited.text
        limited_payload = limited.json()
        assert limited_payload["total"] == 2
        assert len(limited_payload["items"]) == 1

        bpe_res = api_client.get(
            f"/patients/{patient.id}/charting/bpe", headers=auth_headers
        )
        assert bpe_res.status_code == 200, bpe_res.text
        assert len(bpe_res.json()) == 1

        furcations_res = api_client.get(
            f"/patients/{patient.id}/charting/bpe-furcations", headers=auth_headers
        )
        assert furcations_res.status_code == 200, furcations_res.text
        assert len(furcations_res.json()) == 1

        notes_res = api_client.get(
            f"/patients/{patient.id}/charting/notes", headers=auth_headers
        )
        assert notes_res.status_code == 200, notes_res.text
        assert notes_res.json()[0]["legacy_note_key"] == note_key
    finally:
        session.rollback()
        if legacy_code is not None:
            _cleanup(session, patient_id, legacy_code)
            session.commit()
        session.close()


def test_charting_endpoints_blocked_when_feature_disabled(api_client, auth_headers):
    if _charting_enabled(api_client):
        return
    res = api_client.get("/patients/1/charting/perio-probes", headers=auth_headers)
    assert res.status_code == 403, res.text


def test_charting_endpoints_require_auth(api_client):
    res = api_client.get("/patients/1/charting/perio-probes")
    assert res.status_code == 401
