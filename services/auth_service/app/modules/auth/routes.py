from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import decode_access_token
from app.db.session import get_session
from app.modules.auth.dependencies import get_current_user, oauth2_scheme
from app.modules.auth.schemas import LoginRequest, RegisterRequest
from app.modules.auth.service import AuthService
from app.modules.sessions.service import SessionService
from app.modules.users.models import User
from app.modules.users.routes import serialize_user
from shared.responses import success_response

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=201)
async def register(
    data: RegisterRequest,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    token = await AuthService(session).register(data, request)
    set_auth_cookies(response, token)
    return success_response(token.model_dump(mode="json"))


@router.post("/login")
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    token = await AuthService(session).login(payload, request)
    set_auth_cookies(response, token)
    return success_response(token.model_dump(mode="json"))


@router.post("/refresh")
async def refresh(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    refresh_token = request.cookies.get(settings.refresh_cookie_name)
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token cookie is missing")
    token = await AuthService(session).refresh(refresh_token)
    set_auth_cookies(response, token)
    return success_response(token.model_dump(mode="json"))


@router.get("/me")
async def me(current_user: Annotated[User, Depends(get_current_user)]):
    return success_response(serialize_user(current_user))


@router.post("/logout")
async def logout(
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
    bearer_token: Annotated[str | None, Depends(oauth2_scheme)] = None,
):
    token = bearer_token or request.cookies.get(settings.access_cookie_name)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Access token is missing")
    payload = decode_access_token(token)
    await SessionService(session).revoke(UUID(payload["sid"]), current_user.id)
    clear_auth_cookies(response)
    return success_response({})


def set_auth_cookies(response: Response, token) -> None:
    response.set_cookie(
        key=settings.access_cookie_name,
        value=token.access_token,
        max_age=settings.access_token_expire_minutes * 60,
        httponly=settings.cookie_httponly,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        domain=settings.cookie_domain,
        path=settings.cookie_path,
    )
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=token.refresh_token,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        httponly=settings.cookie_httponly,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        domain=settings.cookie_domain,
        path=settings.cookie_path,
    )


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(
        key=settings.access_cookie_name,
        domain=settings.cookie_domain,
        path=settings.cookie_path,
    )
    response.delete_cookie(
        key=settings.refresh_cookie_name,
        domain=settings.cookie_domain,
        path=settings.cookie_path,
    )
