from __future__ import annotations

import re
import os
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from aiogram import Bot
from aiogram.types import FSInputFile, Message
from fastapi import HTTPException, UploadFile, status

from app.config import Settings
from app.utils.enums import TicketMessageContentType

ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
    "video/mp4",
    "video/webm",
    "video/quicktime",
    "audio/mpeg",
    "audio/mp4",
    "audio/ogg",
    "audio/wav",
    "application/pdf",
    "text/plain",
    "text/csv",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


@dataclass(frozen=True)
class StoredUpload:
    path: str
    file_name: str
    mime_type: str
    file_size: int
    content_type: TicketMessageContentType


def content_type_for_mime(mime_type: str) -> TicketMessageContentType:
    if mime_type.startswith("image/"):
        return TicketMessageContentType.PHOTO
    if mime_type.startswith("video/"):
        return TicketMessageContentType.VIDEO
    if mime_type.startswith("audio/"):
        return TicketMessageContentType.AUDIO
    return TicketMessageContentType.DOCUMENT


def safe_file_name(file_name: str | None) -> str:
    clean = Path(file_name or "upload").name
    clean = re.sub(r"[^A-Za-z0-9._ -]+", "_", clean).strip(" .")
    return clean[:180] or "upload"


async def store_upload(file: UploadFile, settings: Settings) -> StoredUpload:
    mime_type = (file.content_type or "application/octet-stream").split(";")[0].strip().lower()
    if mime_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported file type",
        )

    file_name = safe_file_name(file.filename)
    root = os.path.abspath(settings.miniapp_media_storage_dir)
    os.makedirs(root, exist_ok=True)
    extension = Path(file_name).suffix[:16]
    destination = Path(os.path.join(root, f"{uuid4().hex}{extension}"))

    max_bytes = settings.miniapp_max_upload_bytes
    total = 0
    with destination.open("wb") as handle:
        while chunk := await file.read(1024 * 1024):
            total += len(chunk)
            if total > max_bytes:
                handle.close()
                destination.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="File is too large",
                )
            handle.write(chunk)

    if total == 0:
        destination.unlink(missing_ok=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File is empty")

    return StoredUpload(
        path=str(destination),
        file_name=file_name,
        mime_type=mime_type,
        file_size=total,
        content_type=content_type_for_mime(mime_type),
    )


async def send_stored_upload(
    bot: Bot,
    *,
    chat_id: int,
    upload: StoredUpload,
    caption: str | None = None,
    reply_markup=None,
) -> Message:
    input_file = FSInputFile(upload.path, filename=upload.file_name)
    clean_caption = caption.strip()[:1024] if caption and caption.strip() else None
    if upload.content_type == TicketMessageContentType.PHOTO:
        return await bot.send_photo(
            chat_id=chat_id, photo=input_file, caption=clean_caption, reply_markup=reply_markup
        )
    if upload.content_type == TicketMessageContentType.VIDEO:
        return await bot.send_video(
            chat_id=chat_id, video=input_file, caption=clean_caption, reply_markup=reply_markup
        )
    if upload.content_type == TicketMessageContentType.AUDIO:
        return await bot.send_audio(
            chat_id=chat_id, audio=input_file, caption=clean_caption, reply_markup=reply_markup
        )
    return await bot.send_document(
        chat_id=chat_id, document=input_file, caption=clean_caption, reply_markup=reply_markup
    )


def extract_sent_file_ids(message: Message) -> tuple[str | None, str | None]:
    media = None
    if getattr(message, "photo", None):
        media = message.photo[-1]
    else:
        for attr in ("video", "document", "animation", "audio", "voice", "video_note"):
            media = getattr(message, attr, None)
            if media is not None:
                break
    return getattr(media, "file_id", None), getattr(media, "file_unique_id", None)
