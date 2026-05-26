import json
import socket
import threading
import time
from collections.abc import Generator
from dataclasses import dataclass, field
from uuid import UUID

import jwt
import pytest
import uvicorn
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from testcontainers.core.container import DockerContainer
from testcontainers.core.waiting_utils import wait_for_logs

from app.core.config import settings
from shared.responses import success_response


@dataclass
class AiServiceStub:
    url: str
    chat_message: str = "The estimate can be refined with more requirements."
    generated_questions: list[str] = field(default_factory=lambda: ["What is the project scope?"])
    generate_questions_requests: list[dict] = field(default_factory=list)
    estimate_payload: dict = field(default_factory=lambda: {"summary": "Generated estimate"})
    estimate_requests: list[dict] = field(default_factory=list)
    stream_chunks: list[str] = field(default_factory=lambda: ["The estimate ", "can be streamed."])


class GenerateQuestionsRequest(BaseModel):
    text: str


@pytest.fixture()
def minio_service_url() -> Generator[str, None, None]:
    access_key = "minioadmin"
    secret_key = "minioadmin"

    with DockerContainer("minio/minio:RELEASE.2025-04-22T22-12-26Z") as minio:
        minio.with_env("MINIO_ROOT_USER", access_key)
        minio.with_env("MINIO_ROOT_PASSWORD", secret_key)
        minio.with_command("server /data")
        minio.with_exposed_ports(9000)
        minio.start()
        wait_for_logs(minio, "API:", timeout=30)

        host = minio.get_container_host_ip()
        port = minio.get_exposed_port(9000)
        endpoint = f"{host}:{port}"
        bucket = "presale-files"

        previous_endpoint = settings.minio_endpoint
        previous_access_key = settings.minio_access_key
        previous_secret_key = settings.minio_secret_key
        previous_bucket = settings.minio_bucket
        previous_secure = settings.minio_secure
        previous_public_url = settings.minio_public_url

        settings.minio_endpoint = endpoint
        settings.minio_access_key = access_key
        settings.minio_secret_key = secret_key
        settings.minio_bucket = bucket
        settings.minio_secure = False
        settings.minio_public_url = f"http://{endpoint}"

        try:
            yield f"http://{endpoint}"
        finally:
            settings.minio_endpoint = previous_endpoint
            settings.minio_access_key = previous_access_key
            settings.minio_secret_key = previous_secret_key
            settings.minio_bucket = previous_bucket
            settings.minio_secure = previous_secure
            settings.minio_public_url = previous_public_url


def create_access_token(user_id: UUID, email: str = "customer@example.com") -> str:
    return jwt.encode(
        {"sub": str(user_id), "email": email},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


@pytest.fixture()
def ai_service_stub() -> Generator[AiServiceStub, None, None]:
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
    service_stub = AiServiceStub(url="")

    @stub.get("/questions/default")
    async def get_default_questions() -> dict:
        return success_response({"questions": questions})

    @stub.post("/questions")
    async def generate_questions(data: GenerateQuestionsRequest) -> dict:
        service_stub.generate_questions_requests.append(data.model_dump())

        return success_response({"questions": service_stub.generated_questions})

    @stub.post("/chat")
    async def chat() -> dict:
        return success_response({"message": service_stub.chat_message})

    @stub.post("/chat/stream")
    async def chat_stream() -> StreamingResponse:
        async def events() -> Generator[str, None, None]:
            for chunk in service_stub.stream_chunks:
                yield f"data: {json.dumps({'delta': chunk})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"

        return StreamingResponse(events(), media_type="text/event-stream")

    @stub.post("/presale/estimate")
    async def generate_presale_estimate(
        answers: str = Form(),
        files: list[UploadFile] = File(default=[]),
    ) -> dict:
        request_files = []
        for file in files:
            request_files.append(
                {
                    "filename": file.filename,
                    "content_type": file.content_type,
                    "content": (await file.read()).decode("utf-8"),
                }
            )

        service_stub.estimate_requests.append(
            {
                "answers": json.loads(answers),
                "files": request_files,
            }
        )

        return success_response(service_stub.estimate_payload)

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

    previous_ai_service_url = settings.ai_service_url
    service_stub.url = f"http://127.0.0.1:{port}"
    settings.ai_service_url = service_stub.url

    try:
        yield service_stub
    finally:
        settings.ai_service_url = previous_ai_service_url
        server.should_exit = True
        thread.join(timeout=5)


@pytest.fixture()
def ai_service_url(ai_service_stub: AiServiceStub) -> str:
    return ai_service_stub.url
