import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.document import DocumentStatus, DocumentRole


class DocumentOut(BaseModel):
    id: uuid.UUID
    group_id: uuid.UUID | None
    original_filename: str
    file_type: str
    file_size_bytes: int
    status: DocumentStatus
    role: DocumentRole
    is_scanned: bool | None
    page_count: int | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DocumentStatusOut(BaseModel):
    id: uuid.UUID
    status: DocumentStatus
    page_count: int | None
    error_message: str | None
    updated_at: datetime

    class Config:
        from_attributes = True


class PageOut(BaseModel):
    page_number: int
    extraction_method: str
    ocr_confidence: float | None
    rotation_applied: int

    class Config:
        from_attributes = True


class DocumentGroupCreate(BaseModel):
    name: str = "Untitled group"


class DocumentGroupOut(BaseModel):
    id: uuid.UUID
    name: str
    created_at: datetime
    document_ids: list[uuid.UUID] = []

    class Config:
        from_attributes = True


class AddDocumentToGroup(BaseModel):
    document_id: uuid.UUID
