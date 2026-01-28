from datetime import datetime

from typing import Literal

from pydantic import BaseModel, ConfigDict


class R4PerioProbeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    legacy_source: str
    legacy_probe_key: str
    legacy_trans_id: int | None = None
    legacy_patient_code: int | None = None
    tooth: int | None = None
    probing_point: int | None = None
    depth: int | None = None
    bleeding: int | None = None
    plaque: int | None = None
    recorded_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class R4PerioPlaqueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    legacy_source: str
    legacy_plaque_key: str
    legacy_trans_id: int | None = None
    legacy_patient_code: int | None = None
    tooth: int | None = None
    plaque: int | None = None
    bleeding: int | None = None
    recorded_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class R4BPEEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    legacy_source: str
    legacy_bpe_key: str
    legacy_bpe_id: int | None = None
    legacy_patient_code: int | None = None
    recorded_at: datetime | None = None
    sextant_1: int | None = None
    sextant_2: int | None = None
    sextant_3: int | None = None
    sextant_4: int | None = None
    sextant_5: int | None = None
    sextant_6: int | None = None
    notes: str | None = None
    user_code: int | None = None
    created_at: datetime
    updated_at: datetime


class R4BPEFurcationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    legacy_source: str
    legacy_bpe_furcation_key: str
    legacy_bpe_id: int | None = None
    legacy_patient_code: int | None = None
    tooth: int | None = None
    furcation: int | None = None
    sextant: int | None = None
    recorded_at: datetime | None = None
    notes: str | None = None
    user_code: int | None = None
    created_at: datetime
    updated_at: datetime


class R4PatientNoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    legacy_source: str
    legacy_note_key: str
    legacy_patient_code: int | None = None
    legacy_note_number: int | None = None
    note_date: datetime | None = None
    note: str | None = None
    tooth: int | None = None
    surface: int | None = None
    category_number: int | None = None
    fixed_note_code: int | None = None
    user_code: int | None = None
    created_at: datetime
    updated_at: datetime


class R4NoteCategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    legacy_source: str
    legacy_category_number: int
    description: str | None = None
    created_at: datetime
    updated_at: datetime


class R4FixedNoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    legacy_source: str
    legacy_fixed_note_code: int
    category_number: int | None = None
    description: str | None = None
    note: str | None = None
    tooth: int | None = None
    surface: int | None = None
    created_at: datetime
    updated_at: datetime


class R4ToothSurfaceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    legacy_source: str
    legacy_tooth_id: int
    legacy_surface_no: int
    label: str | None = None
    short_label: str | None = None
    sort_order: int | None = None
    created_at: datetime
    updated_at: datetime


class PaginatedR4PerioProbeOut(BaseModel):
    items: list[R4PerioProbeOut]
    total: int
    limit: int
    offset: int
    has_more: bool


class PaginatedR4PerioPlaqueOut(BaseModel):
    items: list[R4PerioPlaqueOut]
    total: int
    limit: int
    offset: int
    has_more: bool


class PaginatedR4ToothSurfaceOut(BaseModel):
    items: list[R4ToothSurfaceOut]
    total: int
    limit: int
    offset: int
    has_more: bool


class R4ChartingMetaOut(BaseModel):
    patient_id: int
    legacy_patient_code: int | None = None
    last_imported_at: datetime | None = None
    source: str = "r4"


class ChartingAuditIn(BaseModel):
    action: Literal["viewer_opened", "share_link_copied"]
    section: str | None = None
