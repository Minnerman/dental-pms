import re
from datetime import datetime
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.clinical import ProcedureStatus, ToothConditionValue, TreatmentPlanStatus
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


class ToothConditionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    teeth: list[str] = Field(min_length=1, max_length=32)
    condition: ToothConditionValue | None = None
    dentition: Literal["permanent", "deciduous"] | None = None
    movement: Literal["forward", "backward"] | None = None
    rotation: Literal["clockwise", "anticlockwise"] | None = None
    expected_revisions: dict[str, Annotated[int, Field(strict=True, ge=0)]]

    @field_validator("teeth", mode="before")
    @classmethod
    def normalize_teeth(cls, value):
        if not isinstance(value, list) or any(
            not isinstance(tooth, str) for tooth in value
        ):
            raise ValueError("teeth must be a list of tooth identifiers")
        teeth = [_tooth(tooth) for tooth in value]
        if len(set(teeth)) != len(teeth):
            raise ValueError("teeth must not repeat")
        return sorted(teeth)

    @field_validator("expected_revisions", mode="before")
    @classmethod
    def normalize_revision_keys(cls, value):
        if not isinstance(value, dict) or any(
            not isinstance(tooth, str) for tooth in value
        ):
            raise ValueError("expected_revisions must map tooth identifiers to revisions")
        normalized = {_tooth(tooth): revision for tooth, revision in value.items()}
        if len(normalized) != len(value):
            raise ValueError("expected_revisions must not repeat a tooth")
        return normalized

    @model_validator(mode="after")
    def check_scope(self):
        if set(self.expected_revisions) != set(self.teeth):
            raise ValueError("expected_revisions must contain exactly the selected teeth")
        if not self.model_fields_set.intersection({"condition", "dentition", "movement", "rotation"}):
            raise ValueError("supply at least one condition, dentition, movement or rotation observation")
        if (self.condition == ToothConditionValue.deciduous or self.dentition == "deciduous") and any(
            int(tooth[-1]) > 5 for tooth in self.teeth
        ):
            raise ValueError("deciduous teeth are supported only in positions 1-5")
        if "dentition" in self.model_fields_set:
            if self.condition == ToothConditionValue.deciduous and self.dentition != "deciduous":
                raise ValueError("legacy deciduous condition requires deciduous dentition")
            if self.condition in {ToothConditionValue.unrecorded, ToothConditionValue.implant} and self.dentition is not None:
                raise ValueError("reset and implant conditions clear dentition to unspecified")
        return self


RootConditionValue = Literal["filled_sound", "filled_defective", "post_core_sound", "post_core_defective"]


def schematic_root_count(tooth: str, dentition: str) -> int:
    """Numbered schematic slots, not a claim about individual patient anatomy."""
    position = int(tooth[-1])
    upper = tooth.startswith("U")
    if dentition == "deciduous":
        if position > 5:
            raise ValueError("deciduous teeth are supported only in positions 1-5")
        return (3 if upper else 2) if position in (4, 5) else 1
    if position >= 6:
        return 3 if upper else 2
    return 2 if upper and position == 4 else 1


class RootObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    condition: RootConditionValue | None
    apicectomy: bool = Field(strict=True)


class RootConditionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    teeth: list[str] = Field(min_length=1, max_length=32)
    condition: RootConditionValue | None = None
    apicectomy: bool = Field(default=False, strict=True)
    expected_revisions: dict[str, Annotated[int, Field(strict=True, ge=0)]]

    @field_validator("teeth", mode="before")
    @classmethod
    def normalize_teeth(cls, value):
        return ToothConditionUpdate.normalize_teeth(value)

    @field_validator("expected_revisions", mode="before")
    @classmethod
    def normalize_revision_keys(cls, value):
        return ToothConditionUpdate.normalize_revision_keys(value)

    @model_validator(mode="after")
    def check_observation(self):
        if set(self.expected_revisions) != set(self.teeth):
            raise ValueError("expected_revisions must contain exactly the selected teeth")
        if not self.model_fields_set.intersection({"condition", "apicectomy"}):
            raise ValueError("supply a root condition or apicectomy observation")
        return self


CrownKind = Literal["fractured", "missing", "metal", "gold", "porcelain", "porcelain_bonded", "composite", "denture_cocr", "denture_acrylic"]
CrownWriteKind = Literal["missing", "metal", "gold", "porcelain", "porcelain_bonded", "composite", "denture_cocr", "denture_acrylic"]
MATERIAL_CROWN_KINDS = {"metal", "gold", "porcelain", "porcelain_bonded", "composite"}
DENTURE_CROWN_KINDS = {"denture_cocr", "denture_acrylic"}
CrownIssue = Literal["decayed", "defective", "fractured", "poor_fitting"]


class CrownObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: CrownKind | None
    issues: list[CrownIssue] = Field(max_length=4)

    @field_validator("issues", mode="before")
    @classmethod
    def canonical_issues(cls, value):
        if not isinstance(value, list) or any(not isinstance(issue, str) for issue in value):
            raise ValueError("issues must be a list of crown issue identifiers")
        if len(set(value)) != len(value):
            raise ValueError("issues must not repeat")
        return sorted(value)

    @model_validator(mode="after")
    def check_material_issues(self):
        if self.issues and self.kind not in MATERIAL_CROWN_KINDS:
            raise ValueError("issues apply only to a material crown")
        return self


class CrownConditionUpdate(CrownObservation):
    # Retired standalone fracture remains readable, but cannot be newly authored.
    kind: CrownWriteKind | None
    teeth: list[str] = Field(min_length=1, max_length=32)
    expected_revisions: dict[str, Annotated[int, Field(strict=True, ge=0)]]

    @field_validator("teeth", mode="before")
    @classmethod
    def normalize_teeth(cls, value):
        return ToothConditionUpdate.normalize_teeth(value)

    @field_validator("expected_revisions", mode="before")
    @classmethod
    def normalize_revision_keys(cls, value):
        return ToothConditionUpdate.normalize_revision_keys(value)

    @model_validator(mode="after")
    def check_scope(self):
        if set(self.expected_revisions) != set(self.teeth):
            raise ValueError("expected_revisions must contain exactly the selected teeth")
        return self


# Current native surface notation is deliberately separate from legacy
# procedure/note surface parsing, whose historical L values stay unchanged.
SurfaceKey = Literal["M", "O", "I", "D", "B", "P", "L"]
NATIVE_SURFACE_ORDER = ("M", "O", "I", "D", "B", "P", "L")
SurfaceMaterial = Literal[
    "amalgam", "precious_metal", "carbon_fibre", "gold", "glass_ionomer",
    "cast_metal_alloy", "metallic", "porcelain", "resin", "stainless_steel",
    "unknown", "vmk", "combination",
]
SurfaceCondition = Literal["sound", "carious_early", "carious_arrested", "carious_established", "defective"]
SurfaceDefect = Literal[
    "open_contact", "cracked", "broken", "faceted", "overhang", "over_contour",
    "under_contour", "cosmetic", "leaking",
]
CARIOUS_SURFACE_CONDITIONS = {"carious_early", "carious_arrested", "carious_established"}


class SurfaceObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["carious", "defective", "restored", "sealant"] | None
    material: SurfaceMaterial | None
    condition: SurfaceCondition | None
    defects: list[SurfaceDefect] = Field(max_length=9)

    @field_validator("defects", mode="before")
    @classmethod
    def canonical_defects(cls, value):
        if not isinstance(value, list) or any(not isinstance(defect, str) for defect in value):
            raise ValueError("defects must be a list of surface defect identifiers")
        if len(set(value)) != len(value):
            raise ValueError("defects must not repeat")
        return sorted(value)

    @model_validator(mode="after")
    def check_observation(self):
        if self.kind is None:
            if self.material is not None or self.condition is not None or self.defects:
                raise ValueError("a surface reset requires null material/condition and no defects")
        elif self.kind == "carious":
            if self.material is not None or self.condition not in CARIOUS_SURFACE_CONDITIONS | {None} or self.defects:
                raise ValueError("carious surfaces allow only an optional caries stage")
        elif self.kind == "defective":
            if self.material is not None or self.condition != "defective":
                raise ValueError("defective surfaces require defective condition and no material")
        elif self.kind == "restored":
            if self.material is None:
                raise ValueError("restored surfaces require an explicit material, including unknown if necessary")
        elif self.kind == "sealant" and self.material is not None:
            raise ValueError("sealant surfaces do not have a restoration material")
        if self.defects and self.condition != "defective":
            raise ValueError("surface defects require a defective condition")
        return self


class SurfaceTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tooth: str
    surfaces: list[SurfaceKey] = Field(min_length=1, max_length=5)
    _normalize_tooth = field_validator("tooth")(_tooth)

    @field_validator("surfaces", mode="before")
    @classmethod
    def canonical_surfaces(cls, value):
        if not isinstance(value, list) or any(not isinstance(surface, str) for surface in value):
            raise ValueError("surfaces must be a list of surface identifiers")
        surfaces = [surface.strip().upper() for surface in value]
        if len(set(surfaces)) != len(surfaces):
            raise ValueError("surfaces must not repeat")
        if any(surface not in NATIVE_SURFACE_ORDER for surface in surfaces):
            raise ValueError("unsupported native surface identifier")
        return sorted(surfaces, key=NATIVE_SURFACE_ORDER.index)

    @model_validator(mode="after")
    def check_anatomy(self):
        anterior = int(self.tooth[-1]) <= 3
        if ("I" in self.surfaces and not anterior) or ("O" in self.surfaces and anterior):
            raise ValueError("use incisal for positions 1-3 and occlusal for positions 4-8")
        if ("P" in self.surfaces and not self.tooth.startswith("U")) or (
                "L" in self.surfaces and not self.tooth.startswith("L")):
            raise ValueError("use palatal for upper teeth and lingual for lower teeth")
        return self


class SurfaceConditionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    targets: list[SurfaceTarget] = Field(min_length=1, max_length=32)
    observation: SurfaceObservation
    expected_revisions: dict[str, Annotated[int, Field(strict=True, ge=0)]]

    @field_validator("expected_revisions", mode="before")
    @classmethod
    def normalize_revision_keys(cls, value):
        return ToothConditionUpdate.normalize_revision_keys(value)

    @model_validator(mode="after")
    def check_scope(self):
        teeth = [target.tooth for target in self.targets]
        if len(set(teeth)) != len(teeth):
            raise ValueError("supply only one target per tooth")
        if set(self.expected_revisions) != set(teeth):
            raise ValueError("expected_revisions must contain exactly the target teeth")
        self.targets.sort(key=lambda target: target.tooth)
        return self


ARCH_TEETH = {
    "upper": [f"UR{n}" for n in range(8, 0, -1)] + [f"UL{n}" for n in range(1, 9)],
    "lower": [f"LR{n}" for n in range(8, 0, -1)] + [f"LL{n}" for n in range(1, 9)],
}
BridgeRole = Literal["abutment", "pontic", "wing"]


class BridgeMember(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tooth: str
    role: BridgeRole
    _normalize_tooth = field_validator("tooth")(_tooth)


class BridgeCrown(CrownObservation):
    kind: Literal["metal", "gold", "porcelain", "porcelain_bonded", "composite"]


class BridgeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    members: list[BridgeMember] = Field(min_length=2, max_length=16)
    crown: BridgeCrown | None = None
    expected_revisions: dict[str, Annotated[int, Field(strict=True, ge=0)]]

    @field_validator("crown", mode="before")
    @classmethod
    def explicit_crown_must_be_material(cls, value):
        if value is None:
            raise ValueError("omit crown to preserve observations, or provide a material crown")
        return value

    @field_validator("expected_revisions", mode="before")
    @classmethod
    def normalize_revision_keys(cls, value):
        return ToothConditionUpdate.normalize_revision_keys(value)

    @model_validator(mode="after")
    def validate_span(self):
        teeth = [member.tooth for member in self.members]
        if len(set(teeth)) != len(teeth):
            raise ValueError("bridge teeth must not repeat")
        if set(self.expected_revisions) != set(teeth):
            raise ValueError("expected_revisions must contain exactly the bridge members")
        if len({tooth[0] for tooth in teeth}) != 1:
            raise ValueError("a bridge must stay within one arch")
        order = ARCH_TEETH["upper" if teeth[0].startswith("U") else "lower"]
        indexes = sorted(order.index(tooth) for tooth in teeth)
        if indexes[-1] - indexes[0] + 1 != len(indexes):
            raise ValueError("assign an explicit role to every tooth position in the bridge span")
        roles = {member.role for member in self.members}
        if "pontic" not in roles or not roles.intersection({"abutment", "wing"}):
            raise ValueError("a bridge requires at least one pontic and one support")
        self.members.sort(key=lambda member: order.index(member.tooth))
        return self


class BridgeReset(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revisions: dict[str, Annotated[int, Field(strict=True, ge=0)]] = Field(min_length=2, max_length=16)

    @field_validator("expected_revisions", mode="before")
    @classmethod
    def normalize_revision_keys(cls, value):
        return ToothConditionUpdate.normalize_revision_keys(value)


class BridgeOut(BaseModel):
    id: int
    arch: Literal["upper", "lower"]
    span_start: str
    span_end: str
    members: list[BridgeMember]


class ToothConditionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    condition: ToothConditionValue | None
    dentition: Literal["permanent", "deciduous"] | None
    movement: Literal["forward", "backward"] | None
    rotation: Literal["clockwise", "anticlockwise"] | None
    root_observations: dict[Literal["1", "2", "3"], RootObservation]
    crown_observation: CrownObservation | None
    surface_observations: dict[SurfaceKey, SurfaceObservation]
    bridge_group_id: int | None
    bridge_role: BridgeRole | None
    revision: int
    updated_at: datetime
    updated_by: ActorOut


class ToothConditionsOut(BaseModel):
    patient_id: int
    teeth: dict[str, ToothConditionOut]
    note_teeth: list[str]
    bridges: list[BridgeOut]


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
