from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import Message

from app.db.session import SessionLocal
from app.filters.roles import IsSupport
from app.keyboards.manager import (
    MANAGER_ACTIVE_CHATS,
    MANAGER_NEW_TICKETS,
    MANAGER_NOTIFICATIONS,
    MANAGER_STATS,
    active_ticket_keyboard,
    manager_keyboard,
    notification_keyboard,
    ticket_claim_keyboard,
)
from app.services.authorization_service import AuthorizationService
from app.services.broadcast_service import BroadcastService
from app.services.relay_service import RelayService
from app.services.statistics_service import StatisticsService
from app.services.ticket_service import TicketService
from app.utils.exceptions import AuthorizationError, UnsupportedRelayContentError

logger = logging.getLogger(__name__)
router = Router(name="manager")

MANAGER_MENU_TEXTS = {
    MANAGER_NEW_TICKETS,
    MANAGER_ACTIVE_CHATS,
    MANAGER_STATS,
    MANAGER_NOTIFICATIONS,
}


@router.message(IsSupport(), Command("mystats"))
@router.message(IsSupport(), F.text == MANAGER_STATS, F.chat.type == "private")
async def manager_stats(
    message: Message,
    authorization: AuthorizationService,
    statistics_service: StatisticsService,
) -> None:
    if message.from_user is None:
        return
    role = authorization.detect_role(message.from_user.id)
    logger.info(
        "private_message_route user_id=%s role=%s route=manager_stats",
        message.from_user.id,
        role,
    )
    async with SessionLocal() as session:
        stats = await statistics_service.manager_stats(
            session, manager_telegram_id=message.from_user.id
        )
    await message.answer(
        "Ваша статистика:\n"
        f"Взято обращений: {stats['claimed_tickets']}\n"
        f"Закрыто обращений: {stats['closed_tickets']}\n"
        f"Активных сейчас: {stats['active_tickets']}",
        reply_markup=manager_keyboard(),
    )


@router.message(IsSupport(), F.text == MANAGER_NEW_TICKETS, F.chat.type == "private")
async def manager_new_tickets(
    message: Message,
    authorization: AuthorizationService,
    ticket_service: TicketService,
) -> None:
    if message.from_user is None:
        return
    if not authorization.is_manager(message.from_user.id) and not authorization.is_owner(
        message.from_user.id
    ):
        return
    role = authorization.detect_role(message.from_user.id)
    logger.info(
        "private_message_route user_id=%s role=%s route=manager_new_tickets",
        message.from_user.id,
        role,
    )
    async with SessionLocal() as session:
        tickets = await ticket_service.list_open_tickets(session)
        previews = [
            (
                ticket,
                await ticket_service.get_recent_ticket_messages(
                    session, ticket_id=ticket.id, limit=3
                ),
            )
            for ticket in tickets
        ]
    if not previews:
        await message.answer("Новых обращений нет.", reply_markup=manager_keyboard())
        return
    for ticket, recent_messages in previews:
        await message.answer(
            _ticket_queue_text(ticket, recent_messages),
            reply_markup=ticket_claim_keyboard(ticket.id),
        )


@router.message(IsSupport(), F.text == MANAGER_ACTIVE_CHATS, F.chat.type == "private")
async def manager_active_chats(
    message: Message,
    authorization: AuthorizationService,
    ticket_service: TicketService,
) -> None:
    if message.from_user is None:
        return
    role = authorization.detect_role(message.from_user.id)
    logger.info(
        "private_message_route user_id=%s role=%s route=manager_active_chats",
        message.from_user.id,
        role,
    )
    async with SessionLocal() as session:
        if authorization.is_owner(message.from_user.id):
            tickets = await ticket_service.list_active_tickets(session)
        else:
            tickets = await ticket_service.list_manager_active_tickets(
                session, manager_telegram_id=message.from_user.id
            )
    if not tickets:
        await message.answer("Активных диалогов нет.", reply_markup=manager_keyboard())
        return
    for ticket in tickets:
        await message.answer(
            _active_ticket_text(ticket),
            reply_markup=active_ticket_keyboard(ticket.id),
        )


@router.message(IsSupport(), F.text == MANAGER_NOTIFICATIONS, F.chat.type == "private")
async def manager_notifications(
    message: Message,
    ticket_service: TicketService,
) -> None:
    if message.from_user is None:
        return
    async with SessionLocal() as session, session.begin():
        enabled = await ticket_service.get_manager_notifications_enabled(
            session, manager_telegram_id=message.from_user.id
        )
    status = "включены" if enabled else "выключены"
    await message.answer(
        f"Уведомления о новых обращениях сейчас {status}.",
        reply_markup=notification_keyboard(enabled),
    )


@router.message(IsSupport(), F.chat.type == "private")
async def manager_private_message(
    message: Message,
    bot: Bot,
    authorization: AuthorizationService,
    broadcast_service: BroadcastService,
    ticket_service: TicketService,
    relay_service: RelayService,
) -> None:
    if message.from_user is None:
        return
    if message.text in MANAGER_MENU_TEXTS:
        return
    if message.text and message.text.startswith("/"):
        return

    async with SessionLocal() as session, session.begin():
        if authorization.is_owner(message.from_user.id):
            owner_state = await broadcast_service.active_owner_state(
                session, owner_telegram_id=message.from_user.id
            )
            if owner_state is not None:
                return
        ticket = await ticket_service.get_selected_ticket(
            session, operator_telegram_id=message.from_user.id
        )
        role = authorization.detect_role(message.from_user.id)
        logger.info(
            "private_message_route user_id=%s role=%s route=manager_message "
            "selected_ticket_id=%s",
            message.from_user.id,
            role,
            ticket.id if ticket else None,
        )
        if ticket is None:
            await message.answer(
                "Выберите активный диалог в меню, чтобы отправить сообщение клиенту.",
                reply_markup=manager_keyboard(),
            )
            return
        try:
            await relay_service.relay_manager_message_to_customer(
                bot,
                session,
                ticket=ticket,
                actor_telegram_id=message.from_user.id,
                message=message,
            )
        except AuthorizationError:
            await message.answer("Недостаточно прав для ответа в этом обращении.")
            return
        except UnsupportedRelayContentError as exc:
            await message.answer(str(exc))
            return
    await message.answer("Сообщение отправлено клиенту.")


def _ticket_queue_text(ticket, recent_messages) -> str:
    username = f" @{ticket.customer.username}" if ticket.customer.username else ""
    latest_message = next((message for message in reversed(recent_messages)), None)
    latest = (
        latest_message.text_preview or latest_message.content
        if latest_message is not None
        else "Нет сообщений"
    )
    return (
        f"Обращение #{ticket.id}\n"
        f"Клиент: {RelayService.customer_display_name(ticket.customer)}{username}\n"
        f"Создано: {ticket.created_at:%Y-%m-%d %H:%M}\n\n"
        f"Последнее сообщение:\n{latest[:1000]}"
    )


def _active_ticket_text(ticket) -> str:
    username = f" @{ticket.customer.username}" if ticket.customer.username else ""
    return (
        f"💬 Обращение #{ticket.id}\n"
        f"Клиент: {RelayService.customer_display_name(ticket.customer)}{username}\n"
        "Статус: В работе\n\n"
        "Откройте диалог, чтобы включить безопасный режим ответа."
    )
