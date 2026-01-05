from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.schemas.actor import ActorOut


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    actor: Optional[ActorOut] = None
    actor_email: Optional[str] = None
    action: str
    entity_type: str
    entity_id: str
    request_id: Optional[str] = None
    ip_address: Optional[str] = None
    before_json: Optional[dict] = None
    after_json: Optional[dict] = None
