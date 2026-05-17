from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.modules.roles.service import RoleService
from app.modules.users.models import User


class AuthBootstrapService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.roles = RoleService(session)

    async def bootstrap(self) -> None:
        await self.roles.ensure_default_roles()

        result = await self.session.execute(select(func.count(User.id)))
        users_count = result.scalar_one()
        if users_count > 0:
            return

        superadmin_role = await self.roles.get_by_code("SUPERADMIN")
        user = User(
            email="admin@gmail.com",
            full_name="System Administrator",
            hashed_password=hash_password("admin123"),
            roles=[superadmin_role] if superadmin_role else [],
        )
        self.session.add(user)
        await self.session.commit()
