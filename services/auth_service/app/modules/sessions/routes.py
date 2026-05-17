from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.auth.dependencies import get_current_user
from app.modules.sessions.schemas import SessionRead
from app.modules.sessions.service import SessionService
from app.modules.users.models import User
from shared.responses import success_response

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("")
async def list_my_sessions(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    sessions = await SessionService(session).list_for_user(current_user.id)
    return success_response([SessionRead.model_validate(item).model_dump(mode="json") for item in sessions])


@router.delete("/{session_id}")
async def revoke_session(
    session_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    auth_session = await SessionService(session).revoke(session_id, current_user.id)
    return success_response(SessionRead.model_validate(auth_session).model_dump(mode="json"))
