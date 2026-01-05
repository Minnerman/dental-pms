from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models.note import NoteType
from app.schemas.actor import ActorOut


class NoteCreate(BaseModel):
    patient_id: Optional[int] = None
    body: str
    note_type: NoteType = NoteType.clinical
    appointment_id: Optional[int] = None


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
