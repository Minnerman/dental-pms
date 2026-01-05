from pydantic import BaseModel, ConfigDict, EmailStr

from app.models.user import Role


class ActorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    role: Role
