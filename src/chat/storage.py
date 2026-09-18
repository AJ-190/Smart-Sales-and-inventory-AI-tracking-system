import os
import uuid
from fastapi import UploadFile, HTTPException, status

MEDIA_ROOT = os.environ.get("MEDIA_ROOT", "media")
CHAT_DIR_NAME = "chat"

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp", "image/bmp", "image/svg+xml"}
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg", ".pdf", ".txt", ".csv", ".doc", ".docx", ".xls", ".xlsx", ".zip"}
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB


def _ext_from_filename(filename: str) -> str:
    return os.path.splitext(filename or "")[1].lower()


def is_image(content_type: str, filename: str) -> bool:
    return content_type in ALLOWED_IMAGE_TYPES or _ext_from_filename(filename) in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg"}


async def save_chat_attachment(business_id: int, file: UploadFile) -> dict:
    ext = _ext_from_filename(file.filename or "")
    if ext and ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type not allowed: {ext or 'unknown'}",
        )

    contents = await file.read()
    if len(contents) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File is too large (max 10 MB)",
        )

    rel_dir = os.path.join(CHAT_DIR_NAME, str(business_id))
    abs_dir = os.path.join(MEDIA_ROOT, rel_dir)
    os.makedirs(abs_dir, exist_ok=True)

    name = f"{uuid.uuid4().hex}{ext}"
    abs_path = os.path.join(abs_dir, name)

    with open(abs_path, "wb") as fh:
        fh.write(contents)

    relative_path = f"/media/{rel_dir}/{name}"
    return {
        "attachment_url": relative_path,
        "attachment_type": file.content_type or (_ext_from_filename(file.filename or "") or "file"),
        "attachment_name": file.filename or "file",
        "attachment_size": len(contents),
    }