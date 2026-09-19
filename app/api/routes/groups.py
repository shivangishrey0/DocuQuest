import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.document import Document, DocumentGroup
from app.models.user import User
from app.schemas.document import DocumentGroupCreate, DocumentGroupOut, AddDocumentToGroup

router = APIRouter(prefix="/api/v1/groups", tags=["document-groups"])


def _to_out(group: DocumentGroup) -> DocumentGroupOut:
    return DocumentGroupOut(
        id=group.id,
        name=group.name,
        created_at=group.created_at,
        document_ids=[d.id for d in group.documents],
    )


@router.post("", response_model=DocumentGroupOut, status_code=status.HTTP_201_CREATED)
def create_group(payload: DocumentGroupCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    group = DocumentGroup(owner_id=user.id, name=payload.name)
    db.add(group)
    db.commit()
    db.refresh(group)
    return _to_out(group)


@router.get("", response_model=list[DocumentGroupOut])
def list_groups(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    groups = db.query(DocumentGroup).filter(DocumentGroup.owner_id == user.id).all()
    return [_to_out(g) for g in groups]


@router.get("/{group_id}", response_model=DocumentGroupOut)
def get_group(group_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    group = db.get(DocumentGroup, group_id)
    if not group or group.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    return _to_out(group)


@router.post("/{group_id}/documents", response_model=DocumentGroupOut)
def add_document_to_group(
    group_id: uuid.UUID,
    payload: AddDocumentToGroup,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    group = db.get(DocumentGroup, group_id)
    if not group or group.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    document = db.get(Document, payload.document_id)
    if not document or document.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    document.group_id = group.id
    for q in document.questions:
        q.group_id = group.id
    for a in document.answer_key_entries:
        a.group_id = group.id
    db.commit()
    db.refresh(group)
    return _to_out(group)
