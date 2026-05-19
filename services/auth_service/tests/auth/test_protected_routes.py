from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_protected_routes_return_401_without_token(client: AsyncClient) -> None:
    protected_routes: list[dict[str, Any]] = [
        {"method": "GET", "route": "/auth/me"},
        {"method": "POST", "route": "/auth/logout"},
        {"method": "GET", "route": "/sessions"},
        {"method": "DELETE", "route": f"/sessions/{uuid4()}"},
        {"method": "GET", "route": "/roles"},
        {"method": "POST", "route": "/roles"},
        {"method": "POST", "route": f"/roles/{uuid4()}/users/{uuid4()}"},
        {"method": "GET", "route": "/users"},
        {"method": "GET", "route": f"/users/{uuid4()}"},
        {"method": "PATCH", "route": "/users/me"},
        {"method": "PATCH", "route": f"/users/{uuid4()}"},
    ]

    for route in protected_routes:
        json = None
        if route == {"method": "POST", "route": "/roles"}:
            json = {"code": "TEST", "title": "Test", "weight": 50}
        if route == {"method": "PATCH", "route": "/users/me"}:
            json = {"full_name": "Test User"}
        if route["method"] == "PATCH" and route["route"] != "/users/me":
            json = {}

        response = await client.request(
            route["method"],
            route["route"],
            json=json,
        )

        assert response.status_code == 401
