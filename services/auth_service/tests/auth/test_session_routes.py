import asyncpg
import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_list_my_sessions_happy_case(client: AsyncClient, asyncpg_url: str) -> None:
    email = "test@example.com"

    register_response = await client.post(
        "/auth/register",
        json={
            "email": email,
            "full_name": "Test User",
            "password": "password123",
        },
        headers={"user-agent": "pytest-sessions"},
    )

    assert register_response.status_code == 201

    register_session_id = register_response.json()["payload"]["session_id"]

    login_response = await client.post(
        "/auth/login",
        json={
            "email": email,
            "password": "password123",
            "fingerprint": "test-fingerprint",
            "session_source": "web",
            "device_type": "desktop",
        },
        headers={"user-agent": "pytest-login-session"},
    )

    assert login_response.status_code == 200

    login_session_id = login_response.json()["payload"]["session_id"]

    conn = await asyncpg.connect(asyncpg_url)
    try:
        user_id = await conn.fetchval("SELECT id FROM users WHERE email = $1", email)
    finally:
        await conn.close()

    response = await client.get("/sessions")

    assert response.status_code == 200

    body = response.json()
    sessions = body["payload"]

    assert len(sessions) == 2

    for session in sessions:
        token_jti = session.pop("token_jti")
        ip_address = session.pop("ip_address")
        expires_at = session.pop("expires_at")
        refresh_expires_at = session.pop("refresh_expires_at")
        created_at = session.pop("created_at")

        assert isinstance(token_jti, str) and len(token_jti) > 0
        assert isinstance(ip_address, str) and len(ip_address) > 0
        assert isinstance(expires_at, str) and len(expires_at) > 0
        assert isinstance(refresh_expires_at, str) and len(refresh_expires_at) > 0
        assert isinstance(created_at, str) and len(created_at) > 0

    sessions_by_id = {session["id"]: session for session in sessions}

    assert body["success"] is True
    assert sessions_by_id == {
        register_session_id: {
            "id": register_session_id,
            "user_id": str(user_id),
            "fingerprint": None,
            "user_agent": "pytest-sessions",
            "session_source": None,
            "device_type": None,
            "os_name": None,
            "os_version": None,
            "browser_name": None,
            "browser_version": None,
            "session_metadata": {},
            "revoked_at": None,
        },
        login_session_id: {
            "id": login_session_id,
            "user_id": str(user_id),
            "fingerprint": "test-fingerprint",
            "user_agent": "pytest-login-session",
            "session_source": "web",
            "device_type": "desktop",
            "os_name": None,
            "os_version": None,
            "browser_name": None,
            "browser_version": None,
            "session_metadata": {},
            "revoked_at": None,
        },
    }
