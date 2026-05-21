from collections.abc import AsyncGenerator
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app import routes


class FakeSession:
    def __init__(self) -> None:
        self.items: list[Any] = []

    def add(self, item: Any) -> None:
        self.items.append(item)

    async def commit(self) -> None:
        return None


@pytest.fixture()
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture()
async def client() -> AsyncGenerator[AsyncClient, None]:
    async def override_get_session() -> AsyncGenerator[Any, None]:
        yield FakeSession()

    app = FastAPI()
    app.dependency_overrides[routes.get_session] = override_get_session
    app.include_router(routes.router)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as test_client:
        yield test_client

    app.dependency_overrides.clear()
