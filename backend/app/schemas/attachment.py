from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AttachmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    original_filename: str
    content_type: str
    byte_size: int
    created_at: datetime


class AttachmentListOut(BaseModel):
    items: list[AttachmentOut]
