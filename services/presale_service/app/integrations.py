import json

import httpx

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

    async def generate_presale_estimate(self, answers: list[str], files: list[dict]) -> dict:
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
                data={"answers": json.dumps(answers, ensure_ascii=False)},
                files=multipart_files or None,
            )
            response.raise_for_status()
            return response.json()["payload"]
