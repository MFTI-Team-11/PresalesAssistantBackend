from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RoleCreate(BaseModel):
    code: str = Field(min_length=2, max_length=64)
    title: str = Field(min_length=2, max_length=128)
    weight: int = Field(ge=0, le=100)


class RoleRead(BaseModel):
    id: UUID
    code: str
    title: str
    weight: int

    model_config = ConfigDict(from_attributes=True)
