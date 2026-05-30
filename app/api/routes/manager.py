from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import (
    get_current_user,
    get_current_user_session,
    get_bot,
    get_authorization_service,
    get_ticket_service,
    get_relay_service,
    get_ui_state_service,
)
from app.api.schemas.tickets import (
    MessageResponse,
    TicketResponse,
    CloseTicketRequest,
    MessageCreateRequest,
)
from app.db.models import Ticket, TicketMessage, User
from app.db.session import get_session
from app.utils.enums import TicketStatus
from app.utils.exceptions import TicketStateError, AuthorizationError, UnsupportedRelayContentError
from aiogram import Bot
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/manager", tags=["manager"])



def verify_manager_or_owner_role(session_payload: dict = Depends(get_current_user_session)) -> None:
    if session_payload["role"] not in ("manager", "owner"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Only managers and owners are allowed to access manager endpoints",
        )


@router.get("/tickets/new", response_model=list[TicketResponse], dependencies=[Depends(verify_manager_or_owner_role)])
async def list_new_tickets(
    session: AsyncSession = Depends(get_session),
) -> list[TicketResponse]:
    """
    Returns a list of all unclaimed (OPEN) tickets.
    """
    stmt = (
        select(Ticket)
        .options(selectinload(Ticket.customer))
        .where(Ticket.status == TicketStatus.OPEN.value)
        .order_by(Ticket.created_at.asc())
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


@router.get("/tickets/active", response_model=list[TicketResponse], dependencies=[Depends(verify_manager_or_owner_role)])
async def list_active_tickets(
    current_user: User = Depends(get_current_user),
    session_payload: dict = Depends(get_current_user_session),
    session: AsyncSession = Depends(get_session),
) -> list[TicketResponse]:
    """
    Returns active (CLAIMED) tickets. 
    Managers only see tickets assigned to themselves; Owners see all claimed tickets.
    """
    role = session_payload["role"]
    stmt = select(Ticket).options(selectinload(Ticket.customer)).where(Ticket.status == TicketStatus.CLAIMED.value)
    
    if role == "manager":
        # Filter strictly by assigned manager
        stmt = stmt.where(Ticket.assigned_manager_telegram_id == current_user.telegram_user_id)
        
    stmt = stmt.order_by(Ticket.claimed_at.desc() if Ticket.claimed_at is not None else Ticket.created_at.desc())
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


@router.get("/tickets/{ticket_id}", response_model=TicketResponse, dependencies=[Depends(verify_manager_or_owner_role)])
async def get_manager_ticket(
    ticket_id: int,
    current_user: User = Depends(get_current_user),
    session_payload: dict = Depends(get_current_user_session),
    session: AsyncSession = Depends(get_session),
) -> TicketResponse:
    """
    Returns the details of a specific ticket.
    Enforces rule: Managers can only read unclaimed OPEN tickets, or tickets assigned to themselves.
    Owners can read any ticket.
    """
    role = session_payload["role"]
    stmt = select(Ticket).options(selectinload(Ticket.customer)).where(Ticket.id == ticket_id)
    ticket = await session.scalar(stmt)
    
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found",
        )
        
    # Check access permission
    if role == "manager":
        is_open = ticket.status == TicketStatus.OPEN.value
        is_assigned_to_me = ticket.assigned_manager_telegram_id == current_user.telegram_user_id
        if not (is_open or is_assigned_to_me):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You are not assigned to this ticket",
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


@router.get("/tickets/{ticket_id}/messages", response_model=list[MessageResponse], dependencies=[Depends(verify_manager_or_owner_role)])
async def list_manager_ticket_messages(
    ticket_id: int,
    limit: int = Query(50, ge=1, le=100),
    after_id: int | None = Query(None, description="Cursor for pagination: only return messages after this message ID"),
    current_user: User = Depends(get_current_user),
    session_payload: dict = Depends(get_current_user_session),
    session: AsyncSession = Depends(get_session),
) -> list[MessageResponse]:
    """
    Returns cursor-paginated messages for a ticket in stable chronological order.
    Enforces the same manager/owner validation checks as the ticket details endpoint.
    """
    role = session_payload["role"]
    ticket = await session.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found",
        )
        
    # Verify access
    if role == "manager":
        is_open = ticket.status == TicketStatus.OPEN.value
        is_assigned_to_me = ticket.assigned_manager_telegram_id == current_user.telegram_user_id
        if not (is_open or is_assigned_to_me):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You are not assigned to this ticket",
            )

    # Query messages
    stmt = select(TicketMessage).where(TicketMessage.ticket_id == ticket_id)
    if after_id is not None:
        stmt = stmt.where(TicketMessage.id > after_id)
        
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
            deliveryStatus=msg.delivery_status,
        )
        for msg in messages
    ]


