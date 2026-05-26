from typing import Annotated

import json

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse

from app.schemas import (
    ChatRequest,
    ChatResponse,
    DefaultQuestionsResponse,
    QuestionsRequest,
    QuestionsResponse,
    PresaleEstimateResponse,
)
from app.service import AiService
from shared.responses import success_response

router = APIRouter()
ai_service = AiService()


def normalize_upload_files(files: UploadFile | list[UploadFile] | None) -> list[UploadFile]:
    if files is None:
        return []

    if isinstance(files, list):
        return files

    return [files]


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
) -> dict:
    response = QuestionsResponse(questions=await ai_service.questions(data.text))
    return success_response(response.model_dump())


@router.get("/questions/default")
async def get_default_questions() -> dict:
    response = DefaultQuestionsResponse(questions=ai_service.default_question_items())
    return success_response(response.model_dump())


@router.post("/chat")
async def chat(
    data: ChatRequest,
) -> dict:
    response = ChatResponse(message=await ai_service.presale_chat(data.messages))
    return success_response(response.model_dump())


@router.post("/chat/stream")
async def chat_stream(data: ChatRequest) -> StreamingResponse:
    async def event_stream():
        async for chunk in ai_service.presale_chat_stream(data.messages):
            yield f"data: {json.dumps({'delta': chunk}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/presale/estimate")
async def generate_presale_estimate(
    answers: Annotated[
        str,
        Form(
            description=(
                "JSON-массив строк с ответами по порядку вопросов из /questions/default"
            )
        ),
    ],
    files: Annotated[
        UploadFile | list[UploadFile] | None,
        File(description="Файлы, фото, документы и изображения с требованиями или ставками"),
    ] = None,
    desired_outputs: Annotated[
        str,
        Form(description="JSON-массив выбранных пользователем результатов пресейла"),
    ] = "[]",
) -> dict:
    parsed_answers = parse_answers(answers)
    parsed_desired_outputs = parse_string_list(desired_outputs)
    attachment_groups, source_documents = await upload_ai_files(normalize_upload_files(files))
    estimate = await ai_service.presale_estimate(
        answers=parsed_answers,
        desired_outputs=parsed_desired_outputs,
        attachment_groups=attachment_groups,
    )
    response = PresaleEstimateResponse(**estimate, source_documents=source_documents)
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


def parse_string_list(raw: str) -> list[str]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="desired_outputs must be a valid JSON array",
        ) from exc

    if not isinstance(value, list):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="desired_outputs must be a JSON array",
        )

    return [str(item).strip() for item in value if str(item).strip()]
