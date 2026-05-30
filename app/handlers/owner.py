# ruff: noqa: E501
from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.filters import BaseFilter, Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select, func

from app.config import Settings, get_settings
from app.db.models import OperatorSession, StaffMember, User
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
    OWNER_MANAGERS,
    OWNER_PROMOTE_MANAGER,
    OWNER_MANAGER_STATS,
)
from app.keyboards.inline import (
    owner_ticket_keyboard,
    owner_manager_keyboard,
    owner_manager_disable_confirm_keyboard,
    owner_promote_users_keyboard,
    owner_promote_unknown_confirm_keyboard,
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
    StaffRole,
    StaffStatus,
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


class IsOwnerAwaitingManagerId(BaseFilter):
    async def __call__(
        self,
        message: Message,
        authorization: AuthorizationService,
    ) -> bool:
        if message.from_user is None or not authorization.is_owner(message.from_user.id):
            return False
        async with SessionLocal() as session:
            op_session = await session.get(OperatorSession, message.from_user.id)
            return op_session is not None and op_session.workflow_state == OwnerWorkflowState.AWAITING_MANAGER_ID.value



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


# --- MANAGER MANAGEMENT HANDLERS ---
import datetime

async def _promote_manager_db(telegram_user_id: int, added_by_telegram_id: int) -> None:
    async with SessionLocal() as session, session.begin():
        stmt = select(StaffMember).where(StaffMember.telegram_user_id == telegram_user_id)
        staff = await session.scalar(stmt)
        if staff:
            staff.status = StaffStatus.ACTIVE.value
            staff.role = StaffRole.MANAGER.value
            staff.added_by_telegram_id = added_by_telegram_id
            staff.disabled_at = None
        else:
            staff = StaffMember(
                telegram_user_id=telegram_user_id,
                role=StaffRole.MANAGER.value,
                status=StaffStatus.ACTIVE.value,
                added_by_telegram_id=added_by_telegram_id
            )
            session.add(staff)

async def _reset_workflow_state(owner_telegram_id: int) -> None:
    async with SessionLocal() as session, session.begin():
        op_session = await session.get(OperatorSession, owner_telegram_id)
        if op_session:
            op_session.workflow_state = None

@router.message(IsOwner(), F.text == OWNER_MANAGERS, F.chat.type == "private")
async def owner_managers_text(
    message: Message,
    bot: Bot,
    ui_state_service: UIStateService,
) -> None:
    user_id = message.from_user.id if message.from_user else message.chat.id
    
    async with SessionLocal() as session:
        stmt = select(StaffMember).order_by(StaffMember.added_at.desc())
        staff_members = (await session.scalars(stmt)).all()
        
        await ui_state_service.show_current_menu(
            bot, session, user_id, custom_text="Список менеджеров в базе данных:", reason="owner_managers_list"
        )
        
        settings = get_settings()
        
        if not staff_members:
            await message.answer("В базе данных нет менеджеров.")
            return
            
        for staff in staff_members:
            u_stmt = select(User).where(User.telegram_user_id == staff.telegram_user_id)
            user = await session.scalar(u_stmt)
            
            name = "Неизвестный пользователь"
            if user:
                name_parts = []
                if user.first_name:
                    name_parts.append(user.first_name)
                if user.last_name:
                    name_parts.append(user.last_name)
                if user.username:
                    name_parts.append(f"(@{user.username})")
                if name_parts:
                    name = " ".join(name_parts)
            
            card = (
                f"👤 {name}\n"
                f"ID: <code>{staff.telegram_user_id}</code>\n"
                f"Роль: <b>{staff.role}</b>\n"
                f"Статус: <b>{staff.status}</b>\n"
                f"Добавлен: {staff.added_at:%Y-%m-%d %H:%M}"
            )
            
            is_active = (staff.status == StaffStatus.ACTIVE.value)
            is_root_owner = (staff.telegram_user_id == settings.owner_id)
            
            markup = None
            if not is_root_owner:
                markup = owner_manager_keyboard(staff.telegram_user_id, is_active=is_active)
            else:
                card += "\n👑 <i>Главный владелец (нельзя деактивировать)</i>"
                
            await message.answer(card, reply_markup=markup, parse_mode="HTML")

@router.callback_query(IsOwner(), F.data == "owner:managers_list")
async def owner_managers_list_callback(
    callback: CallbackQuery,
    bot: Bot,
    ui_state_service: UIStateService,
) -> None:
    if callback.from_user is None:
        return
    try:
        await callback.message.delete()
    except Exception:
        pass
    dummy_msg = Message(
        message_id=callback.message.message_id,
        date=callback.message.date,
        chat=callback.message.chat,
        from_user=callback.from_user,
    )
    await owner_managers_text(dummy_msg, bot, ui_state_service)
    await callback.answer()

@router.message(IsOwner(), F.text == OWNER_PROMOTE_MANAGER, F.chat.type == "private")
async def owner_promote_manager_text(
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
        op_session.workflow_state = OwnerWorkflowState.AWAITING_MANAGER_ID.value
        
    async with SessionLocal() as session:
        settings = get_settings()
        stmt = select(User).where(
            User.telegram_user_id != settings.owner_id
        ).order_by(User.last_seen_at.desc()).limit(10)
        recent_users = (await session.scalars(stmt)).all()
        
        inline_users = []
        for u in recent_users:
            s_stmt = select(StaffMember).where(
                StaffMember.telegram_user_id == u.telegram_user_id
            )
            staff = await session.scalar(s_stmt)
            if not staff or staff.status != StaffStatus.ACTIVE.value:
                name_parts = []
                if u.first_name:
                    name_parts.append(u.first_name)
                if u.last_name:
                    name_parts.append(u.last_name)
                if u.username:
                    name_parts.append(f"(@{u.username})")
                name = " ".join(name_parts).strip() or f"User {u.telegram_user_id}"
                inline_users.append((u.telegram_user_id, name))
                
        markup = owner_promote_users_keyboard(inline_users[:5])
        
        await ui_state_service.show_current_menu(
            bot, session, message.from_user.id,
            custom_text="Введите числовой Telegram ID пользователя для назначения менеджером, или выберите из списка ниже:",
            reason="owner_promote_prompt"
        )
        await message.answer("Список последних активных пользователей:", reply_markup=markup)

@router.message(IsOwnerAwaitingManagerId(), F.chat.type == "private")
async def owner_capture_manager_id(
    message: Message,
    bot: Bot,
    ui_state_service: UIStateService,
) -> None:
    if message.from_user is None:
        return
        
    text = message.text.strip() if message.text else ""
    if text in {OWNER_CANCEL, OWNER_BACK} or text.startswith("/"):
        return
        
    if not text.isdigit():
        await message.answer("⚠️ Некорректный ID. Пожалуйста, отправьте числовой Telegram ID (например, 123456789) или нажмите Отмена.")
        return
        
    telegram_user_id = int(text)
    settings = get_settings()
    
    if telegram_user_id == settings.owner_id:
        await message.answer("⚠️ Вы не можете назначить владельца менеджером.")
        return
        
    async with SessionLocal() as session:
        u_stmt = select(User).where(User.telegram_user_id == telegram_user_id)
        user = await session.scalar(u_stmt)
        
        if not user:
            markup = owner_promote_unknown_confirm_keyboard(telegram_user_id)
            await message.answer(
                f"⚠️ Пользователь с ID <code>{telegram_user_id}</code> не найден в базе данных (он никогда не запускал этого бота).\n\n"
                "Вы уверены, что хотите назначить его менеджером?",
                reply_markup=markup,
                parse_mode="HTML"
            )
            return
            
        await _promote_manager_db(telegram_user_id, message.from_user.id)
        await _reset_workflow_state(message.from_user.id)
        
        await ui_state_service.show_current_menu(
            bot, session, message.from_user.id,
            custom_text=f"✅ Пользователь {user.first_name or telegram_user_id} назначен менеджером.",
            reason="owner_promoted_manager"
        )

@router.callback_query(IsOwner(), F.data.startswith("owner:manager:disable_prompt:"))
async def owner_manager_disable_prompt_callback(
    callback: CallbackQuery,
) -> None:
    if callback.from_user is None or callback.data is None:
        return
    
    target_id = int(callback.data.split(":")[-1])
    settings = get_settings()
    if target_id == settings.owner_id:
        await callback.answer("⚠️ Вы не можете деактивировать главного владельца.", show_alert=True)
        return
        
    markup = owner_manager_disable_confirm_keyboard(target_id)
    await callback.message.edit_reply_markup(reply_markup=markup)
    await callback.answer()

@router.callback_query(IsOwner(), F.data.startswith("owner:manager:disable_confirm:"))
async def owner_manager_disable_confirm_callback(
    callback: CallbackQuery,
    bot: Bot,
    ui_state_service: UIStateService,
) -> None:
    if callback.from_user is None or callback.data is None:
        return
        
    target_id = int(callback.data.split(":")[-1])
    settings = get_settings()
    if target_id == settings.owner_id:
        await callback.answer("⚠️ Вы не можете деактивировать главного владельца.", show_alert=True)
        return
        
    async with SessionLocal() as session, session.begin():
        stmt = select(StaffMember).where(StaffMember.telegram_user_id == target_id)
        staff = await session.scalar(stmt)
        if staff:
            staff.status = StaffStatus.DISABLED.value
            staff.disabled_at = datetime.datetime.now(datetime.UTC)
            
    try:
        await callback.message.delete()
    except Exception:
        pass
    
    dummy_msg = Message(
        message_id=callback.message.message_id,
        date=callback.message.date,
        chat=callback.message.chat,
        from_user=callback.from_user,
    )
    await owner_managers_text(dummy_msg, bot, ui_state_service)
    await callback.answer("Менеджер деактивирован.")

@router.callback_query(IsOwner(), F.data.startswith("owner:manager:enable:"))
async def owner_manager_enable_callback(
    callback: CallbackQuery,
    bot: Bot,
    ui_state_service: UIStateService,
) -> None:
    if callback.from_user is None or callback.data is None:
        return
        
    target_id = int(callback.data.split(":")[-1])
    
    async with SessionLocal() as session, session.begin():
        stmt = select(StaffMember).where(StaffMember.telegram_user_id == target_id)
        staff = await session.scalar(stmt)
        if staff:
            staff.status = StaffStatus.ACTIVE.value
            staff.role = StaffRole.MANAGER.value
            staff.disabled_at = None
            
    try:
        await callback.message.delete()
    except Exception:
        pass
        
    dummy_msg = Message(
        message_id=callback.message.message_id,
        date=callback.message.date,
        chat=callback.message.chat,
        from_user=callback.from_user,
    )
    await owner_managers_text(dummy_msg, bot, ui_state_service)
    await callback.answer("Менеджер активирован.")

@router.callback_query(IsOwner(), F.data.startswith("owner:promote_user:"))
async def owner_promote_user_callback(
    callback: CallbackQuery,
    bot: Bot,
    ui_state_service: UIStateService,
) -> None:
    if callback.from_user is None or callback.data is None:
        return
        
    target_id = int(callback.data.split(":")[-1])
    settings = get_settings()
    if target_id == settings.owner_id:
        await callback.answer("⚠️ Вы не можете назначить владельца менеджером.", show_alert=True)
        return
        
    await _promote_manager_db(target_id, callback.from_user.id)
    await _reset_workflow_state(callback.from_user.id)
    
    try:
        await callback.message.delete()
    except Exception:
        pass
        
    async with SessionLocal() as session:
        await ui_state_service.show_current_menu(
            bot, session, callback.from_user.id,
            custom_text=f"✅ Пользователь с ID {target_id} назначен менеджером.",
            reason="owner_promoted_manager_callback"
        )
    await callback.answer()

@router.callback_query(IsOwner(), F.data.startswith("owner:promote_unknown_confirm:"))
async def owner_promote_unknown_confirm_callback(
    callback: CallbackQuery,
    bot: Bot,
    ui_state_service: UIStateService,
) -> None:
    if callback.from_user is None or callback.data is None:
        return
        
    target_id = int(callback.data.split(":")[-1])
    settings = get_settings()
    if target_id == settings.owner_id:
        await callback.answer("⚠️ Вы не можете назначить владельца менеджером.", show_alert=True)
        return
        
    await _promote_manager_db(target_id, callback.from_user.id)
    await _reset_workflow_state(callback.from_user.id)
    
    try:
        await callback.message.delete()
    except Exception:
        pass
        
    async with SessionLocal() as session:
        await ui_state_service.show_current_menu(
            bot, session, callback.from_user.id,
            custom_text=f"✅ Пользователь с ID {target_id} назначен менеджером.",
            reason="owner_promoted_manager_unknown_callback"
        )
    await callback.answer()

@router.message(IsOwner(), F.text == OWNER_MANAGER_STATS, F.chat.type == "private")
async def owner_manager_stats_text(
    message: Message,
    bot: Bot,
    ui_state_service: UIStateService,
) -> None:
    if message.from_user is None:
        return
        
    async with SessionLocal() as session:
        stmt = select(StaffMember).order_by(StaffMember.added_at.desc())
        staff_members = (await session.scalars(stmt)).all()
        
        if not staff_members:
            await ui_state_service.show_current_menu(
                bot, session, message.from_user.id,
                custom_text="В базе данных нет менеджеров для вывода статистики.",
                reason="owner_manager_stats_empty"
            )
            return
            
        stats_text = "📊 Статистика по менеджерам:\n\n"
        
        from app.db.models import Ticket
        
        for staff in staff_members:
            claimed_stmt = select(func.count(Ticket.id)).where(
                Ticket.assigned_manager_telegram_id == staff.telegram_user_id,
                Ticket.status == TicketStatus.CLAIMED.value
            )
            claimed_count = await session.scalar(claimed_stmt) or 0
            
            closed_stmt = select(func.count(Ticket.id)).where(
                Ticket.assigned_manager_telegram_id == staff.telegram_user_id,
                Ticket.status == TicketStatus.CLOSED.value
            )
            closed_count = await session.scalar(closed_stmt) or 0
            
            u_stmt = select(User).where(User.telegram_user_id == staff.telegram_user_id)
            user = await session.scalar(u_stmt)
            name = user.first_name or f"ID {staff.telegram_user_id}" if user else f"ID {staff.telegram_user_id}"
            
            stats_text += (
                f"👤 <b>{name}</b> (<code>{staff.telegram_user_id}</code>)\n"
                f"   Статус: {staff.status}\n"
                f"   В работе: {claimed_count}\n"
                f"   Закрыто: {closed_count}\n\n"
            )
            
        await ui_state_service.show_current_menu(
            bot, session, message.from_user.id,
            custom_text=stats_text,
            reason="owner_manager_stats"
        )
