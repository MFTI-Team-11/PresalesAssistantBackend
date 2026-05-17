from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SessionRead(BaseModel):
    id: UUID
    user_id: UUID
    token_jti: str
    ip_address: str | None
    fingerprint: str | None
    user_agent: str | None
    session_source: str | None
    device_type: str | None
    os_name: str | None
    os_version: str | None
    browser_name: str | None
    browser_version: str | None
    session_metadata: dict
    expires_at: datetime
    refresh_expires_at: datetime
    revoked_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
