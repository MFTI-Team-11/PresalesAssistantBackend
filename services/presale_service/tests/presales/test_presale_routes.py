import json
import socket
import threading
import time
from collections.abc import Generator
from uuid import UUID, uuid4

import asyncpg
import jwt
import pytest
import uvicorn
from fastapi import FastAPI
from httpx import AsyncClient

from app.core.config import settings
from shared.responses import success_response


def create_access_token(user_id: UUID, email: str = "customer@example.com") -> str:
    return jwt.encode(
        {"sub": str(user_id), "email": email},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


@pytest.fixture()
def ai_service_url() -> Generator[str, None, None]:
    questions = [
        {
            "id": "business_goal",
            "text": "What business goal should the project achieve?",
            "category": "business",
            "required": True,
            "answer_type": "text",
            "allow_file": False,
            "file_required": False,
            "file_hint": None,
            "placeholder": "Describe the expected business outcome",
        },
        {
            "id": "requirements_file",
            "text": "Upload existing requirements if available.",
            "category": "documents",
            "required": False,
            "answer_type": "file",
            "allow_file": True,
            "file_required": False,
            "file_hint": "PDF, DOCX, XLSX, TXT",
            "placeholder": None,
        },
    ]

    stub = FastAPI()

    @stub.get("/questions/default")
    async def get_default_questions() -> dict:
        return success_response({"questions": questions})

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]

    config = uvicorn.Config(
        stub,
        host="127.0.0.1",
        port=port,
        log_level="warning",
        lifespan="off",
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    for _ in range(100):
        if server.started:
            break
        time.sleep(0.01)

    yield f"http://127.0.0.1:{port}"

    server.should_exit = True
    thread.join(timeout=5)


@pytest.mark.anyio
async def test_create_presale_happy_case(
    client: AsyncClient,
    asyncpg_url: str,
) -> None:
    user_id = uuid4()
    token = create_access_token(user_id)

    response = await client.post(
        "/presales",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "CRM implementation estimate",
            "customer_name": "Acme Corp",
            "description": "Estimate a CRM implementation project.",
            "desired_outputs": ["timeline", "team", "budget"],
        },
    )

    assert response.status_code == 201

    body = response.json()
    payload = body["payload"]
    presale_id = UUID(payload.pop("id"))
    owner_id = UUID(payload.pop("owner_id"))
    created_at = payload.pop("created_at")
    updated_at = payload.pop("updated_at")

    assert body["success"] is True
    assert owner_id == user_id
    assert created_at
    assert updated_at
    assert payload == {
        "title": "CRM implementation estimate",
        "customer_name": "Acme Corp",
        "description": "Estimate a CRM implementation project.",
        "status": "draft",
        "desired_outputs": ["timeline", "team", "budget"],
    }

    conn = await asyncpg.connect(asyncpg_url)
    try:
        row = await conn.fetchrow(
            """
            SELECT owner_id, title, customer_name, description, status, desired_outputs
            FROM presale_requests
            WHERE id = $1
            """,
            presale_id,
        )
    finally:
        await conn.close()

    assert row is not None
    assert row["owner_id"] == user_id
    assert row["title"] == "CRM implementation estimate"
    assert row["customer_name"] == "Acme Corp"
    assert row["description"] == "Estimate a CRM implementation project."
    assert row["status"] == "draft"
    assert json.loads(row["desired_outputs"]) == ["timeline", "team", "budget"]


