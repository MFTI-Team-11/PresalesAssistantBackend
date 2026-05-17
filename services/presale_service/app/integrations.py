import httpx

from app.core.config import settings


class AiServiceClient:
    async def generate_questions(self, text: str) -> list[str]:
        async with httpx.AsyncClient(base_url=settings.ai_service_url, timeout=30) as client:
            response = await client.post("/questions", json={"text": text})
            response.raise_for_status()
            return response.json()["payload"]["questions"]

    async def generate_analysis(self, payload: dict) -> dict:
        async with httpx.AsyncClient(base_url=settings.ai_service_url, timeout=60) as client:
            response = await client.post("/analysis", json=payload)
            response.raise_for_status()
            return response.json()["payload"]
