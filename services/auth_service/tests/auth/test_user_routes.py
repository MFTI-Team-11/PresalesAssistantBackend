import asyncpg
import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_list_users_happy_case_for_superadmin(
    client: AsyncClient,
    asyncpg_url: str,
) -> None:
    login_response = await client.post(
        "/auth/login",
        json={
            "email": "admin@gmail.com",
            "password": "admin123",
            "fingerprint": "test-fingerprint",
        },
    )

    assert login_response.status_code == 200

    conn = await asyncpg.connect(asyncpg_url)
    try:
        admin_user_id = await conn.fetchval("SELECT id FROM users WHERE email = $1", "admin@gmail.com")
    finally:
        await conn.close()

    response = await client.get("/users")

    assert response.status_code == 200

    body = response.json()
    roles = body["payload"][0].pop("roles")

    assert roles == ["SUPERADMIN"]
    assert body == {
        "success": True,
        "payload": [
            {
                "id": str(admin_user_id),
                "email": "admin@gmail.com",
                "full_name": "System Administrator",
                "is_active": True,
            }
        ],
    }


@pytest.mark.anyio
async def test_get_user_happy_case_for_superadmin(
    client: AsyncClient,
    asyncpg_url: str,
) -> None:
    login_response = await client.post(
        "/auth/login",
        json={
            "email": "admin@gmail.com",
            "password": "admin123",
            "fingerprint": "test-fingerprint",
        },
    )

    assert login_response.status_code == 200

    conn = await asyncpg.connect(asyncpg_url)
    try:
        admin_user_id = await conn.fetchval("SELECT id FROM users WHERE email = $1", "admin@gmail.com")
    finally:
        await conn.close()

    response = await client.get(f"/users/{admin_user_id}")

    assert response.status_code == 200

    body = response.json()
    roles = body["payload"].pop("roles")

    assert roles == ["SUPERADMIN"]
    assert body == {
        "success": True,
        "payload": {
            "id": str(admin_user_id),
            "email": "admin@gmail.com",
            "full_name": "System Administrator",
            "is_active": True,
        },
    }


@pytest.mark.anyio
async def test_list_users_returns_forbidden_for_non_superadmin(
    client: AsyncClient,
) -> None:
    register_response = await client.post(
        "/auth/register",
        json={
            "email": "test@example.com",
            "full_name": "Test User",
            "password": "password123",
        },
    )

    assert register_response.status_code == 201

    response = await client.get("/users")

    assert response.status_code == 403
    assert response.json() == {"detail": "Required roles: SUPERADMIN"}


@pytest.mark.anyio
async def test_get_user_returns_forbidden_for_non_superadmin(
    client: AsyncClient,
    asyncpg_url: str,
) -> None:
    register_response = await client.post(
        "/auth/register",
        json={
            "email": "test@example.com",
            "full_name": "Test User",
            "password": "password123",
        },
    )

    assert register_response.status_code == 201

    conn = await asyncpg.connect(asyncpg_url)
    try:
        admin_user_id = await conn.fetchval("SELECT id FROM users WHERE email = $1", "admin@gmail.com")
    finally:
        await conn.close()

    response = await client.get(f"/users/{admin_user_id}")

    assert response.status_code == 403
    assert response.json() == {"detail": "Required roles: SUPERADMIN"}