@pytest.mark.anyio
async def test_list_presales_returns_two_items_for_current_user(
    client: AsyncClient,
    asyncpg_url: str,
) -> None:
    user_id = uuid4()
    other_user_id = uuid4()
    token = create_access_token(user_id)

    conn = await asyncpg.connect(asyncpg_url)
    try:
        await conn.execute(
            """
            INSERT INTO presale_requests (
                id, owner_id, title, customer_name, description, status, desired_outputs
            )
            VALUES
                (
                    $1, $2, 'First estimate', 'Acme Corp', 'First description',
                    'draft', '["timeline"]'::jsonb
                ),
                (
                    $3, $2, 'Second estimate', 'Beta LLC', 'Second description',
                    'draft', '["budget"]'::jsonb
                ),
                (
                    $4, $5, 'Other estimate', 'Other Corp', 'Other description',
                    'draft', '["team"]'::jsonb
                )
            """,
            uuid4(),
            user_id,
            uuid4(),
            uuid4(),
            other_user_id,
        )
    finally:
        await conn.close()

    response = await client.get(
        "/presales",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200

    body = response.json()
    payload = body["payload"]

    assert body["success"] is True
    assert len(payload) == 2

    rows = []
    for item in payload:
        assert item.pop("id")
        assert item.pop("created_at")
        assert item.pop("updated_at")
        rows.append(item)

    assert rows == [
        {
            "owner_id": str(user_id),
            "title": "First estimate",
            "customer_name": "Acme Corp",
            "description": "First description",
            "status": "draft",
            "desired_outputs": ["timeline"],
        },
        {
            "owner_id": str(user_id),
            "title": "Second estimate",
            "customer_name": "Beta LLC",
            "description": "Second description",
            "status": "draft",
            "desired_outputs": ["budget"],
        },
    ]


@pytest.mark.anyio
async def test_get_default_questions_returns_questions(
    client: AsyncClient,
    ai_service_url: str,
) -> None:
    token = create_access_token(uuid4())
    previous_ai_service_url = settings.ai_service_url
    settings.ai_service_url = ai_service_url

    try:
        response = await client.get(
            "/presales/questions/default",
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        settings.ai_service_url = previous_ai_service_url

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "payload": [
            {
                "id": "business_goal",
                "text": "What business goal should the project achieve?",
                "category": "business",
                "required": True,
                "answer_type": "text",
                "allow_file": False,
                "file_required": False,
                "file_hint": None,
                "placeholder": "Describe the expected business outcome",
            },
            {
                "id": "requirements_file",
                "text": "Upload existing requirements if available.",
                "category": "documents",
                "required": False,
                "answer_type": "file",
                "allow_file": True,
                "file_required": False,
                "file_hint": "PDF, DOCX, XLSX, TXT",
                "placeholder": None,
            },
        ],
    }


@pytest.mark.anyio
async def test_get_presale_returns_history_for_current_user(
    client: AsyncClient,
    asyncpg_url: str,
) -> None:
    user_id = uuid4()
    presale_id = uuid4()
    question_id = uuid4()
    document_id = uuid4()
    second_document_id = uuid4()
    analysis_id = uuid4()
    chat_message_id = uuid4()
    second_chat_message_id = uuid4()
    token = create_access_token(user_id)

    conn = await asyncpg.connect(asyncpg_url)
    try:
        await conn.execute(
            """
            INSERT INTO presale_requests (
                id, owner_id, title, customer_name, description, status, desired_outputs
            )
            VALUES (
                $1, $2, 'CRM implementation estimate', 'Acme Corp', 'Estimate CRM work',
                'analysis_ready', '["timeline", "budget"]'::jsonb
            )
            """,
            presale_id,
            user_id,
        )
        await conn.execute(
            """
            INSERT INTO pre_analysis_questions (id, presale_id, question, answer)
            VALUES ($1, $2, 'What is the business goal?', 'Improve sales workflow')
            """,
            question_id,
            presale_id,
        )
        await conn.execute(
            """
            INSERT INTO presale_documents (
                id, presale_id, filename, content_type, text_content,
                storage_bucket, storage_object_key, size_bytes
            )
            VALUES
                (
                    $1, $2, 'requirements.txt', 'text/plain', 'Requirement details',
                    'presale-files', 'users/user/presales/file.txt', 128
                ),
                (
                    $3, $2, 'scope.pdf', 'application/pdf', 'Scope details',
                    'presale-files', 'users/user/presales/scope.pdf', 256
                )
            """,
            document_id,
            presale_id,
            second_document_id,
        )
        await conn.execute(
            """
            INSERT INTO presale_analyses (id, presale_id, payload, report_markdown)
            VALUES ($1, $2, '{"summary": "CRM estimate"}'::jsonb, '# Report')
            """,
            analysis_id,
            presale_id,
        )
        await conn.execute(
            """
            INSERT INTO presale_chat_messages (id, presale_id, role, content)
            VALUES
                ($1, $2, 'user', 'Can you explain the estimate?'),
                ($3, $2, 'assistant', 'The estimate is based on the provided requirements.')
            """,
            chat_message_id,
            presale_id,
            second_chat_message_id,
        )
    finally:
        await conn.close()

    response = await client.get(
        f"/presales/{presale_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200

    body = response.json()
    payload = body["payload"]
    presale = payload["presale"]

    assert body["success"] is True
    assert presale.pop("created_at")
    assert presale.pop("updated_at")
    assert presale == {
        "id": str(presale_id),
        "owner_id": str(user_id),
        "title": "CRM implementation estimate",
        "customer_name": "Acme Corp",
        "description": "Estimate CRM work",
        "status": "analysis_ready",
        "desired_outputs": ["timeline", "budget"],
    }
    assert payload["questions"] == [
        {
            "id": str(question_id),
            "question": "What is the business goal?",
            "answer": "Improve sales workflow",
        }
    ]

    for document in payload["documents"]:
        assert document.pop("created_at")

    assert payload["documents"] == [
        {
            "id": str(document_id),
            "filename": "requirements.txt",
            "content_type": "text/plain",
            "storage_bucket": "presale-files",
            "storage_object_key": "users/user/presales/file.txt",
            "size_bytes": 128,
        },
        {
            "id": str(second_document_id),
            "filename": "scope.pdf",
            "content_type": "application/pdf",
            "storage_bucket": "presale-files",
            "storage_object_key": "users/user/presales/scope.pdf",
            "size_bytes": 256,
        }
    ]
    assert payload["analysis"] == {
        "id": str(analysis_id),
        "payload": {"summary": "CRM estimate"},
        "report_markdown": "# Report",
    }

    for chat_message in payload["chat_messages"]:
        assert chat_message.pop("created_at")

    assert payload["chat_messages"] == [
        {
            "id": str(chat_message_id),
            "role": "user",
            "content": "Can you explain the estimate?",
        },
        {
            "id": str(second_chat_message_id),
            "role": "assistant",
            "content": "The estimate is based on the provided requirements.",
        }
    ]
