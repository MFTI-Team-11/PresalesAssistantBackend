from fastapi import FastAPI

from app.routes import router
from app.core.config import settings
from shared.docs import install_docs
from shared.responses import install_response_handlers, success_response


app = FastAPI(title=settings.app_name, version="0.1.0", docs_url=None)
install_docs(app, settings.app_name)
install_response_handlers(app)
app.include_router(router)


@app.get("/health")
async def health_check() -> dict:
    return success_response({"service": "ai_service", "status": "ok"})
