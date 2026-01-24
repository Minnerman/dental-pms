from __future__ import annotations

import logging

from pydantic import EmailStr, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger("dental_pms.config")


class Settings(BaseSettings):
    app_env: str = "development"
    secret_key: str | None = None
    jwt_secret: str | None = None
    jwt_alg: str = "HS256"
    access_token_expire_minutes: int = 120
    reset_token_expire_minutes: int = Field(default=30, alias="RESET_TOKEN_EXPIRE_MINUTES")
    reset_token_debug: bool = Field(default=False, alias="RESET_TOKEN_DEBUG")
    reset_requests_per_minute: int = Field(default=5, alias="RESET_REQUESTS_PER_MINUTE")
    reset_confirm_per_minute: int = Field(default=10, alias="RESET_CONFIRM_PER_MINUTE")
    database_url: str = "postgresql+psycopg://dental_pms:change-me@localhost:5432/dental_pms"
    admin_email: EmailStr = "admin@example.com"
    admin_password: str = "ChangeMe123!"
    feature_charting_viewer: bool = Field(default=True, alias="FEATURE_CHARTING_VIEWER")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator(
        "access_token_expire_minutes",
        "reset_token_expire_minutes",
        "reset_requests_per_minute",
        "reset_confirm_per_minute",
        mode="before",
    )
    @classmethod
    def _coerce_empty_ints(cls, value, info):
        if value in {"", None}:
            return cls.model_fields[info.field_name].default
        return value


def _is_production(app_env: str) -> bool:
    return app_env.strip().lower() in {"prod", "production"}


def _is_weak_secret(value: str) -> bool:
    lowered = value.lower()
    if len(value) < 32:
        return True
    return lowered in {"change-me", "changeme", "secret", "password"}


def _is_default_admin_email(email: str) -> bool:
    return email.strip().lower() == "admin@example.com"


def validate_settings(settings: Settings) -> None:
    app_env = settings.app_env.strip().lower()
    if not settings.secret_key and settings.jwt_secret:
        settings.secret_key = settings.jwt_secret
    if not settings.secret_key:
        settings.secret_key = "change-me"

    if len(settings.admin_password.encode("utf-8")) > 72:
        raise RuntimeError("ADMIN_PASSWORD exceeds bcrypt 72-byte limit")

    production = _is_production(app_env)
    failures: list[str] = []
    warnings: list[str] = []

    if _is_weak_secret(settings.secret_key):
        msg = "SECRET_KEY is missing or too weak (min 32 chars, avoid defaults)"
        if production:
            failures.append(msg)
        else:
            warnings.append(msg)

    if _is_default_admin_email(str(settings.admin_email)):
        msg = "ADMIN_EMAIL is still admin@example.com"
        if production:
            failures.append(msg)
        else:
            warnings.append(msg)

    if len(settings.admin_password) < 12:
        msg = "ADMIN_PASSWORD too short (min 12 chars)"
        if production:
            failures.append(msg)
        else:
            warnings.append(msg)

    if settings.admin_password.strip() in {"ChangeMe123!", "change-me", "changeme"}:
        msg = "ADMIN_PASSWORD is set to a default value"
        if production:
            failures.append(msg)
        else:
            warnings.append(msg)

    for warning in warnings:
        logger.warning("Config warning: %s", warning)

    if failures:
        raise RuntimeError("Config validation failed: " + "; ".join(failures))


settings = Settings()
