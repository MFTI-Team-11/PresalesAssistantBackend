from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class PresaleRequest(Base):
    __tablename__ = "presale_requests"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), index=True)
    title: Mapped[str] = mapped_column(String(255))
    customer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="draft")
    desired_outputs: Mapped[list[str]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    documents = relationship("PresaleDocument", back_populates="presale", cascade="all, delete-orphan")
    rates = relationship("SpecialistRate", back_populates="presale", cascade="all, delete-orphan")
    questions = relationship("PreAnalysisQuestion", back_populates="presale", cascade="all, delete-orphan")
    analysis = relationship(
        "PresaleAnalysis", back_populates="presale", cascade="all, delete-orphan", uselist=False
    )


class PresaleDocument(Base):
    __tablename__ = "presale_documents"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    presale_id: Mapped[UUID] = mapped_column(
        ForeignKey("presale_requests.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    text_content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    presale = relationship("PresaleRequest", back_populates="documents")


class SpecialistRate(Base):
    __tablename__ = "specialist_rates"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    presale_id: Mapped[UUID] = mapped_column(
        ForeignKey("presale_requests.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(100))
    grade: Mapped[str] = mapped_column(String(50))
    hourly_rate: Mapped[float] = mapped_column(Numeric(12, 2))

    presale = relationship("PresaleRequest", back_populates="rates")


class PreAnalysisQuestion(Base):
    __tablename__ = "pre_analysis_questions"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    presale_id: Mapped[UUID] = mapped_column(
        ForeignKey("presale_requests.id", ondelete="CASCADE"), index=True
    )
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    presale = relationship("PresaleRequest", back_populates="questions")


class PresaleAnalysis(Base):
    __tablename__ = "presale_analyses"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    presale_id: Mapped[UUID] = mapped_column(
        ForeignKey("presale_requests.id", ondelete="CASCADE"), unique=True, index=True
    )
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    report_markdown: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    presale = relationship("PresaleRequest", back_populates="analysis")