@router.post("/tickets/{ticket_id}/claim", response_model=TicketResponse, dependencies=[Depends(verify_manager_or_owner_role)])
async def claim_manager_ticket(
    ticket_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    bot: Bot = Depends(get_bot),
    ticket_service: TicketService = Depends(get_ticket_service),
    ui_state_service: UIStateService = Depends(get_ui_state_service),
) -> TicketResponse:
    try:
        ticket = await ticket_service.claim_ticket(
            session,
            ticket_id=ticket_id,
            manager_telegram_id=current_user.telegram_user_id,
        )
        
        # Notify customer
        try:
            await bot.send_message(
                chat_id=ticket.customer.telegram_user_id,
                text=(
                    "К вашему обращению подключился менеджер. "
                    "Теперь вы можете общаться здесь и отправлять файлы."
                ),
            )
        except Exception as exc:
            logger.warning("Failed to send claim message to customer: %s", exc)

        # Update customer keyboard and manager menu in Telegram
        try:
            from app.utils.enums import CustomerMode
            await ui_state_service.show_current_menu(
                bot, session, ticket.customer.telegram_user_id, reason="ticket_claimed_customer"
            )
            await ui_state_service.show_current_menu(
                bot, session, current_user.telegram_user_id, reason="ticket_claimed_manager"
            )
        except Exception as exc:
            logger.warning("Failed to refresh state menus: %s", exc)

        await session.commit()
        
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
    except TicketStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))


@router.post("/tickets/{ticket_id}/close", response_model=TicketResponse, dependencies=[Depends(verify_manager_or_owner_role)])
async def close_manager_ticket(
    ticket_id: int,
    req: CloseTicketRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    bot: Bot = Depends(get_bot),
    ticket_service: TicketService = Depends(get_ticket_service),
    authorization_service: AuthorizationService = Depends(get_authorization_service),
    ui_state_service: UIStateService = Depends(get_ui_state_service),
) -> TicketResponse:
    try:
        ticket = await ticket_service.get_ticket(session, ticket_id=ticket_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")

    is_owner = authorization_service.is_owner(current_user.telegram_user_id)
    is_manager = authorization_service.is_manager(current_user.telegram_user_id)
    
    # Enforce owner supervisor intent
    if is_owner and not req.as_supervisor:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Owner must explicitly act as supervisor to perform write actions",
        )

    # Validate status and assignment rules
    if ticket.status not in {TicketStatus.OPEN.value, TicketStatus.CLAIMED.value}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ticket is already closed or inactive",
        )

    if is_manager and not is_owner:
        # A normal manager cannot close OPEN tickets, and can only close their own CLAIMED tickets
        if ticket.status == TicketStatus.OPEN.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Managers cannot close unclaimed tickets",
            )
        if ticket.assigned_manager_telegram_id != current_user.telegram_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You are not assigned to this ticket",
            )

    # Perform closure
    if is_owner and ticket.status == TicketStatus.OPEN.value:
        ticket = await ticket_service.close_ticket(
            session,
            ticket_id=ticket_id,
            actor_telegram_id=current_user.telegram_user_id,
        )
        ticket_service._audit(
            session,
            event_type="owner_admin_cancellation",
            actor_telegram_id=current_user.telegram_user_id,
            customer_id=ticket.customer_id,
            ticket_id=ticket.id,
            metadata_json={"reason": "Owner forced closure on unclaimed ticket"},
        )
    else:
        ticket = await ticket_service.close_ticket(
            session,
            ticket_id=ticket_id,
            actor_telegram_id=current_user.telegram_user_id,
        )

    # Notify customer
    try:
        from app.utils.enums import CustomerMode
        await bot.send_message(
            chat_id=ticket.customer.telegram_user_id,
            text=(
                "Ваш вопрос закрыт менеджером. "
                "Вы снова можете задавать вопросы AI-помощнику."
            ),
            reply_markup=ui_state_service.keyboard_service.get_customer_keyboard(
                CustomerMode.AI_CHAT.value, ticket.customer.broadcasts_enabled
            ),
        )
    except Exception as exc:
        logger.warning("Failed to send close message to customer: %s", exc)

    # Update keyboards
    try:
        from app.utils.enums import CustomerMode
        await ui_state_service.show_current_menu(
            bot, session, ticket.customer.telegram_user_id, reason="ticket_closed_customer"
        )
        await ui_state_service.show_current_menu(
            bot, session, current_user.telegram_user_id, reason="ticket_closed_manager"
        )
    except Exception as exc:
        logger.warning("Failed to refresh state menus: %s", exc)

    await session.commit()

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


