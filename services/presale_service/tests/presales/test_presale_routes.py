import json
from io import BytesIO
from uuid import UUID, uuid4

import asyncpg
import pytest
from common import AiServiceStub, create_access_token
from httpx import AsyncClient
from minio import Minio

from app.core.config import settings


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

    response = await client.get(
        "/presales/questions/default",
        headers={"Authorization": f"Bearer {token}"},
    )

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
        },
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
        },
    ]


@pytest.mark.anyio
async def test_list_chat_messages_returns_multiple_for_presale(
    client: AsyncClient,
    asyncpg_url: str,
) -> None:
    user_id = uuid4()
    other_user_id = uuid4()
    presale_id = uuid4()
    other_presale_id = uuid4()
    first_message_id = uuid4()
    second_message_id = uuid4()
    token = create_access_token(user_id)

    conn = await asyncpg.connect(asyncpg_url)
    try:
        await conn.execute(
            """
            INSERT INTO presale_requests (
                id, owner_id, title, customer_name, description, status, desired_outputs
            )
            VALUES
                ($1, $2, 'CRM estimate', 'Acme Corp', 'Estimate CRM work', 'draft', '[]'::jsonb),
                ($3, $4, 'Other estimate', 'Other Corp', 'Other work', 'draft', '[]'::jsonb)
            """,
            presale_id,
            user_id,
            other_presale_id,
            other_user_id,
        )
        await conn.execute(
            """
            INSERT INTO presale_chat_messages (id, presale_id, role, content, created_at)
            VALUES
                ($1, $2, 'user', 'What is included?', '2026-01-01 10:00:00+00'),
                ($3, $2, 'assistant', 'Timeline and budget are included.', '2026-01-01 10:01:00+00'),
                ($4, $5, 'user', 'Other user message', '2026-01-01 10:02:00+00')
            """,
            first_message_id,
            presale_id,
            second_message_id,
            uuid4(),
            other_presale_id,
        )
    finally:
        await conn.close()

    response = await client.get(
        f"/presales/{presale_id}/chat/messages",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200

    body = response.json()
    payload = body["payload"]

    assert body["success"] is True
    assert len(payload) == 2

    for chat_message in payload:
        assert chat_message.pop("created_at")

    assert payload == [
        {
            "id": str(first_message_id),
            "role": "user",
            "content": "What is included?",
        },
        {
            "id": str(second_message_id),
            "role": "assistant",
            "content": "Timeline and budget are included.",
        },
    ]


@pytest.mark.anyio
async def test_create_chat_message_appends_user_and_assistant_messages(
    client: AsyncClient,
    asyncpg_url: str,
    ai_service_url: str,
) -> None:
    user_id = uuid4()
    presale_id = uuid4()
    existing_message_id = uuid4()
    token = create_access_token(user_id)

    conn = await asyncpg.connect(asyncpg_url)
    try:
        await conn.execute(
            """
            INSERT INTO presale_requests (
                id, owner_id, title, customer_name, description, status, desired_outputs
            )
            VALUES ($1, $2, 'CRM estimate', 'Acme Corp', 'Estimate CRM work', 'draft', '[]'::jsonb)
            """,
            presale_id,
            user_id,
        )
        await conn.execute(
            """
            INSERT INTO presale_chat_messages (id, presale_id, role, content)
            VALUES ($1, $2, 'assistant', 'Seeded assistant message')
            """,
            existing_message_id,
            presale_id,
        )
    finally:
        await conn.close()

    response = await client.post(
        f"/presales/{presale_id}/chat/messages",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "Please refine the estimate."},
    )

    assert response.status_code == 201

    body = response.json()
    payload = body["payload"]

    assert body["success"] is True
    assert len(payload) == 2

    for chat_message in payload:
        assert chat_message.pop("id")
        assert chat_message.pop("created_at")

    assert payload == [
        {
            "role": "user",
            "content": "Please refine the estimate.",
        },
        {
            "role": "assistant",
            "content": "The estimate can be refined with more requirements.",
        },
    ]

    conn = await asyncpg.connect(asyncpg_url)
    try:
        rows = await conn.fetch(
            """
            SELECT role, content
            FROM presale_chat_messages
            WHERE presale_id = $1
            ORDER BY created_at, role DESC
            """,
            presale_id,
        )
    finally:
        await conn.close()

    assert [(row["role"], row["content"]) for row in rows] == [
        ("assistant", "Seeded assistant message"),
        ("user", "Please refine the estimate."),
        ("assistant", "The estimate can be refined with more requirements."),
    ]


