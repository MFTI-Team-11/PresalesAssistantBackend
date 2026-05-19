from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.auth.dependencies import get_current_user, require_roles
from app.modules.roles.schemas import RoleCreate, RoleRead
from app.modules.roles.service import RoleService
from app.modules.users.models import User
from app.modules.users.routes import serialize_user
from shared.responses import success_response

router = APIRouter(prefix="/roles", tags=["roles"])


@router.get("")
async def list_roles(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    roles = await RoleService(session).list_roles()
    return success_response([RoleRead.model_validate(role).model_dump(mode="json") for role in roles])


@router.post("", status_code=201)
async def create_role(
    data: RoleCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    role = await RoleService(session).create(data)
    return success_response(RoleRead.model_validate(role).model_dump(mode="json"))


@router.post("/{role_id}/users/{user_id}")
async def assign_role(
    role_id: UUID,
    user_id: UUID,
    current_user: Annotated[User, Depends(require_roles(["SUPERADMIN", "MANAGER"]))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    user = await RoleService(session).assign_role(user_id, role_id)
    return success_response(serialize_user(user))


@router.delete("/{role_id}/users/{user_id}")
async def delete_role_from_user(
    role_id: UUID,
    user_id: UUID,
    current_user: Annotated[User, Depends(require_roles(["SUPERADMIN"]))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    user = await RoleService(session).delete_role_from_user(user_id, role_id)
    return success_response(serialize_user(user))
