from typing import Annotated
from uuid import UUID

import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser, get_current_user
from app.db.session import get_session
from app.schemas import (
    AnalysisRead,
    AnswerInput,
    DocumentRead,
    EstimateHistoryRead,
    PresaleCreate,
    PresaleRead,
    QuestionRead,
    SpecialistRateInput,
    SpecialistRateRead,
)
from app.service import PresaleService
from shared.responses import success_response

router = APIRouter()


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


@router.post("/presales", status_code=201)
async def create_presale(
    data: PresaleCreate,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    obj = await PresaleService(session).create(data, user)
    return success_response(PresaleRead.model_validate(obj).model_dump(mode="json"))


@router.get("/presales")
async def list_presales(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    items = await PresaleService(session).list_for_user(user)
    return success_response([PresaleRead.model_validate(item).model_dump(mode="json") for item in items])


@router.post("/presales/{presale_id}/documents", status_code=201)
async def upload_document(
    presale_id: UUID,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    file: UploadFile = File(...),
):
    obj = await PresaleService(session).upload_document(presale_id, user, file)
    return success_response(DocumentRead.model_validate(obj).model_dump(mode="json"))


@router.put("/presales/{presale_id}/rates")
async def replace_rates(
    presale_id: UUID,
    data: list[SpecialistRateInput],
    user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    items = await PresaleService(session).replace_rates(presale_id, user, data)
    return success_response([SpecialistRateRead.model_validate(item).model_dump(mode="json") for item in items])


@router.post("/presales/{presale_id}/questions/generate")
async def generate_questions(
    presale_id: UUID,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    items = await PresaleService(session).generate_questions(presale_id, user)
    return success_response([QuestionRead.model_validate(item).model_dump(mode="json") for item in items])


@router.put("/presales/{presale_id}/questions/answers")
async def save_answers(
    presale_id: UUID,
    data: list[AnswerInput],
    user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    items = await PresaleService(session).save_answers(presale_id, user, data)
    return success_response([QuestionRead.model_validate(item).model_dump(mode="json") for item in items])


@router.post("/presales/{presale_id}/estimate")
async def generate_estimate(
    presale_id: UUID,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    answers: Annotated[
        str,
        Form(description="JSON-массив строк с ответами по порядку вопросов из ai_service"),
    ],
    files: Annotated[list[UploadFile] | None, File()] = None,
):
    obj = await PresaleService(session).generate_estimate(
        presale_id=presale_id,
        user=user,
        answers=parse_answers(answers),
        files=files or [],
    )
    return success_response(AnalysisRead.model_validate(obj).model_dump(mode="json"))


@router.get("/presales/{presale_id}/history")
async def get_history(
    presale_id: UUID,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    data = await PresaleService(session).history(presale_id, user)
    payload = EstimateHistoryRead(
        presale=PresaleRead.model_validate(data["presale"]),
        questions=[QuestionRead.model_validate(item) for item in data["questions"]],
        documents=[DocumentRead.model_validate(item) for item in data["documents"]],
        analysis=AnalysisRead.model_validate(data["analysis"]) if data["analysis"] else None,
    )
    return success_response(payload.model_dump(mode="json"))
