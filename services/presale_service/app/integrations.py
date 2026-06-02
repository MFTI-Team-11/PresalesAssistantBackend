import json
from collections.abc import AsyncGenerator

import httpx
from fastapi import HTTPException, status

from app.core.config import settings


class AiServiceClient:
    async def default_questions(self) -> list[dict]:
        async with httpx.AsyncClient(base_url=settings.ai_service_url, timeout=30) as client:
            response = await client.get("/questions/default")
            response.raise_for_status()
            return response.json()["payload"]["questions"]

    async def generate_questions(self, text: str) -> list[str]:
        async with httpx.AsyncClient(base_url=settings.ai_service_url, timeout=30) as client:
            response = await client.post("/questions", json={"text": text})
            response.raise_for_status()
            return response.json()["payload"]["questions"]

    async def chat(self, messages: list[dict]) -> str:
        async with httpx.AsyncClient(base_url=settings.ai_service_url, timeout=180) as client:
            response = await client.post("/chat", json={"messages": messages})
            response.raise_for_status()
            return response.json()["payload"]["message"]

    async def chat_stream(self, messages: list[dict]) -> AsyncGenerator[str, None]:
        async with httpx.AsyncClient(base_url=settings.ai_service_url, timeout=180) as client:
            async with client.stream("POST", "/chat/stream", json={"messages": messages}) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line.removeprefix("data: ").strip()
                    if not data:
                        continue
                    event = json.loads(data)
                    if event.get("delta"):
                        yield str(event["delta"])
                    if event.get("done"):
                        break

    async def generate_presale_estimate(
        self,
        answers: list[str],
        files: list[dict],
        desired_outputs: list[str],
    ) -> dict:
        multipart_files = []
        for item in files:
            multipart_files.append(
                (
                    "files",
                    (
                        item["filename"],
                        item["content"],
                        item.get("content_type") or "application/octet-stream",
                    ),
                )
            )
        async with httpx.AsyncClient(base_url=settings.ai_service_url, timeout=180) as client:
            response = await client.post(
                "/presale/estimate",
                data={
                    "answers": json.dumps(answers, ensure_ascii=False),
                    "desired_outputs": json.dumps(desired_outputs, ensure_ascii=False),
                },
                files=multipart_files or None,
            )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"AI service estimate failed: {response.text[:500]}",
                ) from exc
            return response.json()["payload"]
