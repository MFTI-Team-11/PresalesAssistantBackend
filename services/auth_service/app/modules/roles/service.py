from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import BASE_ROLES
from app.modules.roles.models import Role
from app.modules.roles.schemas import RoleCreate
from app.modules.users.models import User
from app.modules.users.service import UserService


class RoleService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def ensure_default_roles(self) -> None:
        for code, weight in BASE_ROLES:
            if not await self.get_by_code(code):
                self.session.add(Role(code=code, title=code.title(), weight=weight))
        await self.session.commit()

    async def get_by_code(self, code: str) -> Role | None:
        result = await self.session.execute(select(Role).where(Role.code == code.upper()))
        return result.scalar_one_or_none()

    async def get_by_id(self, role_id: UUID) -> Role | None:
        result = await self.session.execute(select(Role).where(Role.id == role_id))
        return result.scalar_one_or_none()

    async def create(self, data: RoleCreate) -> Role:
        if await self.get_by_code(data.code):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Role already exists")
        role = Role(code=data.code.upper(), title=data.title, weight=data.weight)
        self.session.add(role)
        await self.session.commit()
        await self.session.refresh(role)
        return role

    async def list_roles(self) -> list[Role]:
        result = await self.session.execute(select(Role).order_by(Role.code))
        return list(result.scalars().all())

    async def assign_role(self, user_id: UUID, role_id: UUID) -> User:
        user = await UserService(self.session).get_by_id(user_id)
        role = await self.get_by_id(role_id)
        if not user or not role:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User or role not found")
        if role not in user.roles:
            user.roles.append(role)
            await self.session.commit()
        return user

    async def delete_role_from_user(self, user_id: UUID, role_id: UUID) -> User:
        user = await UserService(self.session).get_by_id(user_id)
        role = await self.get_by_id(role_id)
        if not user or not role:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User or role not found")

        if role in user.roles:
            user.roles.remove(role)
            await self.session.commit()

        await self.session.refresh(user, attribute_names=["roles"])
        return user
