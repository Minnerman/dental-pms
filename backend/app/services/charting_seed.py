from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.patient import Patient
from app.models.r4_charting import (
    R4BPEEntry,
    R4BPEFurcation,
    R4ChartingImportState,
    R4PatientNote,
    R4PerioProbe,
    R4ToothSurface,
)
from app.models.r4_patient_mapping import R4PatientMapping
from app.models.user import Role, User
from app.services.users import create_user

DEMO_PATIENT_CODES = [1000000, 1011978, 1012056, 1013684, 1000035]


def _resolve_actor_id(session: Session) -> int:
    actor_id = session.scalar(select(User.id).order_by(User.id.asc()).limit(1))
    if actor_id:
        return int(actor_id)
    user = create_user(
        session,
        email="charting_seed_admin@example.com",
        password="ChangeMe123!",
        full_name="Charting Seed Admin",
        role=Role.superadmin,
        is_active=True,
        must_change_password=False,
    )
    return int(user.id)


def _get_or_create_patient(session: Session, *, legacy_code: int, actor_id: int) -> Patient:
    patient = session.scalar(
        select(Patient).where(Patient.legacy_source == "r4", Patient.legacy_id == str(legacy_code))
    )
    if patient:
        return patient
    patient = Patient(
        legacy_source="r4",
        legacy_id=str(legacy_code),
        first_name="Charting",
        last_name=f"Demo{legacy_code}",
        created_by_user_id=actor_id,
        updated_by_user_id=actor_id,
    )
    session.add(patient)
    session.flush()
    return patient


def _ensure_mapping(session: Session, *, patient: Patient, legacy_code: int) -> bool:
    mapping = session.scalar(
        select(R4PatientMapping).where(
            R4PatientMapping.legacy_source == "r4",
            R4PatientMapping.legacy_patient_code == legacy_code,
        )
    )
    if mapping:
        return False
    session.add(
        R4PatientMapping(
            legacy_source="r4",
            legacy_patient_code=legacy_code,
            patient_id=patient.id,
        )
    )
    return True


def _ensure_import_state(session: Session, *, patient: Patient, legacy_code: int) -> bool:
    record = session.scalar(
        select(R4ChartingImportState).where(R4ChartingImportState.patient_id == patient.id)
    )
    if record:
        return False
    session.add(
        R4ChartingImportState(
            patient_id=patient.id,
            legacy_patient_code=legacy_code,
            last_imported_at=datetime.now(timezone.utc),
        )
    )
    return True


def _ensure_perio_probe(
    session: Session,
    *,
    legacy_probe_key: str,
    legacy_patient_code: int,
    actor_id: int,
    recorded_at: datetime,
    tooth: int,
    probing_point: int,
    depth: int,
) -> bool:
    existing = session.scalar(
        select(R4PerioProbe).where(R4PerioProbe.legacy_probe_key == legacy_probe_key)
    )
    if existing:
        return False
    session.add(
        R4PerioProbe(
            legacy_source="r4",
            legacy_probe_key=legacy_probe_key,
            legacy_trans_id=1000 + tooth,
            legacy_patient_code=legacy_patient_code,
            tooth=tooth,
            probing_point=probing_point,
            depth=depth,
            bleeding=1 if depth >= 4 else 0,
            plaque=0,
            recorded_at=recorded_at,
            created_by_user_id=actor_id,
        )
    )
    return True


def _ensure_bpe_entry(
    session: Session,
    *,
    legacy_bpe_key: str,
    legacy_bpe_id: int,
    legacy_patient_code: int,
    recorded_at: datetime,
    actor_id: int,
) -> bool:
    existing = session.scalar(select(R4BPEEntry).where(R4BPEEntry.legacy_bpe_key == legacy_bpe_key))
    if existing:
        return False
    session.add(
        R4BPEEntry(
            legacy_source="r4",
            legacy_bpe_key=legacy_bpe_key,
            legacy_bpe_id=legacy_bpe_id,
            legacy_patient_code=legacy_patient_code,
            recorded_at=recorded_at,
            sextant_1=2,
            sextant_2=1,
            sextant_3=0,
            sextant_4=2,
            sextant_5=1,
            sextant_6=0,
            created_by_user_id=actor_id,
        )
    )
    return True


def _ensure_bpe_furcation(
    session: Session,
    *,
    legacy_furcation_key: str,
    legacy_bpe_id: int,
    legacy_patient_code: int,
    recorded_at: datetime,
    actor_id: int,
    tooth: int,
    furcation: int,
    sextant: int,
) -> bool:
    existing = session.scalar(
        select(R4BPEFurcation).where(R4BPEFurcation.legacy_bpe_furcation_key == legacy_furcation_key)
    )
    if existing:
        return False
    session.add(
        R4BPEFurcation(
            legacy_source="r4",
            legacy_bpe_furcation_key=legacy_furcation_key,
            legacy_bpe_id=legacy_bpe_id,
            legacy_patient_code=legacy_patient_code,
            tooth=tooth,
            furcation=furcation,
            sextant=sextant,
            recorded_at=recorded_at,
            created_by_user_id=actor_id,
        )
    )
    return True


def _ensure_patient_note(
    session: Session,
    *,
    legacy_note_key: str,
    legacy_note_number: int,
    legacy_patient_code: int,
    note_date: datetime,
    note: str,
    actor_id: int,
) -> bool:
    existing = session.scalar(
        select(R4PatientNote).where(R4PatientNote.legacy_note_key == legacy_note_key)
    )
    if existing:
        return False
    session.add(
        R4PatientNote(
            legacy_source="r4",
            legacy_note_key=legacy_note_key,
            legacy_patient_code=legacy_patient_code,
            legacy_note_number=legacy_note_number,
            note_date=note_date,
            note=note,
            category_number=1,
            created_by_user_id=actor_id,
        )
    )
    return True


