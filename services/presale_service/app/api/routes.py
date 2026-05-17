from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser, get_current_user
from app.db.session import get_session
from app.schemas import (
    AnalysisRead,
    AnswerInput,
    DocumentRead,
    GenerateAnalysisRequest,
    PresaleCreate,
    PresaleRead,
    QuestionRead,
    SpecialistRateInput,
    SpecialistRateRead,
)
from app.service import PresaleService
from shared.responses import success_response

router = APIRouter()


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


@router.post("/presales/{presale_id}/analysis/generate")
async def generate_analysis(
    presale_id: UUID,
    data: GenerateAnalysisRequest,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    obj = await PresaleService(session).generate_analysis(presale_id, user, data)
    return success_response(AnalysisRead.model_validate(obj).model_dump(mode="json"))
