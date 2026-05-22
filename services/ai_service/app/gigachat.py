import asyncio
import json
import time
from collections.abc import AsyncGenerator
from uuid import uuid4

import httpx
from fastapi import HTTPException, status

from app.core.config import settings


class GigaChatClient:
    def __init__(self) -> None:
        self._access_token: str | None = settings.gigachat_access_token
        self._expires_at: float = float("inf") if settings.gigachat_access_token else 0.0
        self._token_lock = asyncio.Lock()

    async def upload_file(
        self,
        filename: str,
        content: bytes,
        content_type: str | None = None,
    ) -> dict:
        token = await self._get_access_token()
        async with httpx.AsyncClient(
            timeout=settings.gigachat_timeout_seconds,
            verify=settings.gigachat_verify_ssl,
        ) as client:
            response = await client.post(
                settings.gigachat_files_url,
                headers={"Authorization": f"Bearer {token}"},
                data={"purpose": "general"},
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
                detail=f"GigaChat file upload failed: {response.text[:500]}",
            )
        return response.json()

    async def chat_json(
        self,
        messages: list[dict],
        temperature: float = 0.2,
        attachments: list[str] | None = None,
        attachment_groups: list[list[str]] | None = None,
        function_call_auto: bool = False,
    ) -> str:
        token = await self._get_access_token()
        prepared_messages = [dict(message) for message in messages]
        if attachment_groups:
            self._attach_grouped_files(prepared_messages, attachment_groups)
        elif attachments:
            for message in reversed(prepared_messages):
                if message.get("role") == "user":
                    message["attachments"] = attachments
                    break
        payload = {
            "model": settings.gigachat_model,
            "messages": prepared_messages,
            "temperature": temperature,
        }
        if function_call_auto:
            payload["function_call"] = "auto"
        async with httpx.AsyncClient(
            timeout=settings.gigachat_timeout_seconds,
            verify=settings.gigachat_verify_ssl,
        ) as client:
            response = await client.post(
                settings.gigachat_chat_url,
                headers={"Authorization": f"Bearer {token}"},
                json=payload,
            )
        if response.status_code >= 400:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"GigaChat completion failed: {response.text[:500]}",
            )
        data = response.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="GigaChat returned an unexpected completion response",
            ) from exc

    async def chat_stream(
        self,
        messages: list[dict],
        temperature: float = 0.2,
        attachments: list[str] | None = None,
        attachment_groups: list[list[str]] | None = None,
        function_call_auto: bool = False,
    ) -> AsyncGenerator[str, None]:
        token = await self._get_access_token()
        prepared_messages = [dict(message) for message in messages]
        if attachment_groups:
            self._attach_grouped_files(prepared_messages, attachment_groups)
        elif attachments:
            for message in reversed(prepared_messages):
                if message.get("role") == "user":
                    message["attachments"] = attachments
                    break
        payload = {
            "model": settings.gigachat_model,
            "messages": prepared_messages,
            "temperature": temperature,
            "stream": True,
        }
        if function_call_auto:
            payload["function_call"] = "auto"
        async with httpx.AsyncClient(
            timeout=settings.gigachat_timeout_seconds,
            verify=settings.gigachat_verify_ssl,
        ) as client:
            async with client.stream(
                "POST",
                settings.gigachat_chat_url,
                headers={"Authorization": f"Bearer {token}"},
                json=payload,
            ) as response:
                if response.status_code >= 400:
                    error_text = await response.aread()
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail=f"GigaChat completion failed: {error_text.decode()[:500]}",
                    )
                async for line in response.aiter_lines():
                    delta = self._stream_delta(line)
                    if delta:
                        yield delta

    def _stream_delta(self, line: str) -> str | None:
        if not line.startswith("data: "):
            return None
        data = line.removeprefix("data: ").strip()
        if not data or data == "[DONE]":
            return None
        try:
            event = json.loads(data)
        except json.JSONDecodeError:
            return None
        try:
            return event["choices"][0]["delta"].get("content") or event["choices"][0][
                "message"
            ].get("content")
        except (KeyError, IndexError, TypeError, AttributeError):
            return None

    def _attach_grouped_files(
        self,
        messages: list[dict],
        attachment_groups: list[list[str]],
    ) -> None:
        groups = [group for group in attachment_groups if group]
        if not groups:
            return
        for message in reversed(messages):
            if message.get("role") == "user":
                message["attachments"] = groups[0]
                break
        for index, group in enumerate(groups[1:], start=2):
            messages.append(
                {
                    "role": "user",
                    "content": f"Дополнительное вложение {index}. Учитывай его при анализе.",
                    "attachments": group,
                }
            )

    async def _get_access_token(self) -> str:
        if self._access_token and time.time() < self._expires_at - 60:
            return self._access_token
        if settings.gigachat_access_token:
            return settings.gigachat_access_token
        if not settings.gigachat_credentials:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AI_GIGACHAT_CREDENTIALS or AI_GIGACHAT_ACCESS_TOKEN is not configured",
            )
        async with self._token_lock:
            if self._access_token and time.time() < self._expires_at - 60:
                return self._access_token
            async with httpx.AsyncClient(
                timeout=settings.gigachat_timeout_seconds,
                verify=settings.gigachat_verify_ssl,
            ) as client:
                response = await client.post(
                    settings.gigachat_oauth_url,
                    headers={
                        "Authorization": f"Basic {settings.gigachat_credentials}",
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Accept": "application/json",
                        "RqUID": str(uuid4()),
                    },
                    data={"scope": settings.gigachat_scope},
                )
            if response.status_code >= 400:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"GigaChat token request failed: {response.text[:500]}",
                )
            data = response.json()
            token = data.get("access_token")
            if not token:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="GigaChat token response does not contain access_token",
                )
            self._access_token = token
            expires_at = data.get("expires_at")
            self._expires_at = (float(expires_at) / 1000.0) if expires_at else time.time() + 1500
            return token
