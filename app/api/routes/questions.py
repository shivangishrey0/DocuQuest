import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.document import Document
from app.models.question import Question, AnswerKeyEntry, QuestionStatus
from app.models.user import User
from app.schemas.question import QuestionOut, AnswerKeyEntryOut

router = APIRouter(prefix="/api/v1", tags=["questions"])


def _assert_document_owned(db: Session, document_id: uuid.UUID, user: User) -> Document:
    document = db.get(Document, document_id)
    if not document or document.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return document


@router.get("/documents/{document_id}/questions", response_model=list[QuestionOut])
def list_questions_for_document(
    document_id: uuid.UUID,
    status_filter: QuestionStatus | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _assert_document_owned(db, document_id, user)
    q = db.query(Question).filter(Question.document_id == document_id)
    if status_filter:
        q = q.filter(Question.status == status_filter)
    return q.order_by(Question.question_number).all()


@router.get("/questions/{question_id}", response_model=QuestionOut)
def get_question(question_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    question = db.get(Question, question_id)
    if not question:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
    _assert_document_owned(db, question.document_id, user)
    return question


@router.get("/documents/{document_id}/answer-key", response_model=list[AnswerKeyEntryOut])
def get_answer_key(document_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _assert_document_owned(db, document_id, user)
    return db.query(AnswerKeyEntry).filter(AnswerKeyEntry.document_id == document_id).all()


@router.get("/groups/{group_id}/questions", response_model=list[QuestionOut])
def list_questions_for_group(group_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from app.models.document import DocumentGroup

    group = db.get(DocumentGroup, group_id)
    if not group or group.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    return db.query(Question).filter(Question.group_id == group_id).order_by(Question.question_number).all()
