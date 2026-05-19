from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.users.models import User


class UserService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.execute(
            select(User).where(User.email == email.lower()).options(selectinload(User.roles))
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: UUID) -> User | None:
        result = await self.session.execute(
            select(User).where(User.id == user_id).options(selectinload(User.roles))
        )
        return result.scalar_one_or_none()

    async def list_users(self) -> list[User]:
        result = await self.session.execute(select(User).options(selectinload(User.roles)))
        return list(result.scalars().all())

    async def update_self(
        self,
        current_user: User,
        full_name: str,
    ) -> User:
        current_user.full_name = full_name

        await self.session.commit()
        await self.session.refresh(current_user, attribute_names=["roles"])
        return current_user

    async def update_by_admin(
        self,
        user_id: UUID,
        current_user: User,
        full_name: str | None = None,
        is_active: bool | None = None,
    ) -> User:
        user = await self.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        if _has_role(user, ["SUPERADMIN"]) and not _has_role(current_user, ["SUPERADMIN"]):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only SUPERADMIN can update SUPERADMIN users",
            )

        if full_name is not None:
            user.full_name = full_name

        if is_active is not None:
            user.is_active = is_active

        await self.session.commit()
        await self.session.refresh(user, attribute_names=["roles"])
        return user


def _has_role(user: User, allowed_roles: list[str]) -> bool:
    allowed = {role.upper() for role in allowed_roles}
    user_roles = {role.code.upper() for role in user.roles}

    return not user_roles.isdisjoint(allowed)
