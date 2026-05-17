from fastapi import APIRouter

from app.modules.auth.routes import router as auth_router
from app.modules.roles.routes import router as roles_router
from app.modules.sessions.routes import router as sessions_router
from app.modules.users.routes import router as users_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(users_router)
router.include_router(roles_router)
router.include_router(sessions_router)
