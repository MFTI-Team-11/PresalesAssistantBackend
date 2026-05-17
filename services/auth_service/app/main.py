from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import router
from app.core.config import settings
from app.db.session import AsyncSessionLocal, Base, engine
from app.modules.auth.bootstrap import AuthBootstrapService
from shared.docs import install_docs
from shared.responses import install_response_handlers, success_response


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.auto_create_tables:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as session:
        await AuthBootstrapService(session).bootstrap()
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan, docs_url=None)
install_docs(app, settings.app_name)
install_response_handlers(app)
app.include_router(router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return success_response({"service": "auth_service", "status": "ok"})
