from __future__ import annotations

from datetime import date
from typing import Iterable, Protocol

from app.services.r4_import.types import (
    R4Appointment,
    R4AppointmentRecord,
    R4Patient,
    R4Treatment,
    R4TreatmentTransaction,
    R4User,
    R4TreatmentPlan,
    R4TreatmentPlanItem,
    R4TreatmentPlanReview,
    R4ToothSystem,
    R4ToothSurface,
    R4ChartHealingAction,
    R4BPEEntry,
    R4BPEFurcation,
    R4PerioProbe,
    R4PerioPlaque,
    R4PatientNote,
    R4FixedNote,
    R4NoteCategory,
    R4TreatmentNote,
    R4TemporaryNote,
    R4OldPatientNote,
)


class R4Source(Protocol):
    def list_patients(self, limit: int | None = None) -> Iterable[R4Patient]:
        raise NotImplementedError

    def stream_patients(
        self,
        patients_from: int | None = None,
        patients_to: int | None = None,
        limit: int | None = None,
    ) -> Iterable[R4Patient]:
        raise NotImplementedError

    def list_appts(
        self,
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int | None = None,
    ) -> Iterable[R4Appointment]:
        raise NotImplementedError

    def list_treatments(self, limit: int | None = None) -> Iterable[R4Treatment]:
        raise NotImplementedError

    def list_users(self, limit: int | None = None) -> Iterable[R4User]:
        raise NotImplementedError

    def stream_users(self, limit: int | None = None) -> Iterable[R4User]:
        raise NotImplementedError

    def stream_appointments(
        self,
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int | None = None,
    ) -> Iterable[R4AppointmentRecord]:
        raise NotImplementedError

    def stream_treatment_transactions(
        self,
        patients_from: int | None = None,
        patients_to: int | None = None,
        limit: int | None = None,
    ) -> Iterable[R4TreatmentTransaction]:
        raise NotImplementedError

    def list_treatment_plans(
        self,
        patients_from: int | None = None,
        patients_to: int | None = None,
        tp_from: int | None = None,
        tp_to: int | None = None,
        limit: int | None = None,
    ) -> Iterable[R4TreatmentPlan]:
        raise NotImplementedError

    def list_treatment_plan_items(
        self,
        patients_from: int | None = None,
        patients_to: int | None = None,
        tp_from: int | None = None,
        tp_to: int | None = None,
        limit: int | None = None,
    ) -> Iterable[R4TreatmentPlanItem]:
        raise NotImplementedError

    def list_treatment_plan_reviews(
        self,
        patients_from: int | None = None,
        patients_to: int | None = None,
        tp_from: int | None = None,
        tp_to: int | None = None,
        limit: int | None = None,
    ) -> Iterable[R4TreatmentPlanReview]:
        raise NotImplementedError

    def list_tooth_systems(self, limit: int | None = None) -> Iterable[R4ToothSystem]:
        raise NotImplementedError

    def list_tooth_surfaces(self, limit: int | None = None) -> Iterable[R4ToothSurface]:
        raise NotImplementedError

    def list_chart_healing_actions(
        self,
        patients_from: int | None = None,
        patients_to: int | None = None,
        limit: int | None = None,
    ) -> Iterable[R4ChartHealingAction]:
        raise NotImplementedError

    def list_bpe_entries(
        self,
        patients_from: int | None = None,
        patients_to: int | None = None,
        limit: int | None = None,
    ) -> Iterable[R4BPEEntry]:
        raise NotImplementedError

    def list_bpe_furcations(
        self,
        patients_from: int | None = None,
        patients_to: int | None = None,
        limit: int | None = None,
    ) -> Iterable[R4BPEFurcation]:
        raise NotImplementedError

    def list_perio_probes(
        self,
        patients_from: int | None = None,
        patients_to: int | None = None,
        limit: int | None = None,
    ) -> Iterable[R4PerioProbe]:
        raise NotImplementedError

    def list_perio_plaque(
        self,
        patients_from: int | None = None,
        patients_to: int | None = None,
        limit: int | None = None,
    ) -> Iterable[R4PerioPlaque]:
        raise NotImplementedError

    def list_patient_notes(
        self,
        patients_from: int | None = None,
        patients_to: int | None = None,
        limit: int | None = None,
    ) -> Iterable[R4PatientNote]:
        raise NotImplementedError

    def list_fixed_notes(self, limit: int | None = None) -> Iterable[R4FixedNote]:
        raise NotImplementedError

    def list_note_categories(self, limit: int | None = None) -> Iterable[R4NoteCategory]:
        raise NotImplementedError

    def list_treatment_notes(
        self,
        patients_from: int | None = None,
        patients_to: int | None = None,
        limit: int | None = None,
    ) -> Iterable[R4TreatmentNote]:
        raise NotImplementedError

    def list_temporary_notes(
        self,
        patients_from: int | None = None,
        patients_to: int | None = None,
        limit: int | None = None,
    ) -> Iterable[R4TemporaryNote]:
        raise NotImplementedError

    def list_old_patient_notes(
        self,
        patients_from: int | None = None,
        patients_to: int | None = None,
        limit: int | None = None,
    ) -> Iterable[R4OldPatientNote]:
        raise NotImplementedError
