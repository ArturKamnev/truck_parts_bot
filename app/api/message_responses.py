from __future__ import annotations

from app.api.schemas.tickets import MessageResponse
from app.db.models import TicketMessage


def message_response(message: TicketMessage, *, download_base: str) -> MessageResponse:
    has_media = message.content_type != "text"
    return MessageResponse(
        id=message.id,
        ticketId=message.ticket_id,
        senderType=message.sender_type,
        contentType=message.content_type,
        textPreview=message.text_preview,
        captionPreview=message.content if has_media else None,
        createdAt=message.created_at,
        hasMedia=has_media,
        deliveryStatus=message.delivery_status,
        fileName=message.file_name,
        mimeType=message.mime_type,
        fileSize=message.file_size,
        downloadUrl=f"{download_base}/{message.id}/file" if message.file_path else None,
    )
