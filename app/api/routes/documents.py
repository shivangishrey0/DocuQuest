import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.document import Document, DocumentStatus
from app.models.review import ReviewItem
from app.models.user import User
from app.schemas.document import DocumentOut, DocumentStatusOut
from app.schemas.question import ReviewItemOut
from app.services.storage import validate_and_store
from app.workers.tasks import process_document

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])


def _get_owned_document(db: Session, document_id: uuid.UUID, user: User) -> Document:
    document = db.get(Document, document_id)
    if not document or document.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return document


@router.post("/upload", response_model=DocumentOut, status_code=status.HTTP_202_ACCEPTED)
def upload_document(
    file: UploadFile = File(...),
    group_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    document_id = uuid.uuid4()
    stored_path, file_type, size = validate_and_store(file, user.id, document_id)

    document = Document(
        id=document_id,
        owner_id=user.id,
        group_id=group_id,
        original_filename=file.filename,
        stored_path=stored_path,
        file_type=file_type,
        file_size_bytes=size,
        status=DocumentStatus.PENDING,
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    process_document.delay(str(document.id))

    return document


@router.get("", response_model=list[DocumentOut])
def list_documents(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(Document).filter(Document.owner_id == user.id).order_by(Document.created_at.desc()).all()


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(document_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _get_owned_document(db, document_id, user)


@router.get("/{document_id}/status", response_model=DocumentStatusOut)
def get_document_status(document_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _get_owned_document(db, document_id, user)


@router.get("/{document_id}/review-items", response_model=list[ReviewItemOut])
def get_review_items(document_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    document = _get_owned_document(db, document_id, user)
    return db.query(ReviewItem).filter(ReviewItem.document_id == document.id).all()