@router.post("/tickets/{ticket_id}/messages", response_model=MessageResponse, dependencies=[Depends(verify_manager_or_owner_role)])
async def send_manager_message(
    ticket_id: int,
    req: MessageCreateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    bot: Bot = Depends(get_bot),
    relay_service: RelayService = Depends(get_relay_service),
    ticket_service: TicketService = Depends(get_ticket_service),
    authorization_service: AuthorizationService = Depends(get_authorization_service),
) -> MessageResponse:
    try:
        ticket = await ticket_service.get_ticket(session, ticket_id=ticket_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")

    is_owner = authorization_service.is_owner(current_user.telegram_user_id)
    is_manager = authorization_service.is_manager(current_user.telegram_user_id)

    # Enforce owner supervisor intent
    if is_owner and not req.as_supervisor:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Owner must explicitly act as supervisor to perform write actions",
        )

    # Check ticket status is active (OPEN or CLAIMED)
    if ticket.status not in {TicketStatus.OPEN.value, TicketStatus.CLAIMED.value}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot send message to a closed or inactive ticket",
        )

    # Check rules:
    # Manager can only send if assigned manager AND ticket status is CLAIMED
    if is_manager and not is_owner:
        if ticket.status != TicketStatus.CLAIMED.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot send messages to an unclaimed OPEN ticket",
            )
        if ticket.assigned_manager_telegram_id != current_user.telegram_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not the assigned manager for this ticket",
            )

    # Try relaying the message
    try:
        await relay_service.relay_manager_message_to_customer(
            bot=bot,
            session=session,
            ticket=ticket,
            actor_telegram_id=current_user.telegram_user_id,
            text=req.text,
        )
    except Exception as exc:
        # Find the specific new TicketMessage in the session to mark failed
        ticket_message = None
        for obj in list(session.new) + list(session.dirty) + list(session.identity_map.values()):
            if isinstance(obj, TicketMessage) and obj.content == req.text:
                ticket_message = obj
                break
        
        if ticket_message:
            ticket_message.delivery_status = "FAILED"
            
        await session.commit()
        
        if ticket_message:
            return MessageResponse(
                id=ticket_message.id or 0,
                ticketId=ticket_message.ticket_id,
                senderType=ticket_message.sender_type,
                contentType=ticket_message.content_type,
                textPreview=ticket_message.text_preview,
                captionPreview=ticket_message.content if ticket_message.content_type != "text" else None,
                createdAt=ticket_message.created_at,
                hasMedia=ticket_message.content_type != "text",
                deliveryStatus=ticket_message.delivery_status,
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Telegram delivery failed: {str(exc)}"
        )
    
    # Success path
    ticket_message = None
    for obj in list(session.new) + list(session.dirty) + list(session.identity_map.values()):
        if isinstance(obj, TicketMessage) and obj.ticket_id == ticket_id and obj.content == req.text:
            ticket_message = obj
            break

    if not ticket_message:
        stmt = select(TicketMessage).where(TicketMessage.ticket_id == ticket_id).order_by(TicketMessage.id.desc()).limit(1)
        ticket_message = await session.scalar(stmt)

    await session.commit()

    return MessageResponse(
        id=ticket_message.id,
        ticketId=ticket_message.ticket_id,
        senderType=ticket_message.sender_type,
        contentType=ticket_message.content_type,
        textPreview=ticket_message.text_preview,
        captionPreview=ticket_message.content if ticket_message.content_type != "text" else None,
        createdAt=ticket_message.created_at,
        hasMedia=ticket_message.content_type != "text",
        deliveryStatus=ticket_message.delivery_status,
    )

