import os
import uuid
from pathlib import Path

from fastapi import UploadFile, HTTPException, status

from app.config import settings

MAGIC_BYTES = {
    b"%PDF": "pdf",
    b"\xff\xd8\xff": "jpg",
    b"\x89PNG\r\n\x1a\n": "png",
}


def _sniff_file_type(head: bytes) -> str | None:
    for magic, ftype in MAGIC_BYTES.items():
        if head.startswith(magic):
            return ftype
    return None


def validate_and_store(upload: UploadFile, user_id: uuid.UUID, document_id: uuid.UUID) -> tuple[str, str, int]:
    """Validates extension/magic-bytes/size, then writes the file to a per-user,
    per-document directory. Returns (stored_path, file_type, size_bytes)."""

    ext = Path(upload.filename or "").suffix.lower().lstrip(".")
    if ext not in settings.allowed_extensions_set:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file extension '.{ext}'. Allowed: {sorted(settings.allowed_extensions_set)}",
        )

    head = upload.file.read(8)
    upload.file.seek(0)
    sniffed = _sniff_file_type(head)
    if sniffed is None or (sniffed == "jpg" and ext not in ("jpg", "jpeg")) or (sniffed != "jpg" and sniffed != ext):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="File content does not match its extension (failed magic-byte check).",
        )

    user_dir = Path(settings.STORAGE_ROOT) / str(user_id) / str(document_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    dest_path = user_dir / f"original.{ext}"

    size = 0
    max_size = settings.max_upload_size_bytes
    with open(dest_path, "wb") as f:
        while chunk := upload.file.read(1024 * 1024):
            size += len(chunk)
            if size > max_size:
                f.close()
                os.remove(dest_path)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File exceeds max size of {settings.MAX_UPLOAD_SIZE_MB}MB",
                )
            f.write(chunk)

    if size == 0:
        os.remove(dest_path)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty")

    return str(dest_path), ext, size


def page_image_dir(user_id: uuid.UUID, document_id: uuid.UUID) -> Path:
    d = Path(settings.STORAGE_ROOT) / str(user_id) / str(document_id) / "pages"
    d.mkdir(parents=True, exist_ok=True)
    return d
