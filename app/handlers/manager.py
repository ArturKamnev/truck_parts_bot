# ruff: noqa: E501
from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import Message

from app.db.models import OperatorSession
from app.db.session import SessionLocal
from app.filters.roles import IsSupport
from app.keyboards.constants import (
    MANAGER_ACTIVE_CHATS,
    MANAGER_CLOSE_TICKET,
    MANAGER_EXIT_REPLY,
    MANAGER_MY_DIALOGS,
    MANAGER_NEW_TICKETS,
    MANAGER_NOTIFICATIONS_OFF,
    MANAGER_NOTIFICATIONS_ON,
    MANAGER_STATS,
)
from app.keyboards.inline import (
    active_ticket_keyboard,
    ticket_claim_keyboard,
)
from app.services.authorization_service import AuthorizationService
from app.services.broadcast_service import BroadcastService
from app.services.relay_service import RelayService
from app.services.statistics_service import StatisticsService
from app.services.ticket_service import TicketService
from app.services.ui_state_service import UIStateService
from app.utils.enums import CustomerMode
from app.utils.exceptions import AuthorizationError, UnsupportedRelayContentError

logger = logging.getLogger(__name__)
router = Router(name="manager")

MANAGER_MENU_TEXTS = {
    MANAGER_NEW_TICKETS,
    MANAGER_ACTIVE_CHATS,
    MANAGER_STATS,
    MANAGER_NOTIFICATIONS_ON,
    MANAGER_NOTIFICATIONS_OFF,
    MANAGER_CLOSE_TICKET,
    MANAGER_EXIT_REPLY,
    MANAGER_MY_DIALOGS,
}


