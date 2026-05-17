from uuid import UUID

from typing import Any

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    fingerprint: str = Field(min_length=1, max_length=255)
    session_source: str | None = Field(default=None, max_length=64)
    device_type: str | None = Field(default=None, max_length=64)
    os_name: str | None = Field(default=None, max_length=64)
    os_version: str | None = Field(default=None, max_length=64)
    browser_name: str | None = Field(default=None, max_length=64)
    browser_version: str | None = Field(default=None, max_length=64)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    session_id: UUID
    expires_at: str
    refresh_expires_at: str
