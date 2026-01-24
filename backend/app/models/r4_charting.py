from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base


class R4ToothSystem(Base, AuditMixin):
    __tablename__ = "r4_tooth_systems"
    __table_args__ = (
        UniqueConstraint(
            "legacy_source",
            "legacy_tooth_system_id",
            name="uq_r4_tooth_systems_legacy_key",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    legacy_source: Mapped[str] = mapped_column(String(120), nullable=False, default="r4")
    legacy_tooth_system_id: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class R4ToothSurface(Base, AuditMixin):
    __tablename__ = "r4_tooth_surfaces"
    __table_args__ = (
        UniqueConstraint(
            "legacy_source",
            "legacy_tooth_id",
            "legacy_surface_no",
            name="uq_r4_tooth_surfaces_legacy_key",
        ),
        Index(
            "ix_r4_tooth_surfaces_tooth",
            "legacy_source",
            "legacy_tooth_id",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    legacy_source: Mapped[str] = mapped_column(String(120), nullable=False, default="r4")
    legacy_tooth_id: Mapped[int] = mapped_column(Integer, nullable=False)
    legacy_surface_no: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    label: Mapped[str | None] = mapped_column(String(50), nullable=True)
    short_label: Mapped[str | None] = mapped_column(String(20), nullable=True)
    sort_order: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)


class R4ChartHealingAction(Base, AuditMixin):
    __tablename__ = "r4_chart_healing_actions"
    __table_args__ = (
        UniqueConstraint(
            "legacy_source",
            "legacy_action_id",
            name="uq_r4_chart_healing_actions_legacy_key",
        ),
        Index(
            "ix_r4_chart_healing_actions_patient_date",
            "legacy_source",
            "legacy_patient_code",
            "action_date",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    legacy_source: Mapped[str] = mapped_column(String(120), nullable=False, default="r4")
    legacy_action_id: Mapped[int] = mapped_column(Integer, nullable=False)
    legacy_patient_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    appointment_need_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tp_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tp_item: Mapped[int | None] = mapped_column(Integer, nullable=True)
    code_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    action_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    action_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    tooth: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    surface: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    status: Mapped[str | None] = mapped_column(String(120), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_code: Mapped[int | None] = mapped_column(Integer, nullable=True)


class R4BPEEntry(Base, AuditMixin):
    __tablename__ = "r4_bpe_entries"
    __table_args__ = (
        UniqueConstraint(
            "legacy_source",
            "legacy_bpe_key",
            name="uq_r4_bpe_entries_legacy_key",
        ),
        Index(
            "ix_r4_bpe_entries_patient_date",
            "legacy_source",
            "legacy_patient_code",
            "recorded_at",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    legacy_source: Mapped[str] = mapped_column(String(120), nullable=False, default="r4")
    legacy_bpe_key: Mapped[str] = mapped_column(String(160), nullable=False)
    legacy_bpe_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    legacy_patient_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recorded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sextant_1: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    sextant_2: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    sextant_3: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    sextant_4: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    sextant_5: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    sextant_6: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_code: Mapped[int | None] = mapped_column(Integer, nullable=True)


class R4BPEFurcation(Base, AuditMixin):
    __tablename__ = "r4_bpe_furcations"
    __table_args__ = (
        UniqueConstraint(
            "legacy_source",
            "legacy_bpe_furcation_key",
            name="uq_r4_bpe_furcations_legacy_key",
        ),
        Index(
            "ix_r4_bpe_furcations_patient",
            "legacy_source",
            "legacy_patient_code",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    legacy_source: Mapped[str] = mapped_column(String(120), nullable=False, default="r4")
    legacy_bpe_furcation_key: Mapped[str] = mapped_column(String(160), nullable=False)
    legacy_bpe_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    legacy_patient_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tooth: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    furcation: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    sextant: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    recorded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_code: Mapped[int | None] = mapped_column(Integer, nullable=True)


class R4PerioProbe(Base, AuditMixin):
    __tablename__ = "r4_perio_probes"
    __table_args__ = (
        UniqueConstraint(
            "legacy_source",
            "legacy_probe_key",
            name="uq_r4_perio_probes_legacy_key",
        ),
        Index(
            "ix_r4_perio_probes_patient",
            "legacy_source",
            "legacy_patient_code",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    legacy_source: Mapped[str] = mapped_column(String(120), nullable=False, default="r4")
    legacy_probe_key: Mapped[str] = mapped_column(String(160), nullable=False)
    legacy_trans_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    legacy_patient_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tooth: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    probing_point: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    depth: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    bleeding: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    plaque: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    recorded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class R4PerioPlaque(Base, AuditMixin):
    __tablename__ = "r4_perio_plaque"
    __table_args__ = (
        UniqueConstraint(
            "legacy_source",
            "legacy_plaque_key",
            name="uq_r4_perio_plaque_legacy_key",
        ),
        Index(
            "ix_r4_perio_plaque_patient",
            "legacy_source",
            "legacy_patient_code",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    legacy_source: Mapped[str] = mapped_column(String(120), nullable=False, default="r4")
    legacy_plaque_key: Mapped[str] = mapped_column(String(160), nullable=False)
    legacy_trans_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    legacy_patient_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tooth: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    plaque: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    bleeding: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    recorded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class R4PatientNote(Base, AuditMixin):
    __tablename__ = "r4_patient_notes"
    __table_args__ = (
        UniqueConstraint(
            "legacy_source",
            "legacy_note_key",
            name="uq_r4_patient_notes_legacy_key",
        ),
        Index(
            "ix_r4_patient_notes_patient_date",
            "legacy_source",
            "legacy_patient_code",
            "note_date",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    legacy_source: Mapped[str] = mapped_column(String(120), nullable=False, default="r4")
    legacy_note_key: Mapped[str] = mapped_column(String(200), nullable=False)
    legacy_patient_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    legacy_note_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    note_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    tooth: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    surface: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    category_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fixed_note_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    user_code: Mapped[int | None] = mapped_column(Integer, nullable=True)


class R4FixedNote(Base, AuditMixin):
    __tablename__ = "r4_fixed_notes"
    __table_args__ = (
        UniqueConstraint(
            "legacy_source",
            "legacy_fixed_note_code",
            name="uq_r4_fixed_notes_legacy_key",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    legacy_source: Mapped[str] = mapped_column(String(120), nullable=False, default="r4")
    legacy_fixed_note_code: Mapped[int] = mapped_column(Integer, nullable=False)
    category_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str | None] = mapped_column(String(200), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    tooth: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    surface: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)


class R4NoteCategory(Base, AuditMixin):
    __tablename__ = "r4_note_categories"
    __table_args__ = (
        UniqueConstraint(
            "legacy_source",
            "legacy_category_number",
            name="uq_r4_note_categories_legacy_key",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    legacy_source: Mapped[str] = mapped_column(String(120), nullable=False, default="r4")
    legacy_category_number: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str | None] = mapped_column(String(200), nullable=True)


class R4TreatmentNote(Base, AuditMixin):
    __tablename__ = "r4_treatment_notes"
    __table_args__ = (
        UniqueConstraint(
            "legacy_source",
            "legacy_treatment_note_id",
            name="uq_r4_treatment_notes_legacy_key",
        ),
        Index(
            "ix_r4_treatment_notes_patient_date",
            "legacy_source",
            "legacy_patient_code",
            "note_date",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    legacy_source: Mapped[str] = mapped_column(String(120), nullable=False, default="r4")
    legacy_treatment_note_id: Mapped[int] = mapped_column(Integer, nullable=False)
    legacy_patient_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tp_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tp_item: Mapped[int | None] = mapped_column(Integer, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    note_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    user_code: Mapped[int | None] = mapped_column(Integer, nullable=True)


class R4TemporaryNote(Base, AuditMixin):
    __tablename__ = "r4_temporary_notes"
    __table_args__ = (
        UniqueConstraint(
            "legacy_source",
            "legacy_patient_code",
            name="uq_r4_temporary_notes_legacy_key",
        ),
        Index(
            "ix_r4_temporary_notes_patient",
            "legacy_source",
            "legacy_patient_code",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    legacy_source: Mapped[str] = mapped_column(String(120), nullable=False, default="r4")
    legacy_patient_code: Mapped[int] = mapped_column(Integer, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    legacy_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    user_code: Mapped[int | None] = mapped_column(Integer, nullable=True)


class R4OldPatientNote(Base, AuditMixin):
    __tablename__ = "r4_old_patient_notes"
    __table_args__ = (
        UniqueConstraint(
            "legacy_source",
            "legacy_note_key",
            name="uq_r4_old_patient_notes_legacy_key",
        ),
        Index(
            "ix_r4_old_patient_notes_patient_date",
            "legacy_source",
            "legacy_patient_code",
            "note_date",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    legacy_source: Mapped[str] = mapped_column(String(120), nullable=False, default="r4")
    legacy_note_key: Mapped[str] = mapped_column(String(200), nullable=False)
    legacy_patient_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    legacy_note_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    note_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    tooth: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    surface: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    category_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fixed_note_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    user_code: Mapped[int | None] = mapped_column(Integer, nullable=True)


class R4ChartingImportState(Base, AuditMixin):
    __tablename__ = "r4_charting_import_state"
    __table_args__ = (
        UniqueConstraint("patient_id", name="uq_r4_charting_import_state_patient"),
        Index("ix_r4_charting_import_state_patient", "patient_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), nullable=False)
    legacy_patient_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_imported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
