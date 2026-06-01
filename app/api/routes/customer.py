from __future__ import annotations

import logging
import os

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import (
    get_current_user,
    get_current_user_session,
    get_bot,
    get_ticket_service,
    get_relay_service,
)
from app.api.message_responses import message_response
from app.api.schemas.tickets import (
    MessageResponse,
    TicketResponse,
    CreateTicketRequest,
    MessageCreateRequest,
)
from app.config import Settings, get_settings
from app.db.models import Ticket, TicketMessage, User
from app.db.session import get_session
from app.services.media_service import extract_sent_file_ids, send_stored_upload, store_upload
from app.utils.enums import TicketMessageDeliveryStatus, TicketMessageSenderType
from app.utils.exceptions import DuplicateActiveTicketError

router = APIRouter(prefix="/customer", tags=["customer"])
logger = logging.getLogger(__name__)


def _customer_download_base(ticket_id: int) -> str:
    return f"/api/customer/tickets/{ticket_id}/messages"


def verify_customer_role(session_payload: dict = Depends(get_current_user_session)) -> None:
    if session_payload["role"] != "customer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Only customers are allowed to access customer endpoints",
        )


@router.get("/tickets", response_model=list[TicketResponse], dependencies=[Depends(verify_customer_role)])
async def list_customer_tickets(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[TicketResponse]:
    """
    Returns list of tickets belonging to the authenticated customer.
    """
    stmt = (
        select(Ticket)
        .options(selectinload(Ticket.customer))
        .where(Ticket.customer_id == current_user.id)
        .order_by(Ticket.created_at.desc())
    )
    result = await session.scalars(stmt)
    tickets = result.all()
    
    return [
        TicketResponse(
            id=ticket.id,
            customer_id=ticket.customer_id,
            status=ticket.status,
            assigned_manager_telegram_id=ticket.assigned_manager_telegram_id,
            created_at=ticket.created_at,
            claimed_at=ticket.claimed_at,
            closed_at=ticket.closed_at,
            customer_username=ticket.customer.username,
            customer_first_name=ticket.customer.first_name,
            customer_last_name=ticket.customer.last_name,
        )
        for ticket in tickets
    ]


@router.get("/tickets/{ticket_id}", response_model=TicketResponse, dependencies=[Depends(verify_customer_role)])
async def get_customer_ticket(
    ticket_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> TicketResponse:
    """
    Returns details of a specific ticket if it belongs to the authenticated customer.
    """
    stmt = (
        select(Ticket)
        .options(selectinload(Ticket.customer))
        .where(Ticket.id == ticket_id)
    )
    ticket = await session.scalar(stmt)
    
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found",
        )
        
    if ticket.customer_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You do not own this ticket",
        )
        
    return TicketResponse(
        id=ticket.id,
        customer_id=ticket.customer_id,
        status=ticket.status,
        assigned_manager_telegram_id=ticket.assigned_manager_telegram_id,
        created_at=ticket.created_at,
        claimed_at=ticket.claimed_at,
        closed_at=ticket.closed_at,
        customer_username=ticket.customer.username,
        customer_first_name=ticket.customer.first_name,
        customer_last_name=ticket.customer.last_name,
    )


@router.get("/tickets/{ticket_id}/messages", response_model=list[MessageResponse], dependencies=[Depends(verify_customer_role)])
async def list_customer_ticket_messages(
    ticket_id: int,
    limit: int = Query(50, ge=1, le=100),
    after_id: int | None = Query(None, description="Cursor for pagination: only return messages after this message ID"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[MessageResponse]:
    """
    Returns cursor-paginated messages for a customer's ticket in stable chronological order.
    """
    # 1. Verify ownership of ticket
    ticket = await session.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found",
        )
    if ticket.customer_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You do not own this ticket",
        )

    # 2. Query messages
    stmt = (
        select(TicketMessage)
        .where(TicketMessage.ticket_id == ticket_id)
    )
    if after_id is not None:
        stmt = stmt.where(TicketMessage.id > after_id)
        
    # Return in stable chronological order (ascending)
    stmt = stmt.order_by(TicketMessage.id.asc()).limit(limit)
    
    result = await session.scalars(stmt)
    messages = result.all()
    
    return [message_response(msg, download_base=_customer_download_base(ticket_id)) for msg in messages]


@router.post("/tickets", response_model=TicketResponse, dependencies=[Depends(verify_customer_role)])
async def create_customer_ticket(
    req: CreateTicketRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    ticket_service=Depends(get_ticket_service),
    relay_service=Depends(get_relay_service),
    bot=Depends(get_bot),
) -> TicketResponse:
    """
    Creates a new ticket for the customer if they do not have an active one.
    """
    try:
        ticket = await ticket_service.create_ticket(
            session,
            customer=current_user,
            original_request=req.initialMessage,
        )
        await session.commit()
    except DuplicateActiveTicketError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    
    # Notify managers about new ticket
    try:
        await relay_service.notify_managers_about_new_ticket(bot, session, ticket=ticket)
    except Exception as e:
        logger.error(f"Failed to notify managers about ticket {ticket.id}: {e}")

    return TicketResponse(
        id=ticket.id,
        customer_id=ticket.customer_id,
        status=ticket.status,
        assigned_manager_telegram_id=ticket.assigned_manager_telegram_id,
        created_at=ticket.created_at,
        claimed_at=ticket.claimed_at,
        closed_at=ticket.closed_at,
        customer_username=current_user.username,
        customer_first_name=current_user.first_name,
        customer_last_name=current_user.last_name,
    )


