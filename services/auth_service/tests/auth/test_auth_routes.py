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


@pytest.mark.anyio
async def test_register_happy_case(client: AsyncClient, asyncpg_url: str) -> None:
    email = "integration@example.com"

    response = await client.post(
        "/auth/register",
        json={
            "email": email,
            "full_name": "Test User",
            "password": "password123",
        },
        headers={"user-agent": "pytest"},
    )

    assert response.status_code == 201

    body = response.json()
    payload = body["payload"]

    access_token = payload.pop("access_token")
    refresh_token = payload.pop("refresh_token")
    session_id = payload.pop("session_id")
    response_expires_at = payload.pop("expires_at")
    response_refresh_expires_at = payload.pop("refresh_expires_at")

    assert isinstance(access_token, str) and len(access_token) > 0
    assert isinstance(refresh_token, str) and len(refresh_token) > 0
    assert isinstance(session_id, str) and len(session_id) > 0
    assert isinstance(response_expires_at, str) and len(response_expires_at) > 0
    assert isinstance(response_refresh_expires_at, str) and len(response_refresh_expires_at) > 0

    assert response.cookies.get("access_token") == access_token
    assert response.cookies.get("refresh_token") == refresh_token

    assert body == {
        "success": True,
        "payload": {
            "token_type": "bearer",
        },
    }

    conn = await asyncpg.connect(asyncpg_url)
    try:
        users = await conn.fetch("SELECT * FROM users WHERE email = $1", email)
        assert len(users) == 1
        user = dict(users[0])

        user_roles = await conn.fetch("SELECT * FROM user_roles WHERE user_id = $1", user["id"])
        assert len(user_roles) == 1
        user_role = dict(user_roles[0])

        role = dict(await conn.fetchrow("SELECT * FROM roles WHERE id = $1", user_role["role_id"]))
        auth_session = dict(
            await conn.fetchrow("SELECT * FROM auth_sessions WHERE user_id = $1", user["id"])
        )
    finally:
        await conn.close()

    user_id = user.pop("id")
    hashed_password = user.pop("hashed_password")
    created_at = user.pop("created_at")

    assert isinstance(hashed_password, str) and len(hashed_password) > 0
    assert hashed_password != "password123"
    assert created_at is not None

    assert user == {
        "email": email,
        "full_name": "Test User",
        "is_active": True,
    }

    role_id = role.pop("id")
    role_created_at = role.pop("created_at")

    assert role_created_at is not None

    assert user_role == {
        "user_id": user_id,
        "role_id": role_id,
    }

    assert role == {
        "code": "CUSTOMER",
        "title": "Customer",
        "weight": 40,
    }

    auth_session_id = auth_session.pop("id")
    auth_session_user_id = auth_session.pop("user_id")
    token_jti = auth_session.pop("token_jti")
    token_hash = auth_session.pop("token_hash")
    refresh_token_hash = auth_session.pop("refresh_token_hash")
    ip_address = auth_session.pop("ip_address")
    session_expires_at = auth_session.pop("expires_at")
    session_refresh_expires_at = auth_session.pop("refresh_expires_at")
    auth_session_created_at = auth_session.pop("created_at")

    assert str(auth_session_id) == session_id
    assert auth_session_user_id == user_id
    assert isinstance(token_jti, str) and len(token_jti) > 0
    assert isinstance(token_hash, str) and len(token_hash) > 0
    assert isinstance(refresh_token_hash, str) and len(refresh_token_hash) > 0
    assert isinstance(ip_address, str) and len(ip_address) > 0
    assert session_expires_at is not None
    assert session_refresh_expires_at is not None
    assert auth_session_created_at is not None

    assert auth_session == {
        "fingerprint": None,
        "user_agent": "pytest",
        "session_source": None,
        "device_type": None,
        "os_name": None,
        "os_version": None,
        "browser_name": None,
        "browser_version": None,
        "metadata": "{}",
        "revoked_at": None,
    }

async def truncate_tables(asyncpg_url: str) -> None:
    table_names = ", ".join(
        f'"{table.name}"' for table in Base.metadata.sorted_tables if table.name != "roles"
    )

    conn = await asyncpg.connect(asyncpg_url)
    try:
        await conn.execute(f"TRUNCATE {table_names} RESTART IDENTITY CASCADE")
    finally:
        await conn.close()
