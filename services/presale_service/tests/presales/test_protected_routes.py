from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_protected_routes_return_401_without_token(client: AsyncClient) -> None:
    presale_id = uuid4()
    file_id = uuid4()
    protected_routes: list[dict[str, Any]] = [
        {"method": "POST", "route": "/presales", "json": _presale_payload()},
        {"method": "GET", "route": "/presales"},
        {"method": "GET", "route": "/presales/questions/default"},
        {"method": "GET", "route": f"/presales/{presale_id}"},
        {"method": "GET", "route": f"/presales/{presale_id}/files/{file_id}"},
        {"method": "GET", "route": f"/presales/{presale_id}/chat/messages"},
        {
            "method": "POST",
            "route": f"/presales/{presale_id}/chat/messages",
            "json": {"message": "Hello"},
        },
        {
            "method": "POST",
            "route": f"/presales/{presale_id}/chat/messages/stream",
            "json": {"message": "Hello"},
        },
        {
            "method": "POST",
            "route": f"/presales/{presale_id}/documents",
            "files": {"file": ("requirements.txt", b"Requirements", "text/plain")},
        },
        {
            "method": "PUT",
            "route": f"/presales/{presale_id}/rates",
            "json": [{"specialist": "Developer", "hourly_rate": 100}],
        },
        {"method": "POST", "route": f"/presales/{presale_id}/questions/generate"},
        {
            "method": "PUT",
            "route": f"/presales/{presale_id}/questions/answers",
            "json": [{"question_id": str(uuid4()), "answer": "Yes"}],
        },
        {
            "method": "POST",
            "route": f"/presales/{presale_id}/estimate",
            "data": {"answers": "[]"},
        },
        {"method": "GET", "route": f"/presales/{presale_id}/history"},
    ]

    for route in protected_routes:
        response = await client.request(
            route["method"],
            route["route"],
            json=route.get("json"),
            data=route.get("data"),
            files=route.get("files"),
        )

        assert response.status_code == 401


def _presale_payload() -> dict[str, Any]:
    return {
        "title": "CRM implementation estimate",
        "customer_name": "Acme Corp",
        "description": "Estimate a CRM implementation project.",
        "desired_outputs": ["timeline", "team", "budget"],
    }
