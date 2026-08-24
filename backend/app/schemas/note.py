from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.note import NoteType
from app.schemas.actor import ActorOut

MAX_NOTE_BODY_LENGTH = 2_000


def _required_note_body(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("body must not be blank")
    return value


class NoteCreate(BaseModel):
    patient_id: Optional[int] = None
    body: str = Field(max_length=MAX_NOTE_BODY_LENGTH)
    note_type: NoteType = NoteType.clinical
    appointment_id: Optional[int] = None

    _normalize_body = field_validator("body")(_required_note_body)


class AppointmentNoteCreate(BaseModel):
    body: str = Field(max_length=MAX_NOTE_BODY_LENGTH)
    note_type: NoteType = NoteType.clinical

    _normalize_body = field_validator("body")(_required_note_body)


class NoteUpdate(BaseModel):
    body: Optional[str] = Field(default=None, max_length=MAX_NOTE_BODY_LENGTH)
    note_type: Optional[NoteType] = None

    @field_validator("body")
    @classmethod
    def normalize_optional_body(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _required_note_body(value)

    @model_validator(mode="after")
    def reject_explicit_nulls(self):
        for field in ("body", "note_type"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} must not be null")
        return self


class NoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    appointment_id: Optional[int] = None
    body: str
    note_type: NoteType
    created_at: datetime
    updated_at: datetime
    created_by: ActorOut
    updated_by: Optional[ActorOut] = None
    deleted_at: Optional[datetime] = None
    deleted_by: Optional[ActorOut] = None
