from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import Role as RoleEnum


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    role: RoleEnum
    is_active: bool
    must_change_password: bool


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = ""
    role: RoleEnum
    password: str


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[RoleEnum] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None


class UserPasswordResetRequest(BaseModel):
    temp_password: str = Field(min_length=12)


class UserPasswordResetResponse(BaseModel):
    message: str
