# ruff: noqa: E501
from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.filters import BaseFilter, Command
from aiogram.types import CallbackQuery, Message

from app.config import Settings
from app.db.models import OperatorSession
from app.db.session import SessionLocal
from app.filters.roles import IsOwner
from app.handlers.customer import cancel_command
from app.keyboards.constants import (
    OWNER_BACK,
    OWNER_BROADCAST,
    OWNER_BROADCAST_HISTORY,
    OWNER_CANCEL,
    OWNER_CHOOSE_MODEL,
    OWNER_STATS,
    OWNER_TICKETS,
)
from app.keyboards.inline import (
    owner_ticket_keyboard,
)
from app.services.authorization_service import AuthorizationService
from app.services.broadcast_service import BroadcastService
from app.services.statistics_service import StatisticsService
from app.services.ticket_service import TicketService
from app.services.ui_state_service import UIStateService
from app.utils.enums import (
    BroadcastButtonSelection,
    OwnerWorkflowState,
    TicketStatus,
)
from app.utils.exceptions import AuthorizationError, TicketStateError, UnsupportedRelayContentError

logger = logging.getLogger(__name__)
router = Router(name="owner")


class IsOwnerBroadcasting(BaseFilter):
    async def __call__(
        self,
        message: Message,
        authorization: AuthorizationService,
        broadcast_service: BroadcastService,
    ) -> bool:
        if message.from_user is None or not authorization.is_owner(message.from_user.id):
            return False
        async with SessionLocal() as session:
            state = await broadcast_service.active_owner_state(
                session, owner_telegram_id=message.from_user.id
            )
            return state == OwnerWorkflowState.CREATING_BROADCAST_CONTENT.value


@router.message(IsOwner(), Command("admin"))
async def admin_panel(
    message: Message,
    bot: Bot,
    ui_state_service: UIStateService,
) -> None:
    if message.from_user is None:
        return
    logger.info(
        "private_message_route user_id=%s role=owner route=admin_panel",
        message.from_user.id,
    )
    async with SessionLocal() as session:
        await ui_state_service.show_current_menu(
            bot, session, message.from_user.id, reason="admin_command"
        )


@router.message(IsOwner(), F.text == OWNER_CHOOSE_MODEL, F.chat.type == "private")
async def owner_models_text(
    message: Message,
    bot: Bot,
    ui_state_service: UIStateService,
) -> None:
    if message.from_user is None:
        return
    async with SessionLocal() as session, session.begin():
        op_session = await session.get(OperatorSession, message.from_user.id)
        if op_session is None:
            op_session = OperatorSession(operator_telegram_id=message.from_user.id)
            session.add(op_session)
        op_session.workflow_state = "MODEL_SELECTION"
    async with SessionLocal() as session:
        await ui_state_service.show_current_menu(
            bot, session, message.from_user.id, reason="owner_choose_model_text"
        )


@router.message(IsOwner(), F.text == OWNER_STATS, F.chat.type == "private")
async def owner_stats_text(
    message: Message,
    bot: Bot,
    statistics_service: StatisticsService,
    ui_state_service: UIStateService,
) -> None:
    if message.from_user is None:
        return
    async with SessionLocal() as session:
        stats = await statistics_service.owner_stats(session)
        text = _format_owner_stats(stats)
        await ui_state_service.show_current_menu(
            bot, session, message.from_user.id, custom_text=text, reason="owner_stats_text"
        )


@router.message(IsOwner(), F.text == OWNER_TICKETS, F.chat.type == "private")
async def owner_tickets_text(
    message: Message,
    bot: Bot,
    ticket_service: TicketService,
    ui_state_service: UIStateService,
) -> None:
    if message.from_user is None:
        return
    async with SessionLocal() as session:
        tickets = await ticket_service.list_active_tickets(session)
    if not tickets:
        async with SessionLocal() as session:
            await ui_state_service.show_current_menu(
                bot,
                session,
                message.from_user.id,
                custom_text="Открытых обращений нет.",
                reason="owner_tickets_empty",
            )
        return
    async with SessionLocal() as session:
        await ui_state_service.show_current_menu(
            bot,
            session,
            message.from_user.id,
            custom_text="Активные обращения:",
            reason="owner_tickets_list",
        )
    for ticket in tickets:
        await message.answer(
            _format_ticket_card(ticket),
            reply_markup=owner_ticket_keyboard(
                ticket.id, can_claim=ticket.status == TicketStatus.OPEN.value
            ),
        )


