from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
import logging

from app.services.r4_import.types import R4AppointmentRecord


UNMAPPED_MISSING_PATIENT_CODE = "missing_patient_code"
UNMAPPED_MISSING_MAPPING = "missing_patient_mapping"
UNMAPPED_MAPPED_TO_DELETED_PATIENT = "mapped_to_deleted_patient"

logger = logging.getLogger(__name__)


@dataclass
class R4LinkageReportBuilder:
    patient_mappings: dict[int, int]
    deleted_patient_ids: set[int]
    manual_mappings: dict[int, int] = field(default_factory=dict)
    imported_appointment_ids: set[int] | None = None
    top_limit: int = 10
    appointments_total: int = 0
    appointments_with_patient_code: int = 0
    appointments_missing_patient_code: int = 0
    appointments_mapped: int = 0
    appointments_unmapped: int = 0
    appointments_imported: int = 0
    appointments_not_imported: int = 0
    unmapped_reasons: Counter[str] = field(default_factory=Counter)
    unmapped_patient_code_counts: Counter[int] = field(default_factory=Counter)

    def ingest(self, appt: R4AppointmentRecord) -> str | None:
        self.appointments_total += 1
        reason: str | None = None
        patient_code = appt.patient_code

        if self.imported_appointment_ids is not None:
            if appt.appointment_id in self.imported_appointment_ids:
                self.appointments_imported += 1
            else:
                self.appointments_not_imported += 1

        if patient_code is None:
            self.appointments_missing_patient_code += 1
            reason = UNMAPPED_MISSING_PATIENT_CODE
        else:
            self.appointments_with_patient_code += 1
            patient_id = self._resolve_patient_id(patient_code)
            if patient_id is None:
                reason = UNMAPPED_MISSING_MAPPING
            elif patient_id in self.deleted_patient_ids:
                reason = UNMAPPED_MAPPED_TO_DELETED_PATIENT
            else:
                self.appointments_mapped += 1

        if reason is not None:
            self.appointments_unmapped += 1
            self.unmapped_reasons[reason] += 1
            if patient_code is not None:
                self.unmapped_patient_code_counts[patient_code] += 1
        return reason

    def _resolve_patient_id(self, patient_code: int) -> int | None:
        if patient_code in self.manual_mappings:
            target_patient_id = self.manual_mappings[patient_code]
            logger.info(
                "R4 manual mapping used",
                extra={
                    "patient_code": int(patient_code),
                    "target_patient_id": int(target_patient_id),
                },
            )
            return target_patient_id
        return self.patient_mappings.get(patient_code)

    def finalize(self) -> dict[str, object]:
        top_unmapped = [
            {"patient_code": code, "count": count}
            for code, count in self.unmapped_patient_code_counts.most_common(self.top_limit)
        ]
        payload: dict[str, object] = {
            "appointments_total": self.appointments_total,
            "appointments_with_patient_code": self.appointments_with_patient_code,
            "appointments_missing_patient_code": self.appointments_missing_patient_code,
            "appointments_mapped": self.appointments_mapped,
            "appointments_unmapped": self.appointments_unmapped,
            "unmapped_reasons": dict(self.unmapped_reasons),
            "top_unmapped_patient_codes": top_unmapped,
        }
        if self.imported_appointment_ids is not None:
            payload.update(
                {
                    "appointments_imported": self.appointments_imported,
                    "appointments_not_imported": self.appointments_not_imported,
                }
            )
        return payload