def _ensure_tooth_surface(
    session: Session,
    *,
    legacy_tooth_id: int,
    legacy_surface_no: int,
    actor_id: int,
) -> bool:
    existing = session.scalar(
        select(R4ToothSurface).where(
            R4ToothSurface.legacy_tooth_id == legacy_tooth_id,
            R4ToothSurface.legacy_surface_no == legacy_surface_no,
        )
    )
    if existing:
        return False
    session.add(
        R4ToothSurface(
            legacy_source="r4",
            legacy_tooth_id=legacy_tooth_id,
            legacy_surface_no=legacy_surface_no,
            label=f"Surface {legacy_surface_no}",
            short_label=str(legacy_surface_no),
            sort_order=legacy_surface_no,
            created_by_user_id=actor_id,
        )
    )
    return True


def seed_charting_demo(session: Session) -> dict[str, object]:
    actor_id = _resolve_actor_id(session)
    patients = []
    created_counts = {
        "patients": 0,
        "mappings": 0,
        "perio_probes": 0,
        "bpe_entries": 0,
        "bpe_furcations": 0,
        "patient_notes": 0,
        "tooth_surfaces": 0,
        "import_state": 0,
    }

    for legacy_code in DEMO_PATIENT_CODES:
        patient = session.scalar(
            select(Patient).where(
                Patient.legacy_source == "r4", Patient.legacy_id == str(legacy_code)
            )
        )
        if not patient:
            patient = _get_or_create_patient(
                session, legacy_code=legacy_code, actor_id=actor_id
            )
            created_counts["patients"] += 1
        if _ensure_mapping(session, patient=patient, legacy_code=legacy_code):
            created_counts["mappings"] += 1
        if _ensure_import_state(session, patient=patient, legacy_code=legacy_code):
            created_counts["import_state"] += 1
        patients.append({"legacy_code": legacy_code, "patient_id": patient.id})

    base_date = datetime(2024, 1, 1, tzinfo=timezone.utc)

    # Perio probes + tooth surfaces for patient 1000000
    legacy_code = 1000000
    probe_count = 0
    for idx, (tooth, point) in enumerate(
        [(11, 1), (11, 2), (11, 3), (11, 4), (11, 5), (11, 6), (12, 1), (12, 2), (12, 3), (12, 4), (12, 5), (12, 6)]
    ):
        legacy_key = f"demo:{legacy_code}:{tooth}:{point}:{idx}"
        recorded_at = base_date + timedelta(days=idx)
        if _ensure_perio_probe(
            session,
            legacy_probe_key=legacy_key,
            legacy_patient_code=legacy_code,
            actor_id=actor_id,
            recorded_at=recorded_at,
            tooth=tooth,
            probing_point=point,
            depth=3 + (point % 3),
        ):
            probe_count += 1
    created_counts["perio_probes"] += probe_count

    surface_count = 0
    for tooth_id in range(1, 3):
        for surface_no in range(1, 6):
            if _ensure_tooth_surface(
                session,
                legacy_tooth_id=tooth_id,
                legacy_surface_no=surface_no,
                actor_id=actor_id,
            ):
                surface_count += 1
    created_counts["tooth_surfaces"] += surface_count

    # BPE entries for 1011978 (3), 1013684 (2), 1000035 (1)
    bpe_entries = [
        (1011978, 5001, base_date + timedelta(days=30)),
        (1011978, 5002, base_date + timedelta(days=60)),
        (1011978, 5003, base_date + timedelta(days=90)),
        (1013684, 6001, base_date + timedelta(days=45)),
        (1013684, 6002, base_date + timedelta(days=75)),
        (1000035, 7001, base_date + timedelta(days=15)),
    ]
    bpe_count = 0
    for legacy_code, bpe_id, recorded_at in bpe_entries:
        legacy_key = f"demo:{legacy_code}:{bpe_id}"
        if _ensure_bpe_entry(
            session,
            legacy_bpe_key=legacy_key,
            legacy_bpe_id=bpe_id,
            legacy_patient_code=legacy_code,
            recorded_at=recorded_at,
            actor_id=actor_id,
        ):
            bpe_count += 1
    created_counts["bpe_entries"] += bpe_count

    # BPE furcations for 1000035 (3)
    furcation_count = 0
    for idx, tooth in enumerate([16, 26, 36], start=1):
        legacy_key = f"demo:1000035:furc:{idx}"
        if _ensure_bpe_furcation(
            session,
            legacy_furcation_key=legacy_key,
            legacy_bpe_id=7001,
            legacy_patient_code=1000035,
            recorded_at=base_date + timedelta(days=15),
            actor_id=actor_id,
            tooth=tooth,
            furcation=idx,
            sextant=idx,
        ):
            furcation_count += 1
    created_counts["bpe_furcations"] += furcation_count

    # Patient notes for 1012056
    note_count = 0
    for idx in range(1, 6):
        legacy_key = f"demo:1012056:note:{idx}"
        if _ensure_patient_note(
            session,
            legacy_note_key=legacy_key,
            legacy_note_number=idx,
            legacy_patient_code=1012056,
            note_date=base_date + timedelta(days=180 + idx),
            note=f"Demo charting note {idx}",
            actor_id=actor_id,
        ):
            note_count += 1
    created_counts["patient_notes"] += note_count

    return {"patients": patients, "created": created_counts}
