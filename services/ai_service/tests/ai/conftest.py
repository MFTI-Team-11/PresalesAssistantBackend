from collections.abc import AsyncGenerator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app import routes


@pytest.fixture()
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture()
async def client() -> AsyncGenerator[AsyncClient, None]:
    app = FastAPI()
    app.include_router(routes.router)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as test_client:
        yield test_client
