from uuid import UUID
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import CurrentUser
from app.core.storage import FileStorage
from app.integrations import AiServiceClient
from app.models.presale import (
    PreAnalysisQuestion,
    PresaleAnalysis,
    PresaleDocument,
    PresaleRequest,
    SpecialistRate,
)
from app.schemas import (
    AnswerInput,
    PresaleCreate,
    SpecialistRateInput,
)


class PresaleService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.ai = AiServiceClient()
        self.storage = FileStorage()

    async def create(self, data: PresaleCreate, user: CurrentUser) -> PresaleRequest:
        presale = PresaleRequest(owner_id=user.id, **data.model_dump())
        self.session.add(presale)
        await self.session.commit()
        await self.session.refresh(presale)
        return presale

    async def list_for_user(self, user: CurrentUser) -> list[PresaleRequest]:
        result = await self.session.execute(
            select(PresaleRequest)
            .where(PresaleRequest.owner_id == user.id)
            .order_by(PresaleRequest.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_owned(self, presale_id: UUID, user: CurrentUser) -> PresaleRequest:
        result = await self.session.execute(
            select(PresaleRequest)
            .where(PresaleRequest.id == presale_id, PresaleRequest.owner_id == user.id)
            .options(
                selectinload(PresaleRequest.documents),
                selectinload(PresaleRequest.rates),
                selectinload(PresaleRequest.questions),
                selectinload(PresaleRequest.analysis),
            )
        )
        presale = result.scalar_one_or_none()
        if not presale:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Presale not found")
        return presale

    async def upload_document(self, presale_id: UUID, user: CurrentUser, file: UploadFile):
        presale = await self.get_owned(presale_id, user)
        raw = await file.read()
        text = raw.decode("utf-8", errors="ignore")
        object_key = self._storage_key(user, presale, file.filename or "attachment")
        self.storage.put_file(object_key, raw, file.content_type)
        document = PresaleDocument(
            presale_id=presale.id,
            filename=file.filename or "requirements.txt",
            content_type=file.content_type,
            text_content=text,
            storage_bucket=self.storage.bucket,
            storage_object_key=object_key,
            size_bytes=len(raw),
        )
        presale.status = "requirements_uploaded"
        self.session.add(document)
        await self.session.commit()
        await self.session.refresh(document)
        return document

    async def generate_estimate(
        self,
        presale_id: UUID,
        user: CurrentUser,
        answers: list[str],
        files: list[UploadFile],
    ) -> PresaleAnalysis:
        presale = await self.get_owned(presale_id, user)
        questions = await self.ai.default_questions()
        await self.session.execute(
            delete(PreAnalysisQuestion).where(PreAnalysisQuestion.presale_id == presale.id)
        )
        saved_questions = []
        for index, question in enumerate(questions):
            answer = answers[index] if index < len(answers) else ""
            saved_questions.append(
                PreAnalysisQuestion(
                    presale_id=presale.id,
                    question=question["text"],
                    answer=answer,
                )
            )
        self.session.add_all(saved_questions)

        ai_files = []
        for file in files:
            raw = await file.read()
            filename = file.filename or "attachment"
            object_key = self._storage_key(user, presale, filename)
            self.storage.put_file(object_key, raw, file.content_type)
            text = raw.decode("utf-8", errors="ignore")
            self.session.add(
                PresaleDocument(
                    presale_id=presale.id,
                    filename=filename,
                    content_type=file.content_type,
                    text_content=text,
                    storage_bucket=self.storage.bucket,
                    storage_object_key=object_key,
                    size_bytes=len(raw),
                )
            )
            ai_files.append(
                {
                    "filename": filename,
                    "content_type": file.content_type,
                    "content": raw,
                }
            )

        payload = await self.ai.generate_presale_estimate(answers, ai_files)
        if presale.analysis:
            analysis = presale.analysis
            analysis.payload = payload
        else:
            analysis = PresaleAnalysis(presale_id=presale.id, payload=payload)
            self.session.add(analysis)
        presale.status = "analysis_ready"
        analysis.report_markdown = ""
        await self.session.commit()
        await self.session.refresh(analysis)
        return analysis

    async def history(self, presale_id: UUID, user: CurrentUser) -> dict:
        presale = await self.get_owned(presale_id, user)
        return {
            "presale": presale,
            "questions": presale.questions,
            "documents": presale.documents,
            "analysis": presale.analysis,
        }

    async def replace_rates(self, presale_id: UUID, user: CurrentUser, rates: list[SpecialistRateInput]):
        presale = await self.get_owned(presale_id, user)
        await self.session.execute(delete(SpecialistRate).where(SpecialistRate.presale_id == presale.id))
        saved = [SpecialistRate(presale_id=presale.id, **item.model_dump()) for item in rates]
        self.session.add_all(saved)
        await self.session.commit()
        return saved

    async def generate_questions(self, presale_id: UUID, user: CurrentUser):
        presale = await self.get_owned(presale_id, user)
        questions = await self.ai.generate_questions(self._combined_text(presale))
        await self.session.execute(
            delete(PreAnalysisQuestion).where(PreAnalysisQuestion.presale_id == presale.id)
        )
        saved = [PreAnalysisQuestion(presale_id=presale.id, question=item) for item in questions]
        presale.status = "questions_generated"
        self.session.add_all(saved)
        await self.session.commit()
        return saved

    async def save_answers(self, presale_id: UUID, user: CurrentUser, answers: list[AnswerInput]):
        presale = await self.get_owned(presale_id, user)
        questions = {item.id: item for item in presale.questions}
        for item in answers:
            if item.question_id in questions:
                questions[item.question_id].answer = item.answer
        presale.status = "answers_received"
        await self.session.commit()
        return list(questions.values())

    def _combined_text(self, presale: PresaleRequest) -> str:
        return "\n\n".join(document.text_content for document in presale.documents)

    def _storage_key(self, user: CurrentUser, presale: PresaleRequest, filename: str) -> str:
        return f"{user.id}/{presale.id}/{uuid4().hex}_{filename}"
