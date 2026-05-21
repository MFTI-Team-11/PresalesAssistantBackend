from uuid import uuid4

import asyncpg
import pytest
from httpx import AsyncClient

from app.core.security import hash_password


@pytest.mark.anyio
async def test_assign_role_to_user_happy_case(client: AsyncClient, asyncpg_url: str) -> None:
    target_email = "test@example.com"
    target_user_id = uuid4()

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
        manager_role_id = await conn.fetchval("SELECT id FROM roles WHERE code = $1", "MANAGER")
        superadmin_role_id = await conn.fetchval(
            "SELECT id FROM roles WHERE code = $1",
            "SUPERADMIN",
        )

        await conn.execute(
            """
            INSERT INTO users (id, email, full_name, hashed_password, is_active)
            VALUES ($1, $2, $3, $4, $5)
            """,
            target_user_id,
            target_email,
            "Assign Role Target",
            hash_password("password123"),
            True,
        )

        await conn.execute(
            """
            INSERT INTO user_roles (user_id, role_id)
            VALUES ($1, $2)
            """,
            target_user_id,
            manager_role_id,
        )
    finally:
        await conn.close()

    response = await client.post(f"/roles/{superadmin_role_id}/users/{target_user_id}")

    assert response.status_code == 200

    body = response.json()
    roles = body["payload"].pop("roles")

    assert sorted(roles) == ["MANAGER", "SUPERADMIN"]
    assert body == {
        "success": True,
        "payload": {
            "id": str(target_user_id),
            "email": target_email,
            "full_name": "Assign Role Target",
            "is_active": True,
        },
    }

    conn = await asyncpg.connect(asyncpg_url)
    try:
        assigned_role_codes = await conn.fetch(
            """
            SELECT roles.code
            FROM roles
            JOIN user_roles ON user_roles.role_id = roles.id
            WHERE user_roles.user_id = $1
            ORDER BY roles.weight
            """,
            target_user_id,
        )
    finally:
        await conn.close()

    assert [role["code"] for role in assigned_role_codes] == ["MANAGER", "SUPERADMIN"]


@pytest.mark.anyio
async def test_delete_role_from_user_happy_case(client: AsyncClient, asyncpg_url: str) -> None:
    target_email = "delete-role-target@example.com"
    target_user_id = uuid4()

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
        manager_role_id = await conn.fetchval("SELECT id FROM roles WHERE code = $1", "MANAGER")
        superadmin_role_id = await conn.fetchval("SELECT id FROM roles WHERE code = $1", "SUPERADMIN")

        await conn.execute(
            """
            INSERT INTO users (id, email, full_name, hashed_password, is_active)
            VALUES ($1, $2, $3, $4, $5)
            """,
            target_user_id,
            target_email,
            "Delete Role Target",
            hash_password("password123"),
            True,
        )

        await conn.execute(
            """
            INSERT INTO user_roles (user_id, role_id)
            VALUES ($1, $2), ($1, $3)
            """,
            target_user_id,
            manager_role_id,
            superadmin_role_id,
        )
    finally:
        await conn.close()

    response = await client.delete(f"/roles/{manager_role_id}/users/{target_user_id}")

    assert response.status_code == 200

    body = response.json()
    roles = body["payload"].pop("roles")

    assert roles == ["SUPERADMIN"]
    assert body == {
        "success": True,
        "payload": {
            "id": str(target_user_id),
            "email": target_email,
            "full_name": "Delete Role Target",
            "is_active": True,
        },
    }

    conn = await asyncpg.connect(asyncpg_url)
    try:
        assigned_role_codes = await conn.fetch(
            """
            SELECT roles.code
            FROM roles
            JOIN user_roles ON user_roles.role_id = roles.id
            WHERE user_roles.user_id = $1
            ORDER BY roles.weight
            """,
            target_user_id,
        )
    finally:
        await conn.close()

    assert [role["code"] for role in assigned_role_codes] == ["SUPERADMIN"]

@pytest.mark.anyio
async def test_delete_role_from_user_requires_superadmin(
    client: AsyncClient,
    asyncpg_url: str,
) -> None:
    manager_email = "manager@example.com"
    manager_user_id = uuid4()
    target_user_id = uuid4()

    conn = await asyncpg.connect(asyncpg_url)
    try:
        manager_role_id = await conn.fetchval("SELECT id FROM roles WHERE code = $1", "MANAGER")

        await conn.execute(
            """
            INSERT INTO users (id, email, full_name, hashed_password, is_active)
            VALUES ($1, $2, $3, $4, $5)
            """,
            manager_user_id,
            manager_email,
            "Manager User",
            hash_password("password123"),
            True,
        )

        await conn.execute(
            """
            INSERT INTO user_roles (user_id, role_id)
            VALUES ($1, $2)
            """,
            manager_user_id,
            manager_role_id,
        )
    finally:
        await conn.close()

    login_response = await client.post(
        "/auth/login",
        json={
            "email": manager_email,
            "password": "password123",
            "fingerprint": "test-fingerprint",
        },
    )

    assert login_response.status_code == 200

    response = await client.delete(f"/roles/{manager_role_id}/users/{target_user_id}")

    assert response.status_code == 403


@pytest.mark.anyio
async def test_delete_role_from_user_is_idempotent(client: AsyncClient, asyncpg_url: str) -> None:
    target_email = "delete-role-idempotent-target@example.com"
    target_user_id = uuid4()

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
        manager_role_id = await conn.fetchval("SELECT id FROM roles WHERE code = $1", "MANAGER")
        superadmin_role_id = await conn.fetchval(
            "SELECT id FROM roles WHERE code = $1",
            "SUPERADMIN",
        )

        await conn.execute(
            """
            INSERT INTO users (id, email, full_name, hashed_password, is_active)
            VALUES ($1, $2, $3, $4, $5)
            """,
            target_user_id,
            target_email,
            "Delete Role Idempotent Target",
            hash_password("password123"),
            True,
        )

        await conn.execute(
            """
            INSERT INTO user_roles (user_id, role_id)
            VALUES ($1, $2)
            """,
            target_user_id,
            superadmin_role_id,
        )
    finally:
        await conn.close()

    response = await client.delete(f"/roles/{manager_role_id}/users/{target_user_id}")

    assert response.status_code == 200
    assert response.json()["payload"]["roles"] == ["SUPERADMIN"]
