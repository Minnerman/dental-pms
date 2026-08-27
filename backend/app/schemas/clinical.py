import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.clinical import ProcedureStatus, TreatmentPlanStatus
from app.schemas.actor import ActorOut

MAX_CLINICAL_TEXT_LENGTH = 2_000
MAX_FEE_PENCE = 100_000_000
TOOTH_PATTERN = re.compile(r"^(UR|UL|LR|LL)[1-8]$")
SURFACES = {"M", "O", "D", "B", "L", "I"}
SURFACE_ORDER = ("M", "O", "I", "D", "B", "L")
BPE_SCORE_PATTERN = re.compile(r"^[0-4]\*?$")


def _required_text(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("must not be blank")
    return value


def _tooth(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip().upper()
    if not TOOTH_PATTERN.fullmatch(value):
        raise ValueError("must use permanent tooth notation UR1-UL8 or LR1-LL8")
    return value


def _surface(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip().upper()
    if not value or len(value) > 5 or any(surface not in SURFACES for surface in value):
        raise ValueError("must contain only M, O, D, B, L or I")
    if len(set(value)) != len(value):
        raise ValueError("must not repeat a surface")
    return "".join(surface for surface in SURFACE_ORDER if surface in value)


def validate_tooth_surface(tooth: str | None, surface: str | None) -> None:
    if surface is None:
        return
    if tooth is None:
        raise ValueError("surface requires a tooth")
    tooth_number = int(tooth[-1])
    if "I" in surface and tooth_number > 3:
        raise ValueError("incisal surface is only valid for anterior teeth")
    if "O" in surface and tooth_number <= 3:
        raise ValueError("occlusal surface is only valid for posterior teeth")


class ToothNoteCreate(BaseModel):
    tooth: str
    surface: Optional[str] = None
    note: str = Field(max_length=MAX_CLINICAL_TEXT_LENGTH)

    _normalize_tooth = field_validator("tooth", mode="before")(_tooth)
    _normalize_surface = field_validator("surface", mode="before")(_surface)
    _normalize_note = field_validator("note")(_required_text)

    @model_validator(mode="after")
    def check_tooth_surface(self):
        validate_tooth_surface(self.tooth, self.surface)
        return self


class ToothNoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    tooth: str
    surface: Optional[str] = None
    note: str
    created_at: datetime
    created_by: ActorOut


class ProcedureCreate(BaseModel):
    appointment_id: Optional[int] = None
    tooth: Optional[str] = None
    surface: Optional[str] = None
    procedure_code: str = Field(max_length=50)
    description: str = Field(max_length=MAX_CLINICAL_TEXT_LENGTH)
    fee_pence: Optional[int] = Field(default=None, ge=0, le=MAX_FEE_PENCE)
    performed_at: Optional[datetime] = None

    _normalize_tooth = field_validator("tooth", mode="before")(_tooth)
    _normalize_surface = field_validator("surface", mode="before")(_surface)
    _normalize_code = field_validator("procedure_code")(_required_text)
    _normalize_description = field_validator("description")(_required_text)

    @model_validator(mode="after")
    def check_tooth_surface(self):
        validate_tooth_surface(self.tooth, self.surface)
        return self


class ProcedureOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    appointment_id: Optional[int] = None
    tooth: Optional[str] = None
    surface: Optional[str] = None
    procedure_code: str
    description: str
    fee_pence: Optional[int] = None
    status: ProcedureStatus
    performed_at: datetime
    created_by: ActorOut


class TreatmentPlanItemCreate(BaseModel):
    appointment_id: Optional[int] = None
    tooth: Optional[str] = None
    surface: Optional[str] = None
    procedure_code: str = Field(max_length=50)
    description: str = Field(max_length=MAX_CLINICAL_TEXT_LENGTH)
    fee_pence: Optional[int] = Field(default=None, ge=0, le=MAX_FEE_PENCE)

    _normalize_tooth = field_validator("tooth", mode="before")(_tooth)
    _normalize_surface = field_validator("surface", mode="before")(_surface)
    _normalize_code = field_validator("procedure_code")(_required_text)
    _normalize_description = field_validator("description")(_required_text)

    @model_validator(mode="after")
    def check_tooth_surface(self):
        validate_tooth_surface(self.tooth, self.surface)
        return self


class TreatmentPlanItemUpdate(BaseModel):
    appointment_id: Optional[int] = None
    tooth: Optional[str] = None
    surface: Optional[str] = None
    procedure_code: Optional[str] = Field(default=None, max_length=50)
    description: Optional[str] = Field(default=None, max_length=MAX_CLINICAL_TEXT_LENGTH)
    fee_pence: Optional[int] = Field(default=None, ge=0, le=MAX_FEE_PENCE)
    status: Optional[TreatmentPlanStatus] = None

    _normalize_tooth = field_validator("tooth", mode="before")(_tooth)
    _normalize_surface = field_validator("surface", mode="before")(_surface)

    @field_validator("procedure_code", "description")
    @classmethod
    def normalize_optional_required_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _required_text(value)

    @model_validator(mode="after")
    def reject_null_required_fields(self):
        for field in ("procedure_code", "description", "status"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} must not be null")
        return self


class TreatmentPlanItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    appointment_id: Optional[int] = None
    tooth: Optional[str] = None
    surface: Optional[str] = None
    procedure_code: str
    description: str
    fee_pence: Optional[int] = None
    status: TreatmentPlanStatus
    created_at: datetime
    updated_at: datetime
    created_by: ActorOut
    updated_by: Optional[ActorOut] = None


class BpeUpdate(BaseModel):
    scores: list[str]
    recorded_at: Optional[datetime] = None

    @field_validator("scores")
    @classmethod
    def validate_scores(cls, scores: list[str]) -> list[str]:
        if len(scores) != 6:
            raise ValueError("BPE scores must have 6 values")
        normalized = [score.strip() for score in scores]
        for score in normalized:
            if score and score != "*" and not BPE_SCORE_PATTERN.fullmatch(score):
                raise ValueError("BPE scores must be blank, *, or 0-4 with optional *")
        return normalized


class BpeOut(BaseModel):
    bpe_scores: Optional[list[str]] = None
    bpe_recorded_at: Optional[datetime] = None


class ToothHistoryOut(BaseModel):
    notes: list[ToothNoteOut]
    procedures: list[ProcedureOut]


class ClinicalSummaryOut(BaseModel):
    recent_tooth_notes: list[ToothNoteOut]
    recent_procedures: list[ProcedureOut]
    treatment_plan_items: list[TreatmentPlanItemOut]
    bpe_scores: Optional[list[str]] = None
    bpe_recorded_at: Optional[datetime] = None
