from pydantic import BaseModel, ConfigDict

from app.models.user import Role


class ActorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    role: Role
