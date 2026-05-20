from typing import Annotated

import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.request_log import AiRequestLog
from app.schemas import (
    DefaultQuestionsResponse,
    QuestionsRequest,
    QuestionsResponse,
    PresaleEstimateResponse,
)
from app.service import AiService
from shared.responses import success_response

router = APIRouter()
ai_service = AiService()


async def upload_ai_files(files: list[UploadFile] | None) -> tuple[list[list[str]], list[dict]]:
    if not files:
        return [], []
    document_group: list[str] = []
    attachment_groups: list[list[str]] = []
    source_documents: list[dict] = []
    for file in files:
        raw = await file.read()
        uploaded = await ai_service.client.upload_file(
            filename=file.filename or "attachment",
            content=raw,
            content_type=file.content_type,
        )
        file_id = uploaded.get("id")
        modalities = uploaded.get("modalities", [])
        if file_id:
            if "image" in modalities:
                attachment_groups.append([file_id])
            else:
                document_group.append(file_id)
        source_documents.append(
            {
                "filename": file.filename,
                "content_type": file.content_type,
                "bytes": len(raw),
                "ai_file_id": file_id,
                "modalities": modalities,
            }
        )
    if document_group:
        attachment_groups.insert(0, document_group)
    return attachment_groups, source_documents


@router.post("/questions")
async def generate_questions(
    data: QuestionsRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    response = QuestionsResponse(questions=await ai_service.questions(data.text))
    session.add(
        AiRequestLog(
            operation="questions",
            request_payload=data.model_dump(),
            response_payload=response.model_dump(),
        )
    )
    await session.commit()
    return success_response(response.model_dump())


@router.get("/questions/default")
async def get_default_questions(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    response = DefaultQuestionsResponse(questions=ai_service.default_question_items())
    session.add(
        AiRequestLog(
            operation="questions_default",
            request_payload={},
            response_payload=response.model_dump(),
        )
    )
    await session.commit()
    return success_response(response.model_dump())


@router.post("/presale/estimate")
async def generate_presale_estimate(
    session: Annotated[AsyncSession, Depends(get_session)],
    answers: Annotated[
        str,
        Form(
            description=(
                "JSON-массив строк с ответами по порядку вопросов из /questions/default"
            )
        ),
    ],
    files: Annotated[
        list[UploadFile],
        File(description="Файлы, фото, документы и изображения с требованиями или ставками"),
    ] = [],
) -> dict:
    parsed_answers = parse_answers(answers)
    attachment_groups, source_documents = await upload_ai_files(files)
    estimate = await ai_service.presale_estimate(
        answers=parsed_answers,
        attachment_groups=attachment_groups,
    )
    response = PresaleEstimateResponse(**estimate, source_documents=source_documents)
    session.add(
        AiRequestLog(
            operation="presale_estimate",
            request_payload={
                "answers": parsed_answers,
                "source_documents": source_documents,
            },
            response_payload=response.model_dump(),
        )
    )
    await session.commit()
    return success_response(response.model_dump())


def parse_answers(raw: str) -> list[str]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="answers must be a valid JSON array",
        ) from exc
    if not isinstance(value, list):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="answers must be a JSON array",
        )
    return ["" if item is None else str(item) for item in value]
