from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.request_log import AiRequestLog
from app.schemas import (
    AnalysisRequest,
    AnalysisResponse,
    QuestionsRequest,
    QuestionsResponse,
    QuestionsTextResponse,
    PresaleEstimateResponse,
)
from app.service import AiService
from shared.responses import success_response

router = APIRouter()
ai_service = AiService()


async def upload_gigachat_files(files: list[UploadFile] | None) -> tuple[list[str], list[dict]]:
    if not files:
        return [], []
    attachments: list[str] = []
    source_documents: list[dict] = []
    for file in files:
        raw = await file.read()
        uploaded = await ai_service.client.upload_file(
            filename=file.filename or "attachment",
            content=raw,
            content_type=file.content_type,
        )
        file_id = uploaded.get("id")
        if file_id:
            attachments.append(file_id)
        source_documents.append(
            {
                "filename": file.filename,
                "content_type": file.content_type,
                "bytes": len(raw),
                "gigachat_file_id": file_id,
                "modalities": uploaded.get("modalities", []),
            }
        )
    return attachments, source_documents


@router.post("/questions")
async def generate_questions(
    data: QuestionsRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
):
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
):
    response = QuestionsResponse(questions=ai_service.default_questions())
    session.add(
        AiRequestLog(
            operation="questions_default",
            request_payload={},
            response_payload=response.model_dump(),
        )
    )
    await session.commit()
    return success_response(response.model_dump())


@router.get("/questions/text")
async def generate_questions_text(
    session: Annotated[AsyncSession, Depends(get_session)],
):
    response = QuestionsTextResponse(text=ai_service.questions_text())
    session.add(
        AiRequestLog(
            operation="questions_text",
            request_payload={},
            response_payload=response.model_dump(),
        )
    )
    await session.commit()
    return success_response(response.model_dump())


@router.post("/presale/estimate")
async def generate_presale_estimate(
    session: Annotated[AsyncSession, Depends(get_session)],
    input_text: Annotated[
        str,
        Form(
            description=(
                "Свободный текст пользователя: ответы на вопросы, требования, "
                "ставки вроде 'бэкендер 1000р/час, архитектор 2000р/час'"
            )
        ),
    ],
    files: Annotated[
        list[UploadFile] | None,
        File(description="Файлы, фото, скриншоты, документы с требованиями или ставками"),
    ] = None,
):
    attachments, source_documents = await upload_gigachat_files(files)
    estimate = await ai_service.presale_estimate(
        input_text=input_text,
        attachments=attachments,
    )
    response = PresaleEstimateResponse(**estimate, source_documents=source_documents)
    session.add(
        AiRequestLog(
            operation="presale_estimate",
            request_payload={
                "input_text": input_text,
                "source_documents": source_documents,
            },
            response_payload=response.model_dump(),
        )
    )
    await session.commit()
    return success_response(response.model_dump())


@router.post("/analysis")
async def generate_analysis(
    data: AnalysisRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    analysis = await ai_service.analysis(data.text, data.answers, data.desired_outputs)
    response = AnalysisResponse(**analysis)
    session.add(
        AiRequestLog(
            operation="analysis",
            request_payload=data.model_dump(),
            response_payload=response.model_dump(),
        )
    )
    await session.commit()
    return success_response(response.model_dump())
