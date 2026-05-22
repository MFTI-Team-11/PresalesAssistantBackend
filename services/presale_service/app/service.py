from uuid import UUID
from uuid import uuid4
from io import BytesIO
from zipfile import BadZipFile, ZipFile
import xml.etree.ElementTree as ET
from collections.abc import AsyncGenerator

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
    PresaleChatMessage,
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
    AI_SUPPORTED_EXTENSIONS = {".docx", ".xlsx", ".pdf", ".txt", ".csv", ".md"}
    AI_SUPPORTED_CONTENT_TYPES = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "text/csv",
        "text/markdown",
        "text/plain",
    }

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
                selectinload(PresaleRequest.chat_messages),
            )
        )
        presale = result.scalar_one_or_none()
        if not presale:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Presale not found")
        return presale

    async def default_questions(self) -> list[dict]:
        return await self.ai.default_questions()

    async def upload_document(self, presale_id: UUID, user: CurrentUser, file: UploadFile):
        presale = await self.get_owned(presale_id, user)
        raw = await file.read()
        text = self._extract_text(raw, file.filename or "", file.content_type)
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
            text = self._extract_text(raw, filename, file.content_type)
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
            if self._can_send_to_ai(filename, file.content_type):
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
            "chat_messages": presale.chat_messages,
        }

    async def file_url(self, presale_id: UUID, file_id: UUID, user: CurrentUser) -> str:
        presale = await self.get_owned(presale_id, user)
        document = next((item for item in presale.documents if item.id == file_id), None)
        if not document:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
        if not document.storage_object_key:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File object not found")
        url = self.storage.presigned_get_url(document.storage_object_key)
        if not url:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File object not found")
        return url

    async def chat_messages(self, presale_id: UUID, user: CurrentUser) -> list[PresaleChatMessage]:
        presale = await self.get_owned(presale_id, user)
        return list(presale.chat_messages)

    async def chat(self, presale_id: UUID, user: CurrentUser, message: str) -> list[PresaleChatMessage]:
        presale = await self.get_owned(presale_id, user)
        user_message = PresaleChatMessage(
            presale_id=presale.id,
            role="user",
            content=message,
        )
        answer = await self.ai.chat(self._chat_context(presale, message))
        assistant_message = PresaleChatMessage(
            presale_id=presale.id,
            role="assistant",
            content=answer,
        )
        self.session.add_all([user_message, assistant_message])
        await self.session.commit()
        await self.session.refresh(user_message)
        await self.session.refresh(assistant_message)
        return [user_message, assistant_message]

    async def chat_stream(
        self,
        presale_id: UUID,
        user: CurrentUser,
        message: str,
    ) -> AsyncGenerator[str, None]:
        presale = await self.get_owned(presale_id, user)
        user_message = PresaleChatMessage(
            presale_id=presale.id,
            role="user",
            content=message,
        )
        self.session.add(user_message)
        await self.session.commit()
        await self.session.refresh(user_message)

        answer_parts: list[str] = []
        async for chunk in self.ai.chat_stream(self._chat_context(presale, message)):
            answer_parts.append(chunk)
            yield chunk

        answer = "".join(answer_parts).strip()
        if answer:
            assistant_message = PresaleChatMessage(
                presale_id=presale.id,
                role="assistant",
                content=answer,
            )
            self.session.add(assistant_message)
            await self.session.commit()

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

    def _chat_context(self, presale: PresaleRequest, message: str) -> list[dict]:
        context = {
            "presale": {
                "title": presale.title,
                "customer_name": presale.customer_name,
                "description": presale.description,
                "status": presale.status,
                "desired_outputs": presale.desired_outputs,
            },
            "questions": [
                {"question": item.question, "answer": item.answer}
                for item in presale.questions
            ],
            "documents": [
                {
                    "filename": item.filename,
                    "content_type": item.content_type,
                    "text_content": item.text_content,
                }
                for item in presale.documents
            ],
            "analysis": presale.analysis.payload if presale.analysis else None,
        }
        messages = [
            {
                "role": "user",
                "content": (
                    "Контекст пресейла. Используй его при ответе на вопрос пользователя:\n"
                    f"{context}"
                ),
            }
        ]
        messages.extend(
            {"role": item.role, "content": item.content}
            for item in presale.chat_messages[-20:]
        )
        messages.append({"role": "user", "content": message})
        return messages

    def _extract_text(self, raw: bytes, filename: str, content_type: str | None) -> str:
        name = filename.lower()
        if name.endswith(".docx"):
            return self._extract_docx_text(raw)
        if name.endswith(".xlsx"):
            return self._extract_xlsx_text(raw)
        if content_type and content_type.startswith("text/"):
            return self._clean_text(raw.decode("utf-8", errors="ignore"))
        return ""

    def _extract_docx_text(self, raw: bytes) -> str:
        try:
            with ZipFile(BytesIO(raw)) as archive:
                document = archive.read("word/document.xml")
        except (BadZipFile, KeyError):
            return ""
        return self._xml_text(document)

    def _extract_xlsx_text(self, raw: bytes) -> str:
        try:
            with ZipFile(BytesIO(raw)) as archive:
                sheet_names = [
                    name
                    for name in archive.namelist()
                    if name.startswith("xl/worksheets/") and name.endswith(".xml")
                ]
                parts = [self._xml_text(archive.read(name)) for name in sheet_names]
        except BadZipFile:
            return ""
        return self._clean_text("\n".join(part for part in parts if part))

    def _xml_text(self, raw_xml: bytes) -> str:
        try:
            root = ET.fromstring(raw_xml)
        except ET.ParseError:
            return ""
        return self._clean_text(" ".join(text for text in root.itertext() if text.strip()))

    def _clean_text(self, text: str) -> str:
        return text.replace("\x00", "").strip()

    def _can_send_to_ai(self, filename: str, content_type: str | None) -> bool:
        normalized_type = (content_type or "").split(";", 1)[0].strip().lower()
        suffix = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        return (
            suffix in self.AI_SUPPORTED_EXTENSIONS
            or normalized_type in self.AI_SUPPORTED_CONTENT_TYPES
            or normalized_type.startswith("text/")
        )
