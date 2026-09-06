from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.clinical import TreatmentPlanStatus
from app.schemas.actor import ActorOut
from app.schemas.clinical import MAX_FEE_PENCE, SurfaceKey, SurfaceTarget, TreatmentPlanItemOut, _tooth

Level = Literal["tooth", "root", "crown", "surface", "general"]
DrawingKind = Literal["extraction", "implant", "root_canal", "apicectomy", "post_core", "crown", "bridge", "denture", "filling", "inlay_onlay", "veneer", "sealant", "other"]
FeeMode = Literal["catalogue", "agreed", "override", "waived"]
Pence = Annotated[int, Field(strict=True, ge=0, le=MAX_FEE_PENCE)]
Revision = Annotated[int, Field(strict=True, ge=1)]
LEVEL_KINDS = {
    "tooth": {"extraction", "implant", "other"},
    "root": {"root_canal", "apicectomy", "post_core", "other"},
    "crown": {"crown", "bridge", "denture", "inlay_onlay", "veneer", "other"},
    "surface": {"filling", "inlay_onlay", "sealant", "other"},
    "general": {"other"},
}


class PlanningTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")
    level: Level
    tooth: str | None = None
    surfaces: list[SurfaceKey] = Field(default_factory=list, max_length=5)
    _normalize_tooth = field_validator("tooth", mode="before")(_tooth)

    @model_validator(mode="after")
    def valid_target(self):
        if self.level == "general":
            if self.tooth is not None or self.surfaces:
                raise ValueError("General treatment has no tooth or surfaces")
        elif self.tooth is None:
            raise ValueError("A tooth is required for this target")
        if self.level == "surface":
            self.surfaces = SurfaceTarget(tooth=self.tooth, surfaces=self.surfaces).surfaces
        elif self.surfaces:
            raise ValueError("Only surface-level treatment accepts selected surfaces")
        return self


class PlanningStart(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PlanningItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    treatment_id: Annotated[int, Field(strict=True, ge=1)]
    quote_token: str = Field(min_length=64, max_length=64)
    target: PlanningTarget
    drawing_kind: DrawingKind
    fee_mode: FeeMode
    fee_pence: Pence | None = None
    fee_reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def valid_kind(self):
        if self.drawing_kind not in LEVEL_KINDS[self.target.level]:
            raise ValueError("Drawing kind does not match the selected target level")
        return self


class PlanningItemUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: Revision
    status: TreatmentPlanStatus | None = None
    fee_mode: FeeMode | None = None
    fee_pence: Pence | None = None
    fee_reason: str | None = Field(default=None, max_length=500)
    confirm_finance: Annotated[bool, Field(strict=True)] = False

    @model_validator(mode="after")
    def validate_update(self):
        if "status" in self.model_fields_set and self.status is None:
            raise ValueError("status must not be null")
        fee_fields = self.model_fields_set & {"fee_mode", "fee_pence", "fee_reason"}
        if fee_fields and self.fee_mode is None:
            raise ValueError("fee_mode is required when changing a fee")
        if not fee_fields and self.status is None:
            raise ValueError("A fee change or status is required")
        if fee_fields and self.status is not None:
            raise ValueError("Save fee changes before changing treatment status")
        return self


class PlanningItemOut(TreatmentPlanItemOut):
    plan_id: int
    treatment_id: int
    revision: int
    target: PlanningTarget
    drawing_kind: DrawingKind
    catalogue_snapshot: dict
    fee_mode: FeeMode
    fee_reason: str | None
    completed_procedure_id: int | None


class PlanningPlanOut(BaseModel):
    id: int
    created_at: datetime
    created_by: ActorOut
    snapshot: dict
    items: list[PlanningItemOut]


class PlanningOut(BaseModel):
    patient_id: int
    plan: PlanningPlanOut | None
    earlier_items: list[TreatmentPlanItemOut]
    earlier_items_total: int
