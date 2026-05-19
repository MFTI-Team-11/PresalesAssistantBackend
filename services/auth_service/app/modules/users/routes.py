from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.auth.dependencies import get_current_user, require_roles
from app.modules.users.models import User
from app.modules.users.schemas import UserAdminUpdate, UserRead, UserSelfUpdate
from app.modules.users.service import UserService
from shared.responses import success_response

router = APIRouter(prefix="/users", tags=["users"])


def serialize_user(user) -> dict:
    data = UserRead.model_validate(user).model_dump(mode="json")
    data["roles"] = [role.code for role in user.roles]
    return data


@router.get("")
async def list_users(
    current_user: Annotated[User, Depends(require_roles(["SUPERADMIN"]))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    users = await UserService(session).list_users()
    return success_response([serialize_user(user) for user in users])


@router.get("/{user_id}")
async def get_user(
    user_id: UUID,
    current_user: Annotated[User, Depends(require_roles(["SUPERADMIN"]))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    user = await UserService(session).get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return success_response(serialize_user(user))


@router.patch("/me")
async def update_current_user(
    data: UserSelfUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    updated_user = await UserService(session).update_self(
        current_user,
        full_name=data.full_name,
    )
    return success_response(serialize_user(updated_user))


@router.patch("/{user_id}")
async def update_user_by_admin(
    user_id: UUID,
    data: UserAdminUpdate,
    current_user: Annotated[User, Depends(require_roles(["SUPERADMIN", "MANAGER"]))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    updated_user = await UserService(session).update_by_admin(
        user_id,
        current_user,
        full_name=data.full_name,
        is_active=data.is_active,
    )
    return success_response(serialize_user(updated_user))
