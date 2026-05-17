from dataclasses import dataclass
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer

from app.core.config import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="http://localhost:8001/auth/login", auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    id: UUID
    email: str | None = None


async def get_current_user(
    request: Request,
    bearer_token: str | None = Depends(oauth2_scheme),
) -> CurrentUser:
    token = bearer_token or request.cookies.get("access_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate auth token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        return CurrentUser(id=UUID(payload["sub"]), email=payload.get("email"))
    except (jwt.PyJWTError, ValueError, KeyError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate auth token",
            headers={"WWW-Authenticate": "Bearer"},
        )
