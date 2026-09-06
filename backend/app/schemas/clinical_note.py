from datetime import date, datetime
import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.actor import ActorOut

NoteCategory = Literal["clinical", "admin", "medical", "soft_tissue", "correspondence"]
Revision = Annotated[int, Field(strict=True, ge=1)]
MAX_NATIVE_NOTE_LENGTH = 100_000
Code = Annotated[str, Field(strict=True, min_length=1, max_length=80)]


def unique_codes(values: list[str]) -> list[str]:
    if any(not value.strip() or value != value.strip() for value in values):
        raise ValueError("codes must be nonblank labels without surrounding whitespace")
    if len(values) != len(set(values)):
        raise ValueError("codes must not repeat")
    return values


class NoteMetadataCreate(BaseModel):
    clinical_date: date | None = None
    category: NoteCategory | None = None
    template_id: Annotated[int, Field(strict=True, ge=1)] | None = None
    template_revision: Revision | None = None
    codes: list[Code] = Field(default_factory=list, max_length=20)
    _validate_codes = field_validator("codes")(unique_codes)

    @model_validator(mode="after")
    def template_pair(self):
        if (self.template_id is None) != (self.template_revision is None):
            raise ValueError("template_id and template_revision must be supplied together")
        return self


class NoteMetadataOut(BaseModel):
    revision: int
    clinical_date: date | None = None
    category: NoteCategory | None = None
    template_id: int | None = None
    template_revision: int | None = None
    codes: list[str] = Field(default_factory=list)


class NoteAmendmentFields(BaseModel):
    clinical_date: date | None = None
    category: NoteCategory | None = None
    reason: str | None = Field(default=None, max_length=500)
    expected_revision: Revision | None = None


class ToothNoteAmendment(NoteAmendmentFields):
    model_config = ConfigDict(extra="forbid")
    expected_revision: Revision
    note: str | None = Field(default=None, max_length=MAX_NATIVE_NOTE_LENGTH)

    @model_validator(mode="after")
    def explicit_body(self):
        if "note" in self.model_fields_set and (self.note is None or not self.note.strip()):
            raise ValueError("note must not be null or blank")
        return self


class RevisionActor(BaseModel):
    id: int
    name: str | None


class NativeNoteRevisionOut(BaseModel):
    revision: int
    body: str
    note_type: str | None = None
    clinical_date: date | None
    category: NoteCategory | None
    recorded_at: datetime
    recorded_by: RevisionActor | None
    reason: str | None
    baseline: bool
    template_id: int | None
    template_revision: int | None
    codes: list[str]
    archived: bool = False
    deleted_at: datetime | None = None


class NativeNoteHistoryOut(BaseModel):
    items: list[NativeNoteRevisionOut]
    next_before_revision: int | None = None


class TemplateField(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_]{0,31}$")
    label: str = Field(min_length=1, max_length=100)
    options: list[Annotated[str, Field(strict=True, min_length=1, max_length=200)]] = Field(min_length=1, max_length=40)
    required: bool = Field(strict=True)

    @model_validator(mode="after")
    def unique_options(self):
        if not self.label.strip() or any(not value.strip() for value in self.options):
            raise ValueError("labels and options must not be blank")
        if len(self.options) != len(set(self.options)):
            raise ValueError("options must not repeat")
        return self


class ClinicalNoteTemplateCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=160)
    category: NoteCategory = "clinical"
    body: str = Field(min_length=1, max_length=MAX_NATIVE_NOTE_LENGTH)
    fields: list[TemplateField] = Field(default_factory=list, max_length=20)
    codes: list[Code] = Field(default_factory=list, max_length=20)
    is_active: bool = Field(default=True, strict=True)
    _validate_codes = field_validator("codes")(unique_codes)

    @model_validator(mode="after")
    def validate_template(self):
        if not self.title.strip() or not self.body.strip():
            raise ValueError("title and body must not be blank")
        keys = [field.key for field in self.fields]
        if len(keys) != len(set(keys)):
            raise ValueError("field keys must not repeat")
        # Bounded placeholder grammar avoids quadratic scans through malformed
        # long clinical text containing many unmatched opening braces.
        pattern = r"\{\{([A-Za-z][A-Za-z0-9_]{0,31})\}\}"
        placeholders = re.findall(pattern, self.body)
        if set(placeholders) != set(keys):
            raise ValueError("each {{key}} placeholder must match a defined dropdown field")
        remainder = re.sub(pattern, "", self.body)
        if "{{" in remainder or "}}" in remainder:
            raise ValueError("malformed template placeholder")
        return self


class ClinicalNoteTemplateUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: Revision
    title: str | None = Field(default=None, min_length=1, max_length=160)
    category: NoteCategory | None = None
    body: str | None = Field(default=None, min_length=1, max_length=MAX_NATIVE_NOTE_LENGTH)
    fields: list[TemplateField] | None = Field(default=None, max_length=20)
    codes: list[Code] | None = Field(default=None, max_length=20)
    is_active: bool | None = Field(default=None, strict=True)

    @model_validator(mode="after")
    def nonnull(self):
        for field in self.model_fields_set - {"expected_revision"}:
            if getattr(self, field) is None:
                raise ValueError(f"{field} must not be null")
        return self


class ClinicalNoteTemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    category: NoteCategory
    body: str
    fields: list[TemplateField]
    codes: list[str]
    revision: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    created_by: ActorOut
    updated_by: ActorOut | None