@router.message(IsOwner(), F.text == OWNER_BROADCAST, F.chat.type == "private")
async def owner_broadcast_text(
    message: Message,
    bot: Bot,
    broadcast_service: BroadcastService,
    ui_state_service: UIStateService,
) -> None:
    if message.from_user is None:
        return
    async with SessionLocal() as session, session.begin():
        await broadcast_service.start_draft(session, owner_telegram_id=message.from_user.id)
    async with SessionLocal() as session:
        await ui_state_service.show_current_menu(
            bot, session, message.from_user.id, reason="owner_broadcast_start"
        )


@router.message(IsOwner(), F.text == OWNER_BROADCAST_HISTORY, F.chat.type == "private")
async def owner_broadcast_history_text(
    message: Message,
    bot: Bot,
    broadcast_service: BroadcastService,
    ui_state_service: UIStateService,
) -> None:
    if message.from_user is None:
        return
    async with SessionLocal() as session:
        broadcasts = await broadcast_service.recent_broadcasts(session)
    if not broadcasts:
        async with SessionLocal() as session:
            await ui_state_service.show_current_menu(
                bot,
                session,
                message.from_user.id,
                custom_text="История рассылок пока пуста.",
                reason="owner_broadcast_history_empty",
            )
        return
    async with SessionLocal() as session:
        await ui_state_service.show_current_menu(
            bot,
            session,
            message.from_user.id,
            custom_text="История рассылок:",
            reason="owner_broadcast_history_list",
        )
    for broadcast in broadcasts:
        await message.answer(
            _format_broadcast_history_item(broadcast),
            reply_markup=owner_ticket_keyboard(broadcast.id, can_claim=False)
            if False
            else None,  # keep simple
        )


@router.message(IsOwner(), F.text.in_({OWNER_CANCEL, OWNER_BACK}), F.chat.type == "private")
async def owner_cancel_text_button(
    message: Message,
    bot: Bot,
    authorization: AuthorizationService,
    ticket_service: TicketService,
    broadcast_service: BroadcastService,
    ui_state_service: UIStateService,
) -> None:
    await cancel_command(
        message, bot, authorization, ticket_service, broadcast_service, ui_state_service
    )


