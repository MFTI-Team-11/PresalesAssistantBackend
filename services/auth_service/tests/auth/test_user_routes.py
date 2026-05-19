from uuid import uuid4

import asyncpg
import pytest
from httpx import AsyncClient

from app.core.security import hash_password


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
        admin_user_id = await conn.fetchval(
            "SELECT id FROM users WHERE email = $1",
            "admin@gmail.com",
        )
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
        admin_user_id = await conn.fetchval(
            "SELECT id FROM users WHERE email = $1",
            "admin@gmail.com",
        )
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
        admin_user_id = await conn.fetchval(
            "SELECT id FROM users WHERE email = $1",
            "admin@gmail.com",
        )
    finally:
        await conn.close()

    response = await client.get(f"/users/{admin_user_id}")

    assert response.status_code == 403
    assert response.json() == {"detail": "Required roles: SUPERADMIN"}


@pytest.mark.anyio
async def test_update_user_full_name_happy_case_for_customer(
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
        user_id = await conn.fetchval("SELECT id FROM users WHERE email = $1", "test@example.com")
    finally:
        await conn.close()

    response = await client.patch("/users/me", json={"full_name": "Updated User"})

    assert response.status_code == 200

    body = response.json()
    roles = body["payload"].pop("roles")

    assert roles == ["CUSTOMER"]
    assert body == {
        "success": True,
        "payload": {
            "id": str(user_id),
            "email": "test@example.com",
            "full_name": "Updated User",
            "is_active": True,
        },
    }

    conn = await asyncpg.connect(asyncpg_url)
    try:
        full_name = await conn.fetchval("SELECT full_name FROM users WHERE id = $1", user_id)
    finally:
        await conn.close()

    assert full_name == "Updated User"


@pytest.mark.anyio
async def test_update_user_is_active_happy_case_for_superadmin(
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
        user_id = uuid4()
        await conn.execute(
            """
            INSERT INTO users (id, email, full_name, hashed_password, is_active)
            VALUES ($1, $2, $3, $4, $5)
            """,
            user_id, "test@example.com", "Test User", hash_password("password123"), True,
        )
    finally:
        await conn.close()

    response = await client.patch(
        f"/users/{user_id}",
        json={"is_active": False},
    )

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "payload": {
            "id": str(user_id),
            "email": "test@example.com",
            "full_name": "Test User",
            "is_active": False,
            "roles": [],
        },
    }

    conn = await asyncpg.connect(asyncpg_url)
    try:
        is_active = await conn.fetchval("SELECT is_active FROM users WHERE id = $1", user_id)
    finally:
        await conn.close()

    assert is_active is False


@pytest.mark.anyio
async def test_update_other_user_full_name_returns_forbidden_for_customer(
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
        admin_user_id = await conn.fetchval(
            "SELECT id FROM users WHERE email = $1",
            "admin@gmail.com",
        )
    finally:
        await conn.close()

    response = await client.patch(
        f"/users/{admin_user_id}",
        json={"full_name": "Updated Admin"},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Required roles: MANAGER, SUPERADMIN"}

    conn = await asyncpg.connect(asyncpg_url)
    try:
        full_name = await conn.fetchval("SELECT full_name FROM users WHERE id = $1", admin_user_id)
    finally:
        await conn.close()

    assert full_name == "System Administrator"


@pytest.mark.anyio
async def test_update_user_happy_case_for_manager(
    client: AsyncClient,
    asyncpg_url: str,
) -> None:
    conn = await asyncpg.connect(asyncpg_url)
    try:
        manager_role_id = await conn.fetchval("SELECT id FROM roles WHERE code = $1", "MANAGER")
        manager_user_id = uuid4()
        await conn.execute(
            """
            INSERT INTO users (id, email, full_name, hashed_password, is_active)
            VALUES ($1, $2, $3, $4, $5)
            """,
            manager_user_id, "manager@example.com", "Manager User", hash_password("password123"), True,
        )
        target_user_id = uuid4()
        await conn.execute(
            """
            INSERT INTO users (id, email, full_name, hashed_password, is_active)
            VALUES ($1, $2, $3, $4, $5)
            """,
            target_user_id, "test@example.com", "Test User", hash_password("password123"), True,
        )

        await conn.execute(
            "INSERT INTO user_roles (user_id, role_id) VALUES ($1, $2)",
            manager_user_id, manager_role_id,
        )
    finally:
        await conn.close()

    login_response = await client.post(
        "/auth/login",
        json={
            "email": "manager@example.com",
            "password": "password123",
            "fingerprint": "test-fingerprint",
        },
    )

    assert login_response.status_code == 200

    response = await client.patch(
        f"/users/{target_user_id}",
        json={
            "full_name": "Updated User",
            "is_active": False,
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "payload": {
            "id": str(target_user_id),
            "email": "test@example.com",
            "full_name": "Updated User",
            "is_active": False,
            "roles": [],
        },
    }


@pytest.mark.anyio
async def test_update_superadmin_returns_forbidden_for_manager(
    client: AsyncClient,
    asyncpg_url: str,
) -> None:
    conn = await asyncpg.connect(asyncpg_url)
    try:
        manager_role_id = await conn.fetchval("SELECT id FROM roles WHERE code = $1", "MANAGER")
        manager_user_id = uuid4()
        await conn.execute(
            """
            INSERT INTO users (id, email, full_name, hashed_password, is_active)
            VALUES ($1, $2, $3, $4, $5)
            """,
            manager_user_id, "manager@example.com", "Manager User", hash_password("password123"), True,
        )
        admin_user_id = await conn.fetchval(
            "SELECT id FROM users WHERE email = $1",
            "admin@gmail.com",
        )

        await conn.execute(
            "INSERT INTO user_roles (user_id, role_id) VALUES ($1, $2)",
            manager_user_id,
            manager_role_id,
        )
    finally:
        await conn.close()

    login_response = await client.post(
        "/auth/login",
        json={
            "email": "manager@example.com",
            "password": "password123",
            "fingerprint": "test-fingerprint",
        },
    )

    assert login_response.status_code == 200

    response = await client.patch(
        f"/users/{admin_user_id}",
        json={"full_name": "Updated Admin"},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Only SUPERADMIN can update SUPERADMIN users"}

    conn = await asyncpg.connect(asyncpg_url)
    try:
        full_name = await conn.fetchval("SELECT full_name FROM users WHERE id = $1", admin_user_id)
    finally:
        await conn.close()

    assert full_name == "System Administrator"


@pytest.mark.anyio
async def test_update_superadmin_happy_case_for_superadmin(
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
        admin_user_id = await conn.fetchval(
            "SELECT id FROM users WHERE email = $1",
            "admin@gmail.com",
        )
    finally:
        await conn.close()

    response = await client.patch(
        f"/users/{admin_user_id}",
        json={"full_name": "Updated Admin"},
    )

    assert response.status_code == 200

    body = response.json()
    roles = body["payload"].pop("roles")

    assert roles == ["SUPERADMIN"]
    assert body == {
        "success": True,
        "payload": {
            "id": str(admin_user_id),
            "email": "admin@gmail.com",
            "full_name": "Updated Admin",
            "is_active": True,
        },
    }
