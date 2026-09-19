import uuid

from pydantic import BaseModel

from app.models.question import QuestionStatus, QuestionType


class OptionOut(BaseModel):
    label: str
    text: str


class QuestionOut(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    question_number: str | None
    question_text: str
    options: list[dict]
    question_type: QuestionType
    images: list[str]
    answer: str | None
    answer_confidence: float | None
    answer_source: str | None
    source_pages: list[int]
    spans_multiple_pages: bool
    confidence: float
    status: QuestionStatus

    class Config:
        from_attributes = True


class AnswerKeyEntryOut(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    question_number: str
    answer_text: str
    source_page: int | None
    confidence: float
    matched_question_id: uuid.UUID | None

    class Config:
        from_attributes = True


class ReviewItemOut(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    question_id: uuid.UUID | None
    type: str
    severity: str
    message: str

    class Config:
        from_attributes = True
