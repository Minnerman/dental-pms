from datetime import date, datetime
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.patient import PatientCategory
from app.models.treatment import FeeType
from app.schemas.treatment_planning import DrawingKind, PlanningMaterial, LEVEL_KINDS, allowed_planning_materials

TreatmentLevel = Literal["tooth", "root", "crown", "surface", "general"]
FeePence = Annotated[int, Field(strict=True, ge=0, le=100_000_000)]
APPLIANCE_ROUTINE_KEYS = {"bridge": ("routine-v1:crown:2",),
    "denture": ("routine-v1:crown:3", "routine-v1:crown:4", "routine-v1:crown:5")}


class TreatmentPlanningDefaults(BaseModel):
    model_config = ConfigDict(extra="forbid")
    drawing_kind: DrawingKind
    material: PlanningMaterial | None = None


def validate_planning_defaults(level, defaults):
    if defaults is None:
        return
    values = defaults.model_dump() if isinstance(defaults, BaseModel) else defaults
    if level not in LEVEL_KINDS or values["drawing_kind"] not in LEVEL_KINDS[level]:
        raise ValueError("Planning drawing must match the treatment group")
    if values.get("material") is not None and values["material"] not in allowed_planning_materials(values["drawing_kind"], level):
        raise ValueError("Planning material must match the drawing and treatment group")


def suggested_planning_defaults(routine_key, level):
    # Stable identities authored by routine-v1, never parsed treatment names.
    # Ambiguous white materials and general complex procedures stay unspecified.
    routines = {
        "tooth": [("extraction", None), ("extraction", None), ("implant", None)],
        "root": [("other", None), ("root_canal", None), ("post_core", None)],
        "crown": [("crown", None), ("bridge", None), ("denture", "denture_acrylic"),
                  ("denture", "denture_acrylic"), ("denture", "denture_cocr"), ("veneer", None)],
        "surface": [("filling", None), ("inlay_onlay", "gold")],
        "general": [("other", None)] * 6,
    }
    for index, (kind, material) in enumerate(routines.get(level, []), 1):
        if routine_key == f"routine-v1:{level}:{index}":
            return {"drawing_kind": kind, "material": material}
    return None


def validate_fee_values(fee_type, amount, minimum, maximum):
    if fee_type == FeeType.fixed:
        if amount is None or minimum is not None or maximum is not None:
            raise ValueError("FIXED requires amount_pence only")
    elif fee_type == FeeType.range:
        if amount is not None or minimum is None or maximum is None or minimum > maximum:
            raise ValueError("RANGE requires ordered minimum and maximum amounts only")
    elif any(value is not None for value in (amount, minimum, maximum)):
        raise ValueError("N_A or unset fees must not contain an amount")


class TreatmentBase(BaseModel):
    code: Optional[str] = None
    name: str
    description: Optional[str] = None
    is_active: bool = True
    default_duration_minutes: Optional[int] = Field(default=None, ge=1)
    is_denplan_included_default: bool = False
    level: TreatmentLevel | None = None
    display_order: Annotated[int, Field(strict=True, ge=0, le=100_000)] = 0
    planning_defaults: TreatmentPlanningDefaults | None = None


class TreatmentCreate(TreatmentBase):
    code: str | None = Field(default=None, max_length=50)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def default_values(self):
        validate_planning_defaults(self.level, self.planning_defaults)
        return self

    @field_validator("name")
    @classmethod
    def nonblank_name(cls, value):
        if not value.strip():
            raise ValueError("Treatment name is required")
        return value.strip()


class TreatmentUpdate(BaseModel):
    code: Optional[str] = Field(default=None, max_length=50)
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    is_active: Optional[bool] = None
    default_duration_minutes: Optional[int] = Field(default=None, ge=1)
    is_denplan_included_default: Optional[bool] = None
    level: TreatmentLevel | None = None
    display_order: Annotated[int | None, Field(strict=True, ge=0, le=100_000)] = None
    planning_defaults: TreatmentPlanningDefaults | None = None
    expected_planning_defaults_revision: Annotated[int | None, Field(strict=True, ge=0)] = None

    @model_validator(mode="after")
    def nonnull_fields(self):
        if "planning_defaults" in self.model_fields_set and self.expected_planning_defaults_revision is None:
            raise ValueError("expected_planning_defaults_revision is required to change planning defaults")
        if "expected_planning_defaults_revision" in self.model_fields_set and "planning_defaults" not in self.model_fields_set:
            raise ValueError("Supply planning_defaults with its expected revision")
        for field in ("name", "is_active", "display_order", "is_denplan_included_default"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} must not be null")
        if self.name is not None:
            self.name = TreatmentCreate.nonblank_name(self.name)
        return self


class TreatmentOut(TreatmentBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
    created_by_user_id: int
    updated_by_user_id: Optional[int] = None
    routine_key: str | None = None
    planning_defaults_revision: int = 0
    suggested_planning_defaults: TreatmentPlanningDefaults | None = None

    @model_validator(mode="after")
    def suggestions(self):
        suggestion = suggested_planning_defaults(self.routine_key, self.level)
        self.suggested_planning_defaults = TreatmentPlanningDefaults.model_validate(suggestion) if suggestion else None
        return self


class TreatmentFeeBase(BaseModel):
    patient_category: PatientCategory
    fee_type: FeeType
    amount_pence: Optional[int] = Field(default=None, ge=0)
    min_amount_pence: Optional[int] = Field(default=None, ge=0)
    max_amount_pence: Optional[int] = Field(default=None, ge=0)
    notes: Optional[str] = None


class TreatmentFeeUpsert(TreatmentFeeBase):
    amount_pence: FeePence | None = None
    min_amount_pence: FeePence | None = None
    max_amount_pence: FeePence | None = None
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def fee_values(self):
        validate_fee_values(self.fee_type, self.amount_pence, self.min_amount_pence, self.max_amount_pence)
        return self


class TreatmentFeeOut(TreatmentFeeBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    treatment_id: int
    version_id: int | None = None
    effective_from: date | None = None


class TreatmentFeeChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    patient_category: PatientCategory
    fee_type: FeeType | None
    amount_pence: FeePence | None = None
    min_amount_pence: FeePence | None = None
    max_amount_pence: FeePence | None = None
    notes: str | None = Field(default=None, max_length=2000)
    effective_from: date
    expected_revision: Annotated[int, Field(strict=True, ge=0)]

    @model_validator(mode="after")
    def fee_values(self):
        validate_fee_values(self.fee_type, self.amount_pence, self.min_amount_pence, self.max_amount_pence)
        return self


class RoutineDefaultsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
