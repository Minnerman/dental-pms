from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models.document_template import DocumentTemplateKind
from app.schemas.actor import ActorOut


class DocumentTemplateBase(BaseModel):
    name: str
    kind: DocumentTemplateKind
    content: str
    is_active: bool = True


class DocumentTemplateCreate(DocumentTemplateBase):
    pass


class DocumentTemplateUpdate(BaseModel):
    name: Optional[str] = None
    kind: Optional[DocumentTemplateKind] = None
    content: Optional[str] = None
    is_active: Optional[bool] = None


class DocumentTemplateOut(DocumentTemplateBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
    created_by: ActorOut
    updated_by: Optional[ActorOut] = None
    deleted_at: Optional[datetime] = None
    deleted_by: Optional[ActorOut] = None