@pytest.mark.anyio
async def test_stream_chat_message_streams_and_persists_messages(
    client: AsyncClient,
    asyncpg_url: str,
    ai_service_stub: AiServiceStub,
) -> None:
    user_id = uuid4()
    presale_id = uuid4()
    existing_message_id = uuid4()
    token = create_access_token(user_id)
    ai_service_stub.stream_chunks = ["Refined ", "streamed ", "answer."]

    conn = await asyncpg.connect(asyncpg_url)
    try:
        await conn.execute(
            """
            INSERT INTO presale_requests (
                id, owner_id, title, customer_name, description, status, desired_outputs
            )
            VALUES ($1, $2, 'CRM estimate', 'Acme Corp', 'Estimate CRM work', 'draft', '[]'::jsonb)
            """,
            presale_id,
            user_id,
        )
        await conn.execute(
            """
            INSERT INTO presale_chat_messages (id, presale_id, role, content, created_at)
            VALUES ($1, $2, 'assistant', 'Seeded stream message', '2026-01-01 10:00:00+00')
            """,
            existing_message_id,
            presale_id,
        )
    finally:
        await conn.close()

    async with client.stream(
        "POST",
        f"/presales/{presale_id}/chat/messages/stream",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "Please stream the refined estimate."},
    ) as response:
        lines = [line async for line in response.aiter_lines() if line]

    assert response.status_code == 200
    assert lines == [
        'data: {"delta": "Refined "}',
        'data: {"delta": "streamed "}',
        'data: {"delta": "answer."}',
        'data: {"done": true}',
    ]

    conn = await asyncpg.connect(asyncpg_url)
    try:
        rows = await conn.fetch(
            """
            SELECT role, content
            FROM presale_chat_messages
            WHERE presale_id = $1
            ORDER BY created_at, role DESC
            """,
            presale_id,
        )
    finally:
        await conn.close()

    assert [(row["role"], row["content"]) for row in rows] == [
        ("assistant", "Seeded stream message"),
        ("user", "Please stream the refined estimate."),
        ("assistant", "Refined streamed answer."),
    ]


@pytest.mark.anyio
async def test_download_file_redirects_to_presigned_url(
    client: AsyncClient,
    asyncpg_url: str,
    minio_service_url: str,
) -> None:
    user_id = uuid4()
    presale_id = uuid4()
    file_id = uuid4()
    token = create_access_token(user_id)
    object_key = "users/user/presales/requirements.txt"
    file_content = b"Requirement details"
    minio_client = Minio(
        endpoint=minio_service_url.removeprefix("http://"),
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=False,
    )

    minio_client.make_bucket(settings.minio_bucket)
    minio_client.put_object(
        bucket_name=settings.minio_bucket,
        object_name=object_key,
        data=BytesIO(file_content),
        length=len(file_content),
        content_type="text/plain",
    )

    conn = await asyncpg.connect(asyncpg_url)
    try:
        await conn.execute(
            """
            INSERT INTO presale_requests (
                id, owner_id, title, customer_name, description, status, desired_outputs
            )
            VALUES ($1, $2, 'CRM estimate', 'Acme Corp', 'Estimate CRM work', 'draft', '[]'::jsonb)
            """,
            presale_id,
            user_id,
        )
        await conn.execute(
            """
            INSERT INTO presale_documents (
                id, presale_id, filename, content_type, text_content,
                storage_bucket, storage_object_key, size_bytes
            )
            VALUES (
                $1, $2, 'requirements.txt', 'text/plain', 'Requirement details',
                'presale-files', $3, 128
            )
            """,
            file_id,
            presale_id,
            object_key,
        )
    finally:
        await conn.close()

    response = await client.get(
        f"/presales/{presale_id}/files/{file_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 307
    assert response.headers["location"].startswith(
        f"{minio_service_url}/presale-files/users/user/presales/requirements.txt?"
    )

    async with AsyncClient() as external_client:
        file_response = await external_client.get(response.headers["location"])

    assert file_response.status_code == 200
    assert file_response.content == file_content
