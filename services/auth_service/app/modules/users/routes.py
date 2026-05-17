from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.users.schemas import UserRead
from app.modules.users.service import UserService
from shared.responses import success_response

router = APIRouter(prefix="/users", tags=["users"])


def serialize_user(user) -> dict:
    data = UserRead.model_validate(user).model_dump(mode="json")
    data["roles"] = [role.code for role in user.roles]
    return data


@router.get("")
async def list_users(session: Annotated[AsyncSession, Depends(get_session)]):
    users = await UserService(session).list_users()
    return success_response([serialize_user(user) for user in users])


@router.get("/{user_id}")
async def get_user(user_id: UUID, session: Annotated[AsyncSession, Depends(get_session)]):
    user = await UserService(session).get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return success_response(serialize_user(user))
