from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_token
from app.modules.sessions.models import AuthSession


class SessionService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        session_id: UUID,
        user_id: UUID,
        token: str,
        token_jti: str,
        refresh_token: str,
        expires_at: datetime,
        refresh_expires_at: datetime,
        ip_address: str | None,
        fingerprint: str | None,
        user_agent: str | None,
        session_source: str | None,
        device_type: str | None,
        os_name: str | None,
        os_version: str | None,
        browser_name: str | None,
        browser_version: str | None,
        metadata: dict,
    ) -> AuthSession:
        auth_session = AuthSession(
            id=session_id,
            user_id=user_id,
            token_jti=token_jti,
            token_hash=hash_token(token),
            refresh_token_hash=hash_token(refresh_token),
            expires_at=expires_at,
            refresh_expires_at=refresh_expires_at,
            ip_address=ip_address,
            fingerprint=fingerprint,
            user_agent=user_agent,
            session_source=session_source,
            device_type=device_type,
            os_name=os_name,
            os_version=os_version,
            browser_name=browser_name,
            browser_version=browser_version,
            session_metadata=metadata,
        )
        self.session.add(auth_session)
        await self.session.commit()
        await self.session.refresh(auth_session)
        return auth_session

    async def validate_refresh_token(self, refresh_token: str) -> AuthSession:
        result = await self.session.execute(
            select(AuthSession).where(AuthSession.refresh_token_hash == hash_token(refresh_token))
        )
        auth_session = result.scalar_one_or_none()
        if (
            not auth_session
            or auth_session.revoked_at is not None
            or auth_session.refresh_expires_at <= datetime.now(UTC)
        ):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token is not active")
        return auth_session

    async def rotate_tokens(
        self,
        auth_session: AuthSession,
        access_token: str,
        token_jti: str,
        refresh_token: str,
        expires_at: datetime,
        refresh_expires_at: datetime,
    ) -> AuthSession:
        auth_session.token_jti = token_jti
        auth_session.token_hash = hash_token(access_token)
        auth_session.refresh_token_hash = hash_token(refresh_token)
        auth_session.expires_at = expires_at
        auth_session.refresh_expires_at = refresh_expires_at
        await self.session.commit()
        await self.session.refresh(auth_session)
        return auth_session

    async def list_for_user(self, user_id: UUID) -> list[AuthSession]:
        result = await self.session.execute(
            select(AuthSession)
            .where(AuthSession.user_id == user_id)
            .order_by(AuthSession.created_at.desc())
        )
        return list(result.scalars().all())

    async def revoke(self, session_id: UUID, user_id: UUID | None = None) -> AuthSession:
        query = select(AuthSession).where(AuthSession.id == session_id)
        if user_id:
            query = query.where(AuthSession.user_id == user_id)
        result = await self.session.execute(query)
        auth_session = result.scalar_one_or_none()
        if not auth_session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
        auth_session.revoked_at = datetime.now(UTC)
        await self.session.commit()
        await self.session.refresh(auth_session)
        return auth_session

    async def validate_token(self, token: str, token_jti: str) -> AuthSession:
        result = await self.session.execute(
            select(AuthSession).where(
                AuthSession.token_jti == token_jti,
                AuthSession.token_hash == hash_token(token),
            )
        )
        auth_session = result.scalar_one_or_none()
        if (
            not auth_session
            or auth_session.revoked_at is not None
            or auth_session.expires_at <= datetime.now(UTC)
        ):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session is not active")
        return auth_session
