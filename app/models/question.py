import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, ForeignKey, Integer, Text, Enum as SAEnum, Float
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class QuestionStatus(str, enum.Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    REVIEW = "review"


class QuestionType(str, enum.Enum):
    MCQ_SINGLE = "mcq_single"
    MCQ_MULTI = "mcq_multi"
    TRUE_FALSE = "true_false"
    SHORT_ANSWER = "short_answer"
    UNKNOWN = "unknown"


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False, index=True)
    group_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("document_groups.id"), nullable=True, index=True)

    question_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    question_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    options: Mapped[list] = mapped_column(JSONB, default=list)  # [{"label": "A", "text": "..."}]
    question_type: Mapped[QuestionType] = mapped_column(
        SAEnum(QuestionType, name="question_type", values_callable=lambda x: [e.value for e in x]), default=QuestionType.UNKNOWN
    )
    images: Mapped[list] = mapped_column(JSONB, default=list)  # list of stored image paths associated with the question

    answer: Mapped[str | None] = mapped_column(String(512), nullable=True)
    answer_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    answer_source: Mapped[str | None] = mapped_column(String(64), nullable=True)  # e.g. "answer_key_doc:<id>" | "inline"

    source_pages: Mapped[list] = mapped_column(JSONB, default=list)  # [page_number, ...]
    spans_multiple_pages: Mapped[bool] = mapped_column(default=False)

    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[QuestionStatus] = mapped_column(
        SAEnum(QuestionStatus, name="question_status", values_callable=lambda x: [e.value for e in x]), default=QuestionStatus.REVIEW
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    document = relationship("Document", back_populates="questions")


class AnswerKeyEntry(Base):
    """A raw parsed row from an answer-key section/document, before/after matching to a Question."""

    __tablename__ = "answer_key_entries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False, index=True)
    group_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("document_groups.id"), nullable=True, index=True)

    question_number: Mapped[str] = mapped_column(String(32), nullable=False)
    answer_text: Mapped[str] = mapped_column(String(512), nullable=False)
    raw_line: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    matched_question_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("questions.id"), nullable=True)

    document = relationship("Document", back_populates="answer_key_entries")
