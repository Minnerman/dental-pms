from datetime import datetime
from typing import Annotated, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.clinical import TreatmentPlanStatus
from app.schemas.actor import ActorOut
from app.schemas.clinical import ARCH_TEETH, MAX_CLINICAL_TEXT_LENGTH, MAX_FEE_PENCE, SurfaceKey, SurfaceTarget, SurfaceMaterial, MATERIAL_CROWN_KINDS, DENTURE_CROWN_KINDS, TreatmentPlanItemOut, _required_text, _tooth

Level = Literal["tooth", "root", "crown", "surface", "general"]
DrawingKind = Literal["extraction", "implant", "root_canal", "apicectomy", "post_core", "crown", "bridge", "denture", "filling", "inlay_onlay", "veneer", "sealant", "other"]
FeeMode = Literal["catalogue", "agreed", "override", "waived"]
Pence = Annotated[int, Field(strict=True, ge=0, le=MAX_FEE_PENCE)]
Revision = Annotated[int, Field(strict=True, ge=1)]
PlanningMaterial = SurfaceMaterial | Literal["metal", "porcelain_bonded", "composite", "denture_cocr", "denture_acrylic"]
LEVEL_KINDS = {
    "tooth": {"extraction", "implant", "other"},
    "root": {"root_canal", "apicectomy", "post_core", "other"},
    "crown": {"crown", "bridge", "denture", "inlay_onlay", "veneer", "other"},
    "surface": {"filling", "inlay_onlay", "sealant", "other"},
    "general": {"other"},
}


def allowed_planning_materials(kind, level):
    if kind == "denture":
        return DENTURE_CROWN_KINDS
    if kind in {"crown", "bridge", "veneer"} or kind == "inlay_onlay" and level == "crown":
        return MATERIAL_CROWN_KINDS
    if kind == "filling" or kind == "inlay_onlay" and level == "surface":
        return set(get_args(SurfaceMaterial))
    return set()


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
        elif self.tooth is None and self.level != "crown":
            raise ValueError("A tooth is required for this target")
        if self.level == "surface":
            self.surfaces = SurfaceTarget(tooth=self.tooth, surfaces=self.surfaces).surfaces
        elif self.surfaces:
            raise ValueError("Only surface-level treatment accepts selected surfaces")
        return self


class PlanningApplianceMember(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tooth: str
    role: Literal["abutment", "pontic", "wing", "denture"]
    _normalize_tooth = field_validator("tooth", mode="before")(_tooth)


class PlanningAppliance(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["bridge", "denture"]
    arch: Literal["upper", "lower"]
    members: list[PlanningApplianceMember] = Field(min_length=1, max_length=16)

    @model_validator(mode="after")
    def member_scope(self):
        teeth = [member.tooth for member in self.members]
        arch = ARCH_TEETH[self.arch]
        if len(set(teeth)) != len(teeth) or any(tooth not in arch for tooth in teeth):
            raise ValueError("Appliance members must be unique teeth in the selected arch")
        self.members = sorted(self.members, key=lambda member: arch.index(member.tooth))
        roles = {member.role for member in self.members}
        if self.kind == "bridge":
            indexes = [arch.index(member.tooth) for member in self.members]
            if (len(teeth) < 2 or indexes[-1] - indexes[0] + 1 != len(teeth)
                    or "denture" in roles or "pontic" not in roles or not roles.intersection({"abutment", "wing"})):
                raise ValueError("A bridge requires a contiguous span with at least one support and one pontic")
        elif roles != {"denture"}:
            raise ValueError("Every denture member must be a replacement tooth")
        return self


def validate_appliance_target(target, kind, appliance):
    if appliance is not None:
        if target.level != "crown" or target.tooth is not None or target.surfaces or kind != appliance.kind:
            raise ValueError("An appliance uses a crown-level whole-appliance target and its matching drawing kind")
    elif target.level != "general" and target.tooth is None:
        raise ValueError("An individual treatment requires a tooth")


class PlanningStart(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PlanningItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    treatment_id: Annotated[int, Field(strict=True, ge=1)]
    quote_token: str = Field(min_length=64, max_length=64)
    target: PlanningTarget
    drawing_kind: DrawingKind
    material: PlanningMaterial | None = None
    appliance: PlanningAppliance | None = None
    fee_mode: FeeMode
    fee_pence: Pence | None = None
    fee_reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def valid_kind(self):
        validate_appliance_target(self.target, self.drawing_kind, self.appliance)
        if self.appliance is not None and self.material is None:
            raise ValueError("Choose an explicit material for the whole appliance")
        if self.drawing_kind not in LEVEL_KINDS[self.target.level]:
            raise ValueError("Drawing kind does not match the selected target level")
        if self.material is not None and self.material not in allowed_planning_materials(self.drawing_kind, self.target.level):
            raise ValueError("Material does not match the selected drawing kind and target level")
        return self


class PlanningCustomItemCreate(BaseModel):
    """A native explicitly targeted treatment, not a fabricated catalogue entry."""
    model_config = ConfigDict(extra="forbid")
    description: str = Field(min_length=1, max_length=MAX_CLINICAL_TEXT_LENGTH)
    fee_pence: Pence
    fee_mode: Literal["agreed", "waived"]
    fee_reason: str | None = Field(default=None, max_length=500)
    target: PlanningTarget = Field(default_factory=lambda: PlanningTarget(level="general"))
    _normalize_description = field_validator("description")(_required_text)

    @model_validator(mode="after")
    def individual_target(self):
        validate_appliance_target(self.target, "other", None)
        return self


class PlanningItemUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: Revision
    material: PlanningMaterial | None = None
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
        material_change = "material" in self.model_fields_set
        if material_change and (fee_fields or self.status is not None or self.confirm_finance):
            raise ValueError("Save the material separately from fee or status changes")
        if fee_fields and self.fee_mode is None:
            raise ValueError("fee_mode is required when changing a fee")
        if not fee_fields and self.status is None and not material_change:
            raise ValueError("A fee, material or status change is required")
        if fee_fields and self.status is not None:
            raise ValueError("Save fee changes before changing treatment status")
        return self


class PlanningItemUncomplete(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: Revision
    reason: str = Field(min_length=1, max_length=500)
    confirm_finance: Annotated[bool, Field(strict=True)]

    @field_validator("reason")
    @classmethod
    def reason_required(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("A reason is required to correct a completion")
        return value

    @field_validator("confirm_finance")
    @classmethod
    def explicitly_confirmed(cls, value):
        if value is not True:
            raise ValueError("Confirm the account adjustment; payments and refunds are unchanged")
        return value


class PlanningItemOut(TreatmentPlanItemOut):
    plan_id: int
    treatment_id: int | None
    revision: int
    target: PlanningTarget
    drawing_kind: DrawingKind
    material: PlanningMaterial | None = None
    appliance: PlanningAppliance | None = None
    pricing: dict | None = None
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
