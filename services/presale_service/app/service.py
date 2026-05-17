from uuid import UUID

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import CurrentUser
from app.integrations import AiServiceClient
from app.models.presale import (
    PreAnalysisQuestion,
    PresaleAnalysis,
    PresaleDocument,
    PresaleRequest,
    SpecialistRate,
)
from app.pricing import PricingService
from app.reporting import ReportService
from app.schemas import (
    AnswerInput,
    GenerateAnalysisRequest,
    PresaleCreate,
    SpecialistRateInput,
)


class PresaleService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.ai = AiServiceClient()
        self.pricing = PricingService()
        self.reports = ReportService()

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
        if not text.strip():
            raise HTTPException(status_code=400, detail="Upload a text-like requirements document")
        document = PresaleDocument(
            presale_id=presale.id,
            filename=file.filename or "requirements.txt",
            content_type=file.content_type,
            text_content=text,
        )
        presale.status = "requirements_uploaded"
        self.session.add(document)
        await self.session.commit()
        await self.session.refresh(document)
        return document

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

    async def generate_analysis(self, presale_id: UUID, user: CurrentUser, data: GenerateAnalysisRequest):
        presale = await self.get_owned(presale_id, user)
        raw_ai = await self.ai.generate_analysis(
            {
                "text": self._combined_text(presale),
                "answers": [item.answer for item in presale.questions if item.answer],
                "desired_outputs": presale.desired_outputs,
            }
        )
        rates = self.pricing.normalize_rates(
            [{"role": item.role, "grade": item.grade, "hourly_rate": float(item.hourly_rate)} for item in presale.rates]
        )
        effort_budget = self.pricing.effort_budget(raw_ai["tasks"], rates)
        warranty_budget = self.pricing.warranty_budget(effort_budget["total_cost"])
        payload = {
            **raw_ai,
            "effort_budget": effort_budget,
            "support_budget": self.pricing.support_budget(data.support_scheme, rates),
            "warranty_budget": warranty_budget,
            "monthly_expenses": self.pricing.monthly_expenses(
                effort_budget["total_cost"], warranty_budget["annual_cost"], data.project_months
            ),
        }
        if presale.analysis:
            analysis = presale.analysis
            analysis.payload = payload
        else:
            analysis = PresaleAnalysis(presale_id=presale.id, payload=payload)
            self.session.add(analysis)
        presale.status = "analysis_ready"
        await self.session.flush()
        analysis.report_markdown = self.reports.render(presale, payload)
        await self.session.commit()
        await self.session.refresh(analysis)
        return analysis

    def _combined_text(self, presale: PresaleRequest) -> str:
        return "\n\n".join(document.text_content for document in presale.documents)
