from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery

from app.config import AVAILABLE_MODELS
from app.db.session import SessionLocal
from app.filters.roles import IsOwner, IsSupport
from app.keyboards.customer import customer_keyboard
from app.keyboards.manager import (
    active_ticket_keyboard,
    manager_keyboard,
    notification_keyboard,
    ticket_chat_keyboard,
)
from app.keyboards.owner import model_id_by_index, model_selection_keyboard
from app.services.authorization_service import AuthorizationService
from app.services.relay_service import RelayService
from app.services.settings_service import SettingsService
from app.services.ticket_service import TicketService
from app.utils.enums import TicketStatus
from app.utils.exceptions import AuthorizationError, TicketStateError

router = Router(name="callbacks")


@router.callback_query(IsSupport(), F.data == "manager:active")
async def manager_active_callback(
    callback: CallbackQuery,
    authorization: AuthorizationService,
    ticket_service: TicketService,
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
        await callback.message.answer("Активных диалогов нет.", reply_markup=manager_keyboard())
        await callback.answer()
        return
    for ticket in tickets:
        await callback.message.answer(
            f"Обращение #{ticket.id}: {ticket.status}",
            reply_markup=active_ticket_keyboard(ticket.id),
        )
    await callback.answer()


@router.callback_query(IsSupport(), F.data == "operator:exit_reply")
async def operator_exit_reply(
    callback: CallbackQuery,
    ticket_service: TicketService,
) -> None:
    if callback.from_user is None:
        return
    async with SessionLocal() as session, session.begin():
        await ticket_service.clear_selected_ticket(
            session, operator_telegram_id=callback.from_user.id
        )
    await callback.message.answer(
        "Режим ответа выключен. Сообщения больше не будут отправляться клиенту.",
        reply_markup=manager_keyboard(),
    )
    await callback.answer()


@router.callback_query(IsSupport(), F.data.startswith("manager:notify:"))
async def manager_notifications_callback(
    callback: CallbackQuery,
    ticket_service: TicketService,
) -> None:
    if callback.from_user is None or callback.data is None:
        return
    enabled = callback.data.endswith(":on")
    async with SessionLocal() as session, session.begin():
        await ticket_service.set_manager_notifications_enabled(
            session, manager_telegram_id=callback.from_user.id, enabled=enabled
        )
    status = "включены" if enabled else "выключены"
    await callback.message.answer(
        f"Уведомления о новых обращениях {status}.",
        reply_markup=notification_keyboard(enabled),
    )
    await callback.answer()


@router.callback_query(IsSupport(), F.data.startswith("ticket:"))
async def ticket_callback(
    callback: CallbackQuery,
    bot: Bot,
    ticket_service: TicketService,
    authorization: AuthorizationService,
    relay_service: RelayService,
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

    async with SessionLocal() as session, session.begin():
        try:
            if action == "claim":
                ticket = await ticket_service.claim_ticket(
                    session,
                    ticket_id=ticket_id,
                    manager_telegram_id=callback.from_user.id,
                )
                await bot.send_message(
                    chat_id=ticket.customer.telegram_user_id,
                    text=(
                        "К вашему обращению подключился менеджер. "
                        "Теперь вы можете общаться здесь и отправлять файлы."
                    ),
                )
                await callback.message.answer(
                    await _ticket_chat_text(session, ticket_service, ticket_id=ticket.id),
                    reply_markup=ticket_chat_keyboard(ticket.id),
                )
                await callback.answer("Обращение взято")
            elif action == "history":
                ticket = await ticket_service.get_ticket(session, ticket_id=ticket_id)
                if not ticket_service.can_view_manager_ticket(ticket, callback.from_user.id):
                    raise AuthorizationError("Недостаточно прав")
                await relay_service.copy_ticket_history_to_chat(
                    bot, session, ticket_id=ticket.id, destination_chat_id=callback.from_user.id
                )
                await callback.answer()
            elif action == "open":
                ticket = await ticket_service.get_ticket(session, ticket_id=ticket_id)
                if not ticket_service.can_view_manager_ticket(ticket, callback.from_user.id):
                    raise AuthorizationError("Недостаточно прав")
                if ticket.status in {TicketStatus.CLAIMED.value, TicketStatus.OPEN.value}:
                    await ticket_service.select_ticket(
                        session, operator_telegram_id=callback.from_user.id, ticket=ticket
                    )
                    await callback.message.answer(
                        await _ticket_chat_text(session, ticket_service, ticket_id=ticket.id),
                        reply_markup=ticket_chat_keyboard(ticket.id),
                    )
                await callback.answer()
            elif action == "close":
                ticket = await ticket_service.close_ticket(
                    session,
                    ticket_id=ticket_id,
                    actor_telegram_id=callback.from_user.id,
                )
                await bot.send_message(
                    chat_id=ticket.customer.telegram_user_id,
                    text=(
                        "Ваш вопрос закрыт менеджером. "
                        "Вы снова можете задавать вопросы AI-помощнику."
                    ),
                    reply_markup=customer_keyboard(),
                )
                await callback.message.answer("Обращение закрыто.", reply_markup=manager_keyboard())
                await callback.answer("Закрыто")
            else:
                await callback.answer("Неизвестное действие", show_alert=True)
        except (AuthorizationError, TicketStateError) as exc:
            await callback.answer(str(exc), show_alert=True)


@router.callback_query(IsOwner(), F.data.startswith("owner:model:"))
async def switch_model_callback(
    callback: CallbackQuery,
    authorization: AuthorizationService,
    settings_service: SettingsService,
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

    async with SessionLocal() as session, session.begin():
        active_model = await settings_service.switch_active_model(
            session,
            actor_telegram_id=callback.from_user.id,
            model_id=model_id,
        )
    await callback.message.edit_text(
        f"Активная модель обновлена:\n{AVAILABLE_MODELS[active_model]}",
        reply_markup=model_selection_keyboard(active_model),
    )
    await callback.answer("Модель обновлена")


async def _ticket_chat_text(session, ticket_service: TicketService, *, ticket_id: int) -> str:
    ticket = await ticket_service.get_ticket(session, ticket_id=ticket_id)
    messages = await ticket_service.get_recent_ticket_messages(
        session, ticket_id=ticket.id, limit=6
    )
    username = f" @{ticket.customer.username}" if ticket.customer.username else ""
    status = "В работе" if ticket.status == TicketStatus.CLAIMED.value else "Открыто"
    history = "\n".join(
        f"{message.sender_type}: {message.text_preview or message.content}" for message in messages
    )
    if not history:
        history = "История обращения пока пуста."
    return (
        f"Вы отвечаете клиенту по обращению #{ticket.id}. "
        "Все отправленные сейчас сообщения и файлы будут переданы этому клиенту.\n\n"
        f"Клиент: {ticket.customer.first_name or ticket.customer.telegram_user_id}{username}\n"
        f"Статус: {status}\n\n"
        f"Последние сообщения:\n{history[:2000]}"
    )
