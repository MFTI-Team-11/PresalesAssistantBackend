from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserRead(BaseModel):
    id: UUID
    email: EmailStr
    full_name: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class UserSelfUpdate(BaseModel):
    full_name: str = Field(min_length=2, max_length=255)

    model_config = ConfigDict(extra="forbid")


class UserAdminUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    is_active: bool | None = None

    model_config = ConfigDict(extra="forbid")
