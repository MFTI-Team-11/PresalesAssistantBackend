import httpx
from fastapi import HTTPException, status

from app.core.config import settings


class OpenAIClient:
    async def upload_file(
        self,
        filename: str,
        content: bytes,
        content_type: str | None = None,
    ) -> dict:
        if not settings.openai_api_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AI_OPENAI_API_KEY is not configured",
            )

        async with httpx.AsyncClient(timeout=settings.openai_timeout_seconds) as client:
            response = await client.post(
                settings.openai_files_url,
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                data={"purpose": settings.openai_file_purpose},
                files={
                    "file": (
                        filename,
                        content,
                        content_type or "application/octet-stream",
                    )
                },
            )

        if response.status_code >= 400:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"OpenAI file upload failed: {response.text[:500]}",
            )

        uploaded = response.json()
        uploaded["modalities"] = self._modalities(content_type)

        return uploaded

    async def chat_json(
        self,
        messages: list[dict],
        temperature: float = 0.2,
        attachments: list[str] | None = None,
        attachment_groups: list[list[str]] | None = None,
        function_call_auto: bool = False,
    ) -> str:
        if not settings.openai_api_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AI_OPENAI_API_KEY is not configured",
            )

        payload = {
            "model": settings.openai_model,
            "input": self._input(messages, attachments, attachment_groups),
            "temperature": temperature,
        }

        async with httpx.AsyncClient(timeout=settings.openai_timeout_seconds) as client:
            response = await client.post(
                settings.openai_responses_url,
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                json=payload,
            )

        if response.status_code >= 400:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"OpenAI response failed: {response.text[:500]}",
            )

        data = response.json()
        text = data.get("output_text") or self._output_text(data)
        if not text:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="OpenAI returned an unexpected response",
            )

        return text

    def _input(
        self,
        messages: list[dict],
        attachments: list[str] | None,
        attachment_groups: list[list[str]] | None,
    ) -> list[dict]:
        prepared = [self._message(message) for message in messages]
        groups = [group for group in attachment_groups or [] if group]

        if groups:
            self._attach_grouped_files(prepared, groups)
        elif attachments:
            self._attach_files_to_last_user_message(prepared, attachments)

        return prepared

    def _message(self, message: dict) -> dict:
        role = "developer" if message.get("role") == "system" else message.get("role", "user")
        return {
            "role": role,
            "content": [
                {
                    "type": "input_text",
                    "text": str(message.get("content", "")),
                }
            ],
        }

    def _attach_grouped_files(self, messages: list[dict], groups: list[list[str]]) -> None:
        self._attach_files_to_last_user_message(messages, groups[0])

        for index, group in enumerate(groups[1:], start=2):
            messages.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": f"Additional attachment {index}. Use it in the analysis.",
                        },
                        *self._file_parts(group),
                    ],
                }
            )

    def _attach_files_to_last_user_message(self, messages: list[dict], file_ids: list[str]) -> None:
        for message in reversed(messages):
            if message.get("role") == "user":
                message["content"].extend(self._file_parts(file_ids))

                return

    def _file_parts(self, file_ids: list[str]) -> list[dict]:
        return [{"type": "input_file", "file_id": file_id} for file_id in file_ids]

    def _output_text(self, data: dict) -> str | None:
        parts: list[str] = []

        for item in data.get("output", []):
            for content in item.get("content", []):
                if content.get("type") in {"output_text", "text"} and content.get("text"):
                    parts.append(str(content["text"]))

        return "\n".join(parts) if parts else None

    def _modalities(self, content_type: str | None) -> list[str]:
        if content_type and content_type.startswith("image/"):
            return ["image"]

        return ["document"]
