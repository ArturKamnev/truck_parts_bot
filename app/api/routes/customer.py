from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import get_current_user, get_current_user_session
from app.api.schemas.tickets import MessageResponse, TicketResponse
from app.db.models import Ticket, TicketMessage, User
from app.db.session import get_session

router = APIRouter(prefix="/customer", tags=["customer"])


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
    
    return [
        MessageResponse(
            id=msg.id,
            ticketId=msg.ticket_id,
            senderType=msg.sender_type,
            contentType=msg.content_type,
            textPreview=msg.text_preview,
            captionPreview=msg.content if msg.content_type != "text" else None,
            createdAt=msg.created_at,
            hasMedia=msg.content_type != "text",
        )
        for msg in messages
    ]
