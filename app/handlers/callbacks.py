from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery

from app.config import AVAILABLE_MODELS
from app.db.models import OperatorSession

# ruff: noqa: E501
from app.db.session import SessionLocal
from app.filters.roles import IsOwner, IsSupport
from app.keyboards.inline import (
    active_ticket_keyboard,
)
from app.keyboards.owner import model_id_by_index
from app.services.authorization_service import AuthorizationService
from app.services.relay_service import RelayService
from app.services.settings_service import SettingsService
from app.services.ticket_service import TicketService
from app.services.ui_state_service import UIStateService
from app.utils.enums import CustomerMode, TicketStatus
from app.utils.exceptions import AuthorizationError, TicketStateError

logger = logging.getLogger(__name__)
router = Router(name="callbacks")


@router.callback_query(IsSupport(), F.data == "manager:active")
async def manager_active_callback(
    callback: CallbackQuery,
    bot: Bot,
    authorization: AuthorizationService,
    ticket_service: TicketService,
    ui_state_service: UIStateService,
) -> None:
    if callback.from_user is None or not authorization.can_use_support_tools(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    async with SessionLocal() as session:
        if authorization.is_owner(callback.from_user.id):
            tickets = await ticket_service.list_active_tickets(session)
        else:
            tickets = await ticket_service.list_manager_active_tickets(
                session, manager_telegram_id=callback.from_user.id
            )
    if not tickets:
        async with SessionLocal() as session:
            await ui_state_service.show_current_menu(
                bot,
                session,
                callback.from_user.id,
                custom_text="Активных диалогов нет.",
                reason="manager_active_chats_callback_empty",
            )
        await callback.answer()
        return

    async with SessionLocal() as session:
        await ui_state_service.show_current_menu(
            bot,
            session,
            callback.from_user.id,
            custom_text="Активные диалоги:",
            reason="manager_active_chats_callback_list",
        )
    for ticket in tickets:
        await callback.message.answer(
            f"Обращение #{ticket.id}: {ticket.status}",
            reply_markup=active_ticket_keyboard(ticket.id),
        )
    await callback.answer()


@router.callback_query(IsSupport(), F.data == "operator:exit_reply")
async def operator_exit_reply(
    callback: CallbackQuery,
    bot: Bot,
    ticket_service: TicketService,
    ui_state_service: UIStateService,
) -> None:
    if callback.from_user is None:
        return
    async with SessionLocal() as session, session.begin():
        await ticket_service.clear_selected_ticket(
            session, operator_telegram_id=callback.from_user.id
        )
    async with SessionLocal() as session:
        await ui_state_service.show_current_menu(
            bot,
            session,
            callback.from_user.id,
            custom_text="Режим ответа выключен. Сообщения больше не будут отправляться клиенту.",
            reason="operator_exit_reply_callback",
        )
    await callback.answer()


@router.callback_query(IsSupport(), F.data.startswith("manager:notify:"))
async def manager_notifications_callback(
    callback: CallbackQuery,
    bot: Bot,
    ticket_service: TicketService,
    ui_state_service: UIStateService,
) -> None:
    if callback.from_user is None or callback.data is None:
        return
    enabled = callback.data.endswith(":on")
    async with SessionLocal() as session, session.begin():
        await ticket_service.set_manager_notifications_enabled(
            session, manager_telegram_id=callback.from_user.id, enabled=enabled
        )
    status = "включены" if enabled else "выключены"
    async with SessionLocal() as session:
        await ui_state_service.show_current_menu(
            bot,
            session,
            callback.from_user.id,
            custom_text=f"Уведомления о новых обращениях {status}.",
            reason="manager_notifications_callback",
        )
    await callback.answer()


@router.callback_query(IsSupport(), F.data.startswith("ticket:"))
async def ticket_callback(
    callback: CallbackQuery,
    bot: Bot,
    ticket_service: TicketService,
    authorization: AuthorizationService,
    relay_service: RelayService,
    ui_state_service: UIStateService,
) -> None:
    if callback.from_user is None or callback.data is None:
        return
    if not authorization.can_use_support_tools(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    parts = callback.data.split(":")
    if len(parts) != 3 or not parts[2].isdigit():
        await callback.answer("Некорректное действие", show_alert=True)
        return
    action = parts[1]
    ticket_id = int(parts[2])

    try:
        async with SessionLocal() as session, session.begin():
            ticket = await ticket_service.get_ticket(session, ticket_id=ticket_id)
            if action == "claim":
                if ticket.status != TicketStatus.OPEN.value:
                    raise TicketStateError("Это обращение уже взял другой менеджер.")
                await ticket_service.claim_ticket(
                    session,
                    ticket_id=ticket_id,
                    manager_telegram_id=callback.from_user.id,
                )
                try:
                    await bot.send_message(
                        chat_id=ticket.customer.telegram_user_id,
                        text=(
                            "К вашему обращению подключился менеджер. "
                            "Теперь вы можете общаться здесь и отправлять файлы."
                        ),
                    )
                except Exception:
                    pass
                # Update customer keyboard first
                await ui_state_service.show_current_menu(
                    bot, session, ticket.customer.telegram_user_id, reason="ticket_claimed_customer"
                )

                # Update manager keyboard
                await ui_state_service.show_current_menu(
                    bot, session, callback.from_user.id, reason="ticket_claimed_manager"
                )
                await callback.answer("Обращение взято")

            elif action == "history":
                if not ticket_service.can_view_manager_ticket(ticket, callback.from_user.id):
                    raise AuthorizationError("Недостаточно прав")
                await relay_service.copy_ticket_history_to_chat(
                    bot, session, ticket_id=ticket.id, destination_chat_id=callback.from_user.id
                )
                await callback.answer()

            elif action == "open":
                if not ticket_service.can_view_manager_ticket(ticket, callback.from_user.id):
                    raise AuthorizationError("Недостаточно прав")
                if ticket.status in {TicketStatus.CLAIMED.value, TicketStatus.OPEN.value}:
                    await ticket_service.select_ticket(
                        session, operator_telegram_id=callback.from_user.id, ticket=ticket
                    )
                await ui_state_service.show_current_menu(
                    bot, session, callback.from_user.id, reason="ticket_open_manager"
                )
                await callback.answer()

            elif action == "close":
                if ticket.status not in {TicketStatus.CLAIMED.value, TicketStatus.OPEN.value}:
                    raise TicketStateError("Обращение уже закрыто.")
                await ticket_service.close_ticket(
                    session,
                    ticket_id=ticket_id,
                    actor_telegram_id=callback.from_user.id,
                )
                try:
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
                except Exception:
                    pass
                # Update customer keyboard
                await ui_state_service.show_current_menu(
                    bot, session, ticket.customer.telegram_user_id, reason="ticket_closed_customer"
                )
                # Update manager keyboard
                await ui_state_service.show_current_menu(
                    bot,
                    session,
                    callback.from_user.id,
                    custom_text=f"Обращение #{ticket_id} закрыто.",
                    reason="ticket_closed_manager",
                )
                await callback.answer("Закрыто")
            else:
                await callback.answer("Неизвестное действие", show_alert=True)
    except (AuthorizationError, TicketStateError) as exc:
        await callback.answer(str(exc), show_alert=True)
        async with SessionLocal() as session:
            await ui_state_service.show_current_menu(
                bot,
                session,
                callback.from_user.id,
                message=callback.message,
                reason="ticket_callback_error",
            )


@router.callback_query(IsOwner(), F.data.startswith("owner:model:"))
async def switch_model_callback(
    callback: CallbackQuery,
    bot: Bot,
    authorization: AuthorizationService,
    settings_service: SettingsService,
    ui_state_service: UIStateService,
) -> None:
    if callback.from_user is None or callback.data is None:
        return
    if not authorization.is_owner(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    index_text = callback.data.rsplit(":", maxsplit=1)[-1]
    if not index_text.isdigit():
        await callback.answer("Некорректная модель", show_alert=True)
        return
    model_id = model_id_by_index(int(index_text))
    if model_id is None:
        await callback.answer("Некорректная модель", show_alert=True)
        return

    try:
        async with SessionLocal() as session, session.begin():
            active_model = await settings_service.switch_active_model(
                session,
                actor_telegram_id=callback.from_user.id,
                model_id=model_id,
            )
            # Clear owner workflow state when selection is finalized
            op_session = await session.get(OperatorSession, callback.from_user.id)
            if op_session:
                op_session.workflow_state = None
        async with SessionLocal() as session:
            await ui_state_service.show_current_menu(
                bot,
                session,
                callback.from_user.id,
                custom_text=f"Активная модель обновлена:\n{AVAILABLE_MODELS[active_model]}",
                reason="owner_model_switched",
            )
        await callback.answer("Модель обновлена")
    except Exception as exc:
        await callback.answer(str(exc), show_alert=True)
        async with SessionLocal() as session:
            await ui_state_service.show_current_menu(
                bot,
                session,
                callback.from_user.id,
                message=callback.message,
                reason="owner_model_switch_error",
            )