@router.callback_query(IsOwner(), F.data == "owner:panel")
async def owner_panel_callback(
    callback: CallbackQuery,
    bot: Bot,
    authorization: AuthorizationService,
    ui_state_service: UIStateService,
) -> None:
    if callback.from_user is None or not authorization.is_owner(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    async with SessionLocal() as session, session.begin():
        op_session = await session.get(OperatorSession, callback.from_user.id)
        if op_session:
            op_session.workflow_state = None
    async with SessionLocal() as session:
        await ui_state_service.show_current_menu(
            bot, session, callback.from_user.id, reason="owner_panel_callback"
        )
    await callback.answer()


@router.callback_query(IsOwner(), F.data == "owner:models")
async def owner_models(
    callback: CallbackQuery,
    bot: Bot,
    authorization: AuthorizationService,
    ui_state_service: UIStateService,
) -> None:
    if callback.from_user is None or not authorization.is_owner(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    async with SessionLocal() as session, session.begin():
        op_session = await session.get(OperatorSession, callback.from_user.id)
        if op_session:
            op_session.workflow_state = "MODEL_SELECTION"
    async with SessionLocal() as session:
        await ui_state_service.show_current_menu(
            bot, session, callback.from_user.id, reason="owner_models_callback"
        )
    await callback.answer()


@router.callback_query(IsOwner(), F.data == "owner:stats")
async def owner_stats(
    callback: CallbackQuery,
    bot: Bot,
    authorization: AuthorizationService,
    statistics_service: StatisticsService,
    ui_state_service: UIStateService,
) -> None:
    if callback.from_user is None or not authorization.is_owner(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    async with SessionLocal() as session:
        stats = await statistics_service.owner_stats(session)
        text = _format_owner_stats(stats)
        await ui_state_service.show_current_menu(
            bot, session, callback.from_user.id, custom_text=text, reason="owner_stats_callback"
        )
    await callback.answer()


@router.callback_query(IsOwner(), F.data == "owner:open_tickets")
async def owner_open_tickets(
    callback: CallbackQuery,
    bot: Bot,
    authorization: AuthorizationService,
    ticket_service: TicketService,
    ui_state_service: UIStateService,
) -> None:
    if callback.from_user is None or not authorization.is_owner(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    async with SessionLocal() as session:
        tickets = await ticket_service.list_active_tickets(session)
    if not tickets:
        async with SessionLocal() as session:
            await ui_state_service.show_current_menu(
                bot,
                session,
                callback.from_user.id,
                custom_text="Открытых обращений нет.",
                reason="owner_open_tickets_callback_empty",
            )
        await callback.answer()
        return
    async with SessionLocal() as session:
        await ui_state_service.show_current_menu(
            bot,
            session,
            callback.from_user.id,
            custom_text="Активные обращения отправлены ниже.",
            reason="owner_open_tickets_callback_list",
        )
    for ticket in tickets:
        await callback.message.answer(
            _format_ticket_card(ticket),
            reply_markup=owner_ticket_keyboard(
                ticket.id, can_claim=ticket.status == TicketStatus.OPEN.value
            ),
        )
    await callback.answer()


@router.callback_query(IsOwner(), F.data == "broadcast:start")
async def broadcast_start(
    callback: CallbackQuery,
    bot: Bot,
    authorization: AuthorizationService,
    broadcast_service: BroadcastService,
    ui_state_service: UIStateService,
) -> None:
    if callback.from_user is None or not authorization.is_owner(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    async with SessionLocal() as session, session.begin():
        await broadcast_service.start_draft(session, owner_telegram_id=callback.from_user.id)
    async with SessionLocal() as session:
        await ui_state_service.show_current_menu(
            bot, session, callback.from_user.id, reason="owner_broadcast_start_callback"
        )
    await callback.answer()


@router.callback_query(IsOwner(), F.data == "broadcast:history")
async def broadcast_history(
    callback: CallbackQuery,
    bot: Bot,
    authorization: AuthorizationService,
    broadcast_service: BroadcastService,
    ui_state_service: UIStateService,
) -> None:
    if callback.from_user is None or not authorization.is_owner(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    async with SessionLocal() as session:
        broadcasts = await broadcast_service.recent_broadcasts(session)
    if not broadcasts:
        async with SessionLocal() as session:
            await ui_state_service.show_current_menu(
                bot,
                session,
                callback.from_user.id,
                custom_text="История рассылок пока пуста.",
                reason="owner_broadcast_history_callback_empty",
            )
        await callback.answer()
        return
    async with SessionLocal() as session:
        await ui_state_service.show_current_menu(
            bot,
            session,
            callback.from_user.id,
            custom_text="История рассылок:",
            reason="owner_broadcast_history_callback_list",
        )
    from app.keyboards.inline import broadcast_report_keyboard

    for broadcast in broadcasts:
        await callback.message.answer(
            _format_broadcast_history_item(broadcast),
            reply_markup=broadcast_report_keyboard(broadcast.id),
        )
    await callback.answer()


@router.callback_query(IsOwner(), F.data == "broadcast:cancel")
async def broadcast_cancel(
    callback: CallbackQuery,
    bot: Bot,
    authorization: AuthorizationService,
    broadcast_service: BroadcastService,
    ui_state_service: UIStateService,
) -> None:
    if callback.from_user is None or not authorization.is_owner(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    async with SessionLocal() as session, session.begin():
        await broadcast_service.cancel_active_draft(
            session, owner_telegram_id=callback.from_user.id
        )
    async with SessionLocal() as session:
        await ui_state_service.show_current_menu(
            bot,
            session,
            callback.from_user.id,
            custom_text="Рассылка отменена.",
            reason="owner_broadcast_cancel_callback",
        )
    await callback.answer()


@router.callback_query(IsOwner(), F.data == "broadcast:restart")
async def broadcast_restart(
    callback: CallbackQuery,
    bot: Bot,
    authorization: AuthorizationService,
    broadcast_service: BroadcastService,
    ui_state_service: UIStateService,
) -> None:
    if callback.from_user is None or not authorization.is_owner(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    async with SessionLocal() as session, session.begin():
        await broadcast_service.start_draft(session, owner_telegram_id=callback.from_user.id)
    async with SessionLocal() as session:
        await ui_state_service.show_current_menu(
            bot, session, callback.from_user.id, reason="owner_broadcast_restart_callback"
        )
    await callback.answer()


@router.callback_query(IsOwner(), F.data.startswith("broadcast:buttons:"))
async def broadcast_buttons(
    callback: CallbackQuery,
    bot: Bot,
    authorization: AuthorizationService,
    broadcast_service: BroadcastService,
    ui_state_service: UIStateService,
) -> None:
    if callback.from_user is None or callback.data is None:
        return
    if not authorization.is_owner(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    selection_value = callback.data.rsplit(":", maxsplit=1)[-1]
    try:
        selection = BroadcastButtonSelection(selection_value)
    except ValueError:
        await callback.answer("Некорректный выбор кнопок", show_alert=True)
        return
    async with SessionLocal() as session, session.begin():
        draft = await broadcast_service.get_active_draft(
            session, owner_telegram_id=callback.from_user.id
        )
        if draft is None:
            await callback.answer("Черновик не найден", show_alert=True)
            return
        try:
            broadcast = await broadcast_service.set_buttons(
                session,
                owner_telegram_id=callback.from_user.id,
                broadcast_id=draft.id,
                selection=selection,
            )
            await broadcast_service.copy_broadcast_to_chat(
                bot, broadcast=broadcast, destination_chat_id=callback.from_user.id
            )
        except (AuthorizationError, TicketStateError) as exc:
            await callback.answer(str(exc), show_alert=True)
            return
    async with SessionLocal() as session:
        await ui_state_service.show_current_menu(
            bot, session, callback.from_user.id, reason="owner_broadcast_buttons_selected"
        )
    await callback.answer()


@router.callback_query(IsOwner(), F.data == "broadcast:test")
async def broadcast_test(
    callback: CallbackQuery,
    bot: Bot,
    authorization: AuthorizationService,
    broadcast_service: BroadcastService,
) -> None:
    if callback.from_user is None or not authorization.is_owner(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    async with SessionLocal() as session:
        broadcast = await broadcast_service.get_active_draft(
            session, owner_telegram_id=callback.from_user.id
        )
        if broadcast is None:
            await callback.answer("Черновик не найден", show_alert=True)
            return
        await broadcast_service.send_test(bot, session, broadcast=broadcast)
    await callback.message.answer(
        "Тест отправлен вам. Черновик сохранён.",
        reply_markup=owner_ticket_keyboard(broadcast.id, can_claim=False)
        if False
        else None,  # keep clean
    )
    await callback.answer()


@router.callback_query(IsOwner(), F.data == "broadcast:send_all")
async def broadcast_send_all(
    callback: CallbackQuery,
    bot: Bot,
    authorization: AuthorizationService,
    broadcast_service: BroadcastService,
    ui_state_service: UIStateService,
) -> None:
    if callback.from_user is None or not authorization.is_owner(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    async with SessionLocal() as session, session.begin():
        broadcast = await broadcast_service.get_active_draft(
            session, owner_telegram_id=callback.from_user.id
        )
        if broadcast is None:
            await callback.answer("Черновик не найден", show_alert=True)
            return
        try:
            broadcast, recipient_count = await broadcast_service.request_final_confirmation(
                session, owner_telegram_id=callback.from_user.id, broadcast_id=broadcast.id
            )
        except TicketStateError as exc:
            await callback.answer(str(exc), show_alert=True)
            return
    async with SessionLocal() as session:
        await ui_state_service.show_current_menu(
            bot, session, callback.from_user.id, reason="owner_broadcast_send_all_callback"
        )
    await callback.answer()


@router.callback_query(IsOwner(), F.data.startswith("broadcast:confirm:"))
async def broadcast_confirm(
    callback: CallbackQuery,
    bot: Bot,
    authorization: AuthorizationService,
    broadcast_service: BroadcastService,
    ui_state_service: UIStateService,
) -> None:
    if callback.from_user is None or callback.data is None:
        return
    if not authorization.is_owner(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    broadcast_id_text = callback.data.rsplit(":", maxsplit=1)[-1]
    if not broadcast_id_text.isdigit():
        await callback.answer("Некорректная рассылка", show_alert=True)
        return
    async with SessionLocal() as session, session.begin():
        try:
            broadcast = await broadcast_service.start_sending(
                session,
                owner_telegram_id=callback.from_user.id,
                broadcast_id=int(broadcast_id_text),
            )
        except TicketStateError as exc:
            await callback.answer(str(exc), show_alert=True)
            return
    broadcast_service.launch_sending_job(bot, broadcast_id=broadcast.id)
    async with SessionLocal() as session:
        await ui_state_service.show_current_menu(
            bot,
            session,
            callback.from_user.id,
            custom_text=f"Рассылка #{broadcast.id} поставлена в отправку. Получателей: {broadcast.recipient_count}.",
            reason="owner_broadcast_confirm_callback",
        )
    await callback.answer("Отправка началась")


@router.callback_query(IsOwner(), F.data.startswith("broadcast:report:"))
async def broadcast_report(
    callback: CallbackQuery,
    authorization: AuthorizationService,
    broadcast_service: BroadcastService,
) -> None:
    if callback.from_user is None or callback.data is None:
        return
    if not authorization.is_owner(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    broadcast_id_text = callback.data.rsplit(":", maxsplit=1)[-1]
    if not broadcast_id_text.isdigit():
        await callback.answer("Некорректная рассылка", show_alert=True)
        return
    async with SessionLocal() as session:
        try:
            broadcast = await broadcast_service.get_report(
                session,
                owner_telegram_id=callback.from_user.id,
                broadcast_id=int(broadcast_id_text),
            )
        except AuthorizationError:
            await callback.answer("Недостаточно прав", show_alert=True)
            return
    await callback.message.answer(_format_broadcast_history_item(broadcast))
    await callback.answer()


@router.message(IsOwnerBroadcasting(), F.text == OWNER_CANCEL, F.chat.type == "private")
async def broadcast_cancel_message(
    message: Message,
    bot: Bot,
    broadcast_service: BroadcastService,
    ui_state_service: UIStateService,
) -> None:
    if message.from_user is None:
        return
    async with SessionLocal() as session, session.begin():
        await broadcast_service.cancel_active_draft(session, owner_telegram_id=message.from_user.id)
    async with SessionLocal() as session:
        await ui_state_service.show_current_menu(
            bot,
            session,
            message.from_user.id,
            custom_text="Рассылка отменена.",
            reason="owner_broadcast_cancel_text_message",
        )


@router.message(IsOwnerBroadcasting(), F.chat.type == "private")
async def broadcast_capture_message(
    message: Message,
    bot: Bot,
    settings: Settings,
    broadcast_service: BroadcastService,
    ui_state_service: UIStateService,
) -> None:
    if message.from_user is None:
        return
    if message.text in {OWNER_CANCEL, OWNER_BACK} or (
        message.text and message.text.startswith("/")
    ):
        return

    async with SessionLocal() as session, session.begin():
        try:
            await broadcast_service.capture_content(
                session, owner_telegram_id=message.from_user.id, message=message
            )
        except UnsupportedRelayContentError as exc:
            await message.answer(str(exc))
            await ui_state_service.show_current_menu(
                bot, session, message.from_user.id, reason="unsupported_broadcast_content"
            )
            return

    async with SessionLocal() as session:
        await ui_state_service.show_current_menu(
            bot, session, message.from_user.id, reason="broadcast_content_captured"
        )


def _format_owner_stats(stats: dict) -> str:
    manager_lines = "\n".join(
        f"- {manager_id}: {count}" for manager_id, count in stats["tickets_per_manager"].items()
    )
    if not manager_lines:
        manager_lines = "- пока нет"
    avg = stats["avg_first_claim_seconds"]
    avg_text = f"{avg} сек." if avg is not None else "недостаточно данных"
    return (
        "Статистика бота:\n"
        f"Клиентов всего: {stats['total_customers']}\n"
        f"Новых сегодня: {stats['new_customers_today']}\n"
        f"AI-сообщений: {stats['total_ai_messages']}\n"
        f"Обращений всего: {stats['total_tickets']}\n"
        f"Открытых: {stats['open_tickets']}\n"
        f"В работе: {stats['claimed_tickets']}\n"
        f"Закрытых: {stats['closed_tickets']}\n"
        f"Среднее время до взятия: {avg_text}\n\n"
        f"По менеджерам:\n{manager_lines}"
    )


def _format_ticket_card(ticket) -> str:
    username = f" @{ticket.customer.username}" if ticket.customer.username else ""
    manager = ticket.assigned_manager_telegram_id or "не назначен"
    return (
        f"Обращение #{ticket.id}\n"
        f"Клиент: {ticket.customer.first_name or ticket.customer.telegram_user_id}{username}\n"
        f"Статус: {ticket.status}\n"
        f"Менеджер: {manager}\n"
        f"Создано: {ticket.created_at:%Y-%m-%d %H:%M}"
    )


def _format_broadcast_history_item(broadcast) -> str:
    preview = (broadcast.content_preview or "Без текста")[:120]
    return (
        f"Рассылка #{broadcast.id}\n"
        f"Дата: {broadcast.created_at:%Y-%m-%d %H:%M}\n"
        f"Статус: {broadcast.status}\n"
        f"Текст: {preview}\n"
        f"Получателей: {broadcast.recipient_count}\n"
        f"Доставлено: {broadcast.delivered_count}\n"
        f"Ошибок: {broadcast.failed_count}\n"
        f"Недоступны: {broadcast.blocked_count}"
    )
