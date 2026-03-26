from typing import Optional
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import Role as RoleEnum
from app.services.users import PASSWORD_MIN_LENGTH


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    role: RoleEnum
    is_active: bool
    must_change_password: bool
    created_at: datetime


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = ""
    role: RoleEnum
    temp_password: str = Field(min_length=PASSWORD_MIN_LENGTH)


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[RoleEnum] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None


class UserPasswordResetRequest(BaseModel):
    temp_password: str = Field(min_length=PASSWORD_MIN_LENGTH)


class UserPasswordResetResponse(BaseModel):
    message: str
