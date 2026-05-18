from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PresaleCreate(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    customer_name: str | None = Field(default=None, max_length=255)
    desired_outputs: list[str] = Field(default_factory=list)


class PresaleRead(BaseModel):
    id: UUID
    owner_id: UUID
    title: str
    customer_name: str | None
    status: str
    desired_outputs: list[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentRead(BaseModel):
    id: UUID
    filename: str
    content_type: str | None
    storage_bucket: str | None = None
    storage_object_key: str | None = None
    size_bytes: int | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SpecialistRateInput(BaseModel):
    role: str = Field(min_length=2, max_length=100)
    grade: str = Field(min_length=2, max_length=50)
    hourly_rate: float = Field(gt=0)


class SpecialistRateRead(SpecialistRateInput):
    id: UUID

    model_config = ConfigDict(from_attributes=True)


class QuestionRead(BaseModel):
    id: UUID
    question: str
    answer: str | None

    model_config = ConfigDict(from_attributes=True)


class AnswerInput(BaseModel):
    question_id: UUID
    answer: str = Field(min_length=1)


class AnalysisRead(BaseModel):
    id: UUID
    payload: dict
    report_markdown: str

    model_config = ConfigDict(from_attributes=True)


class EstimateHistoryRead(BaseModel):
    presale: PresaleRead
    questions: list[QuestionRead]
    documents: list[DocumentRead]
    analysis: AnalysisRead | None