@router.message(IsSupport(), Command("mystats"))
@router.message(IsSupport(), F.text == MANAGER_STATS, F.chat.type == "private")
async def manager_stats(
    message: Message,
    bot: Bot,
    authorization: AuthorizationService,
    statistics_service: StatisticsService,
    ui_state_service: UIStateService,
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
        text = (
            "Ваша статистика:\n"
            f"Взято обращений: {stats['claimed_tickets']}\n"
            f"Закрыто обращений: {stats['closed_tickets']}\n"
            f"Активных сейчас: {stats['active_tickets']}"
        )
        await ui_state_service.show_current_menu(
            bot, session, message.from_user.id, custom_text=text, reason="manager_stats"
        )


@router.message(IsSupport(), F.text == MANAGER_NEW_TICKETS, F.chat.type == "private")
async def manager_new_tickets(
    message: Message,
    bot: Bot,
    authorization: AuthorizationService,
    ticket_service: TicketService,
    ui_state_service: UIStateService,
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
        async with SessionLocal() as session:
            await ui_state_service.show_current_menu(
                bot,
                session,
                message.from_user.id,
                custom_text="Новых обращений нет.",
                reason="manager_new_tickets_empty",
            )
        return

    # Send menu first to establish layout
    async with SessionLocal() as session:
        await ui_state_service.show_current_menu(
            bot,
            session,
            message.from_user.id,
            custom_text="Список новых обращений:",
            reason="manager_new_tickets_list",
        )
    for ticket, recent_messages in previews:
        await message.answer(
            _ticket_queue_text(ticket, recent_messages),
            reply_markup=ticket_claim_keyboard(ticket.id),
        )


@router.message(IsSupport(), F.text == MANAGER_ACTIVE_CHATS, F.chat.type == "private")
async def manager_active_chats(
    message: Message,
    bot: Bot,
    authorization: AuthorizationService,
    ticket_service: TicketService,
    ui_state_service: UIStateService,
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
        async with SessionLocal() as session:
            await ui_state_service.show_current_menu(
                bot,
                session,
                message.from_user.id,
                custom_text="Активных диалогов нет.",
                reason="manager_active_chats_empty",
            )
        return

    async with SessionLocal() as session:
        await ui_state_service.show_current_menu(
            bot,
            session,
            message.from_user.id,
            custom_text="Ваши активные диалоги:",
            reason="manager_active_chats_list",
        )
    for ticket in tickets:
        await message.answer(
            _active_ticket_text(ticket),
            reply_markup=active_ticket_keyboard(ticket.id),
        )


@router.message(
    IsSupport(),
    F.text.in_({MANAGER_NOTIFICATIONS_ON, MANAGER_NOTIFICATIONS_OFF}),
    F.chat.type == "private",
)
async def toggle_notifications(
    message: Message,
    bot: Bot,
    ticket_service: TicketService,
    ui_state_service: UIStateService,
) -> None:
    if message.from_user is None:
        return
    async with SessionLocal() as session, session.begin():
        enabled = await ticket_service.get_manager_notifications_enabled(
            session, manager_telegram_id=message.from_user.id
        )
        enabled = not enabled
        await ticket_service.set_manager_notifications_enabled(
            session, manager_telegram_id=message.from_user.id, enabled=enabled
        )
    status = "включены" if enabled else "выключены"
    async with SessionLocal() as session:
        await ui_state_service.show_current_menu(
            bot,
            session,
            message.from_user.id,
            custom_text=f"Уведомления о новых обращениях {status}.",
            reason="toggle_notifications",
        )


@router.message(IsSupport(), F.text == MANAGER_CLOSE_TICKET, F.chat.type == "private")
async def manager_close_ticket_text(
    message: Message,
    bot: Bot,
    ticket_service: TicketService,
    ui_state_service: UIStateService,
) -> None:
    if message.from_user is None:
        return
    async with SessionLocal() as session, session.begin():
        op_session = await session.get(OperatorSession, message.from_user.id)
        ticket_id = op_session.selected_ticket_id if op_session else None
        if ticket_id is None:
            await ui_state_service.show_current_menu(
                bot,
                session,
                message.from_user.id,
                custom_text="У вас нет выбранного диалога.",
                reason="manager_close_no_ticket",
            )
            return
        ticket = await ticket_service.close_ticket(
            session, ticket_id=ticket_id, actor_telegram_id=message.from_user.id
        )
        try:
            await bot.send_message(
                chat_id=ticket.customer.telegram_user_id,
                text="Ваш вопрос закрыт менеджером. Вы снова можете задавать вопросы AI-помощнику.",
                reply_markup=ui_state_service.keyboard_service.get_customer_keyboard(
                    CustomerMode.AI_CHAT.value, ticket.customer.broadcasts_enabled
                ),
            )
        except Exception:
            pass
    async with SessionLocal() as session:
        await ui_state_service.show_current_menu(
            bot,
            session,
            message.from_user.id,
            custom_text=f"Обращение #{ticket_id} закрыто.",
            reason="manager_closed_ticket",
        )


@router.message(IsSupport(), F.text == MANAGER_EXIT_REPLY, F.chat.type == "private")
async def manager_exit_reply_text(
    message: Message,
    bot: Bot,
    ticket_service: TicketService,
    ui_state_service: UIStateService,
) -> None:
    if message.from_user is None:
        return
    async with SessionLocal() as session, session.begin():
        await ticket_service.clear_selected_ticket(
            session, operator_telegram_id=message.from_user.id
        )
    async with SessionLocal() as session:
        await ui_state_service.show_current_menu(
            bot,
            session,
            message.from_user.id,
            custom_text="Режим ответа выключен. Сообщения больше не будут отправляться клиенту.",
            reason="manager_exit_reply",
        )


@router.message(IsSupport(), F.text == MANAGER_MY_DIALOGS, F.chat.type == "private")
async def manager_my_dialogs_text(
    message: Message,
    bot: Bot,
    ticket_service: TicketService,
    ui_state_service: UIStateService,
) -> None:
    if message.from_user is None:
        return
    async with SessionLocal() as session, session.begin():
        await ticket_service.clear_selected_ticket(
            session, operator_telegram_id=message.from_user.id
        )
    async with SessionLocal() as session:
        await ui_state_service.show_current_menu(
            bot, session, message.from_user.id, reason="manager_view_my_dialogs"
        )
        tickets = await ticket_service.list_manager_active_tickets(
            session, manager_telegram_id=message.from_user.id
        )
        if not tickets:
            await message.answer("Активных диалогов нет.")
            return
        for ticket in tickets:
            await message.answer(
                f"💬 Обращение #{ticket.id}\nКлиент: {RelayService.customer_display_name(ticket.customer)}\nСтатус: В работе",
                reply_markup=active_ticket_keyboard(ticket.id),
            )


@router.message(IsSupport(), F.chat.type == "private")
async def manager_private_message(
    message: Message,
    bot: Bot,
    authorization: AuthorizationService,
    broadcast_service: BroadcastService,
    ticket_service: TicketService,
    relay_service: RelayService,
    ui_state_service: UIStateService,
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
            "private_message_route user_id=%s role=%s route=manager_message selected_ticket_id=%s",
            message.from_user.id,
            role,
            ticket.id if ticket else None,
        )
        if ticket is None:
            await ui_state_service.show_current_menu(
                bot,
                session,
                message.from_user.id,
                custom_text="Выберите активный диалог в меню, чтобы отправить сообщение клиенту.",
                reason="manager_message_no_selected_ticket",
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