@router.post("/tickets/{ticket_id}/messages", response_model=MessageResponse, dependencies=[Depends(verify_customer_role)])
async def create_customer_message(
    ticket_id: int,
    req: MessageCreateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    ticket_service=Depends(get_ticket_service),
    relay_service=Depends(get_relay_service),
    bot=Depends(get_bot),
) -> MessageResponse:
    """
    Sends a message from a customer to their own active ticket.
    """
    ticket = await ticket_service.get_ticket(session, ticket_id=ticket_id)
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found",
        )
    if ticket.customer_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You do not own this ticket",
        )
        
    if ticket.status not in ("OPEN", "CLAIMED"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot send message to a closed or cancelled ticket",
        )
        
    await relay_service.relay_customer_message(
        bot,
        session,
        ticket=ticket,
        customer=current_user,
        text=req.text,
    )
    await session.commit()
    
    # Fetch the newly created message
    stmt = (
        select(TicketMessage)
        .where(TicketMessage.ticket_id == ticket.id)
        .order_by(TicketMessage.id.desc())
        .limit(1)
    )
    msg = await session.scalar(stmt)
    if not msg:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save message",
        )
        
    return message_response(msg, download_base=_customer_download_base(ticket.id))


@router.post(
    "/tickets/{ticket_id}/messages/upload",
    response_model=MessageResponse,
    dependencies=[Depends(verify_customer_role)],
)
async def upload_customer_ticket_file(
    ticket_id: int,
    file: UploadFile = File(...),
    caption: str | None = Form(None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    ticket_service=Depends(get_ticket_service),
    bot=Depends(get_bot),
) -> MessageResponse:
    ticket = await ticket_service.get_ticket(session, ticket_id=ticket_id)
    if ticket.customer_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You do not own this ticket",
        )
    if ticket.status not in ("OPEN", "CLAIMED"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot send files to a closed or cancelled ticket",
        )

    upload = await store_upload(file, settings)
    clean_caption = (caption or "").strip()
    content = clean_caption or upload.file_name
    message = ticket_service.add_ticket_message(
        session,
        ticket=ticket,
        sender_type=TicketMessageSenderType.CUSTOMER,
        sender_telegram_id=current_user.telegram_user_id,
        content=content,
        content_type=upload.content_type,
        text_preview=content,
        delivery_status=TicketMessageDeliveryStatus.STORED,
        file_name=upload.file_name,
        mime_type=upload.mime_type,
        file_size=upload.file_size,
        file_path=upload.path,
    )
    await session.flush()

    destination_ids: list[int] = []
    if ticket.status == "CLAIMED" and ticket.assigned_manager_telegram_id:
        destination_ids = [ticket.assigned_manager_telegram_id]
    elif ticket.status == "OPEN":
        destination_ids = await ticket_service.selected_owner_ids_for_ticket(session, ticket_id=ticket.id)

    delivered = True
    for destination_id in destination_ids:
        try:
            sent = await send_stored_upload(
                bot,
                chat_id=destination_id,
                upload=upload,
                caption=f"Ticket #{ticket.id}: {content}",
            )
            file_id, file_unique_id = extract_sent_file_ids(sent)
            message.file_id = message.file_id or file_id
            message.file_unique_id = message.file_unique_id or file_unique_id
        except Exception as exc:
            logger.warning("Failed to relay customer upload ticket_id=%s: %s", ticket.id, exc)
            delivered = False

    message.delivery_status = (
        TicketMessageDeliveryStatus.DELIVERED.value
        if destination_ids and delivered
        else TicketMessageDeliveryStatus.FAILED.value
        if destination_ids
        else TicketMessageDeliveryStatus.STORED.value
    )
    await session.commit()
    await session.refresh(message)
    return message_response(message, download_base=_customer_download_base(ticket.id))


@router.get(
    "/tickets/{ticket_id}/messages/{message_id}/file",
    dependencies=[Depends(verify_customer_role)],
)
async def download_customer_ticket_file(
    ticket_id: int,
    message_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    ticket = await session.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    if ticket.customer_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    message = await session.get(TicketMessage, message_id)
    if not message or message.ticket_id != ticket_id or not message.file_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    if not os.path.isfile(message.file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    return FileResponse(
        message.file_path,
        media_type=message.mime_type or "application/octet-stream",
        filename=message.file_name or "attachment",
    )


class BroadcastToggleRequest(BaseModel):
    enabled: bool


@router.post("/profile/broadcast-toggle", response_model=bool, dependencies=[Depends(verify_customer_role)])
async def toggle_broadcast(
    req: BroadcastToggleRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> bool:
    """
    Toggles the broadcast subscription opt-in setting for the current customer.
    """
    current_user.broadcasts_enabled = req.enabled
    await session.commit()
    return current_user.broadcasts_enabled
