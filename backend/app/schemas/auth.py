from pydantic import BaseModel, EmailStr, Field


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    must_change_password: bool = False


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetResponse(BaseModel):
    message: str
    reset_token: str | None = None


class PasswordResetConfirm(BaseModel):
    token: str = Field(min_length=20)
    new_password: str = Field(min_length=8)


class PasswordResetConfirmResponse(BaseModel):
    message: str


class ChangePasswordRequest(BaseModel):
    new_password: str = Field(min_length=8)
    old_password: str | None = None


class ChangePasswordResponse(BaseModel):
    message: str
