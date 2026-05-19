import asyncio
from collections.abc import AsyncGenerator, Generator
from typing import Any

import asyncpg
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from testcontainers.postgres import PostgresContainer

from app.db.session import Base
from app.modules.auth import routes as auth_routes


@pytest.fixture()
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(scope="session")
def postgres_url() -> Generator[str, None, None]:
    with PostgresContainer("postgres:16-alpine", driver="asyncpg") as postgres:
        yield postgres.get_connection_url()


@pytest.fixture(scope="session")
def asyncpg_url(postgres_url: str) -> str:
    return postgres_url.replace("postgresql+asyncpg://", "postgresql://")


@pytest.fixture(scope="session")
def db_sessionmaker(postgres_url: str) -> Generator[Any, None, None]:
    setup_engine = create_async_engine(postgres_url)

    async def create_tables() -> None:
        async with setup_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(create_tables())
    asyncio.run(setup_engine.dispose())

    engine = create_async_engine(postgres_url, poolclass=NullPool)
    yield async_sessionmaker(engine, expire_on_commit=False)
    asyncio.run(engine.dispose())


@pytest.fixture(autouse=True)
async def clean_db(asyncpg_url: str) -> None:
    await truncate_tables(asyncpg_url)


@pytest.fixture()
async def client(db_sessionmaker: Any) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_session() -> AsyncGenerator[Any, None]:
        async with db_sessionmaker() as session:
            yield session

    app = FastAPI()
    app.dependency_overrides[auth_routes.get_session] = override_get_session
    app.include_router(auth_routes.router)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as test_client:
        yield test_client

    app.dependency_overrides.clear()


async def truncate_tables(asyncpg_url: str) -> None:
    table_names = ", ".join(
        f'"{table.name}"' for table in Base.metadata.sorted_tables if table.name != "roles"
    )

    conn = await asyncpg.connect(asyncpg_url)
    try:
        await conn.execute(f"TRUNCATE {table_names} RESTART IDENTITY CASCADE")
    finally:
        await conn.close()
