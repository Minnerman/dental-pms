from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class TimelineItem(BaseModel):
    type: str
    entity_type: str
    entity_id: str
    action: str
    occurred_at: datetime
    actor_email: Optional[str] = None
    actor_role: Optional[str] = None
    summary: str
    link: Optional[str] = None
