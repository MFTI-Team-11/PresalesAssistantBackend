from uuid import uuid4

from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    refresh_token_expires_at,
    token_expires_at,
    verify_password,
)
from app.modules.auth.schemas import LoginRequest, RegisterRequest, TokenResponse
from app.modules.roles.service import RoleService
from app.modules.sessions.service import SessionService
from app.modules.users.models import User
from app.modules.users.service import UserService


class AuthService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.users = UserService(session)
        self.roles = RoleService(session)
        self.sessions = SessionService(session)

    async def register(self, data: RegisterRequest, request: Request) -> TokenResponse:
        if await self.users.get_by_email(data.email):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already exists")
        await self.roles.ensure_default_roles()
        default_role = await self.roles.get_by_code("CUSTOMER")
        user = User(
            email=data.email.lower(),
            full_name=data.full_name,
            hashed_password=hash_password(data.password),
            roles=[default_role] if default_role else [],
        )
        self.session.add(user)
        await self.session.flush()
        response = await self._create_session_token(user, request)
        await self.session.commit()
        return response

    async def login(self, payload: LoginRequest, request: Request) -> TokenResponse:
        user = await self.users.get_by_email(payload.email)
        if not user or not verify_password(payload.password, user.hashed_password):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bad credentials")
        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive")
        return await self._create_session_token(user, request, payload)

    async def refresh(self, refresh_token: str) -> TokenResponse:
        auth_session = await self.sessions.validate_refresh_token(refresh_token)
        user = await self.users.get_by_id(auth_session.user_id)
        if not user or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user")
        expires_at = token_expires_at()
        refresh_expires_at = refresh_token_expires_at()
        access_token, token_jti = create_access_token(user.id, user.email, auth_session.id, expires_at)
        new_refresh_token = create_refresh_token()
        await self.sessions.rotate_tokens(
            auth_session=auth_session,
            access_token=access_token,
            token_jti=token_jti,
            refresh_token=new_refresh_token,
            expires_at=expires_at,
            refresh_expires_at=refresh_expires_at,
        )
        return TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
            session_id=auth_session.id,
            expires_at=expires_at.isoformat(),
            refresh_expires_at=refresh_expires_at.isoformat(),
        )

    async def _create_session_token(
        self,
        user: User,
        request: Request,
        payload: LoginRequest | None = None,
    ) -> TokenResponse:
        session_id = uuid4()
        expires_at = token_expires_at()
        refresh_expires_at = refresh_token_expires_at()
        token, token_jti = create_access_token(user.id, user.email, session_id, expires_at)
        refresh_token = create_refresh_token()
        auth_session = await self.sessions.create(
            session_id=session_id,
            user_id=user.id,
            token=token,
            token_jti=token_jti,
            refresh_token=refresh_token,
            expires_at=expires_at,
            refresh_expires_at=refresh_expires_at,
            fingerprint=payload.fingerprint if payload else None,
            user_agent=request.headers.get("user-agent"),
            session_source=payload.session_source if payload else None,
            device_type=payload.device_type if payload else None,
            os_name=payload.os_name if payload else None,
            os_version=payload.os_version if payload else None,
            browser_name=payload.browser_name if payload else None,
            browser_version=payload.browser_version if payload else None,
            ip_address=_client_ip(request),
            metadata=_session_metadata(payload, request),
        )
        return TokenResponse(
            access_token=token,
            refresh_token=refresh_token,
            session_id=auth_session.id,
            expires_at=expires_at.isoformat(),
            refresh_expires_at=refresh_expires_at.isoformat(),
        )


def _client_ip(request: Request) -> str | None:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip
    return request.client.host if request.client else None


def _session_metadata(payload: LoginRequest | None, request: Request) -> dict:
    metadata = dict(payload.metadata) if payload else {}
    metadata["accept_language"] = request.headers.get("accept-language")
    metadata["origin"] = request.headers.get("origin")
    metadata["referer"] = request.headers.get("referer")
    return {key: value for key, value in metadata.items() if value is not None}
