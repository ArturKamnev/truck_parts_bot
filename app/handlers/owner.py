from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.filters import BaseFilter, Command
from aiogram.types import CallbackQuery, Message

from app.config import Settings
from app.db.session import SessionLocal
from app.filters.roles import IsOwner
from app.keyboards.owner import (
    broadcast_button_selection_keyboard,
    broadcast_cancel_keyboard,
    broadcast_confirm_keyboard,
    broadcast_preview_keyboard,
    broadcast_report_keyboard,
    model_selection_keyboard,
    owner_panel_keyboard,
    owner_ticket_keyboard,
)
from app.services.authorization_service import AuthorizationService
from app.services.broadcast_service import BroadcastService
from app.services.settings_service import SettingsService
from app.services.statistics_service import StatisticsService
from app.services.ticket_service import TicketService
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
            return (
                await broadcast_service.active_owner_state(
                    session, owner_telegram_id=message.from_user.id
                )
                is not None
            )


@router.message(IsOwner(), Command("admin"))
async def admin_panel(
    message: Message,
    authorization: AuthorizationService,
    settings_service: SettingsService,
) -> None:
    if message.from_user is None:
        return
    logger.info(
        "private_message_route user_id=%s role=owner route=admin_panel",
        message.from_user.id,
    )
    async with SessionLocal() as session:
        active_model = await settings_service.get_active_model(session)
    await message.answer(
        f"Панель владельца\nАктивная модель: {active_model}",
        reply_markup=owner_panel_keyboard(),
    )


@router.callback_query(IsOwner(), F.data == "owner:panel")
async def owner_panel_callback(
    callback: CallbackQuery,
    authorization: AuthorizationService,
    settings_service: SettingsService,
) -> None:
    if callback.from_user is None or not authorization.is_owner(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    async with SessionLocal() as session:
        active_model = await settings_service.get_active_model(session)
    await callback.message.edit_text(
        f"Панель владельца\nАктивная модель: {active_model}",
        reply_markup=owner_panel_keyboard(),
    )
    await callback.answer()


@router.callback_query(IsOwner(), F.data == "owner:models")
async def owner_models(
    callback: CallbackQuery,
    authorization: AuthorizationService,
    settings_service: SettingsService,
) -> None:
    if callback.from_user is None or not authorization.is_owner(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    async with SessionLocal() as session:
        active_model = await settings_service.get_active_model(session)
    await callback.message.edit_text(
        f"Выберите модель AI\nАктивная модель: {active_model}",
        reply_markup=model_selection_keyboard(active_model),
    )
    await callback.answer()


@router.callback_query(IsOwner(), F.data == "owner:stats")
async def owner_stats(
    callback: CallbackQuery,
    authorization: AuthorizationService,
    statistics_service: StatisticsService,
) -> None:
    if callback.from_user is None or not authorization.is_owner(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    async with SessionLocal() as session:
        stats = await statistics_service.owner_stats(session)
    await callback.message.edit_text(
        _format_owner_stats(stats), reply_markup=owner_panel_keyboard()
    )
    await callback.answer()


@router.callback_query(IsOwner(), F.data == "owner:open_tickets")
async def owner_open_tickets(
    callback: CallbackQuery,
    authorization: AuthorizationService,
    ticket_service: TicketService,
) -> None:
    if callback.from_user is None or not authorization.is_owner(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    async with SessionLocal() as session:
        tickets = await ticket_service.list_active_tickets(session)
    if not tickets:
        await callback.message.edit_text(
            "Открытых обращений нет.", reply_markup=owner_panel_keyboard()
        )
        await callback.answer()
        return
    await callback.message.edit_text(
        "Активные обращения отправлены ниже.", reply_markup=owner_panel_keyboard()
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
    authorization: AuthorizationService,
    broadcast_service: BroadcastService,
) -> None:
    if callback.from_user is None or not authorization.is_owner(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    async with SessionLocal() as session, session.begin():
        await broadcast_service.start_draft(session, owner_telegram_id=callback.from_user.id)
    await callback.message.answer(
        "Отправьте сообщение для рассылки. Можно отправить текст, фото, видео, "
        "документ или файл с подписью.",
        reply_markup=broadcast_cancel_keyboard(),
    )
    await callback.answer()


@router.callback_query(IsOwner(), F.data == "broadcast:history")
async def broadcast_history(
    callback: CallbackQuery,
    authorization: AuthorizationService,
    broadcast_service: BroadcastService,
) -> None:
    if callback.from_user is None or not authorization.is_owner(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    async with SessionLocal() as session:
        broadcasts = await broadcast_service.recent_broadcasts(session)
    if not broadcasts:
        await callback.message.answer(
            "История рассылок пока пуста.", reply_markup=owner_panel_keyboard()
        )
        await callback.answer()
        return
    for broadcast in broadcasts:
        await callback.message.answer(
            _format_broadcast_history_item(broadcast),
            reply_markup=broadcast_report_keyboard(broadcast.id),
        )
    await callback.answer()


@router.callback_query(IsOwner(), F.data == "broadcast:cancel")
async def broadcast_cancel(
    callback: CallbackQuery,
    authorization: AuthorizationService,
    broadcast_service: BroadcastService,
) -> None:
    if callback.from_user is None or not authorization.is_owner(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    async with SessionLocal() as session, session.begin():
        await broadcast_service.cancel_active_draft(
            session, owner_telegram_id=callback.from_user.id
        )
    await callback.message.answer("Рассылка отменена.", reply_markup=owner_panel_keyboard())
    await callback.answer()


@router.callback_query(IsOwner(), F.data == "broadcast:restart")
async def broadcast_restart(
    callback: CallbackQuery,
    authorization: AuthorizationService,
    broadcast_service: BroadcastService,
) -> None:
    if callback.from_user is None or not authorization.is_owner(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    async with SessionLocal() as session, session.begin():
        await broadcast_service.start_draft(session, owner_telegram_id=callback.from_user.id)
    await callback.message.answer(
        "Отправьте новое сообщение для рассылки.",
        reply_markup=broadcast_cancel_keyboard(),
    )
    await callback.answer()


@router.callback_query(IsOwner(), F.data.startswith("broadcast:buttons:"))
async def broadcast_buttons(
    callback: CallbackQuery,
    bot: Bot,
    authorization: AuthorizationService,
    broadcast_service: BroadcastService,
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
    await callback.message.answer(
        "Предпросмотр рассылки:", reply_markup=broadcast_preview_keyboard()
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
        reply_markup=broadcast_preview_keyboard(),
    )
    await callback.answer()


@router.callback_query(IsOwner(), F.data == "broadcast:send_all")
async def broadcast_send_all(
    callback: CallbackQuery,
    authorization: AuthorizationService,
    broadcast_service: BroadcastService,
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
    await callback.message.answer(
        _format_broadcast_confirmation(broadcast, recipient_count),
        reply_markup=broadcast_confirm_keyboard(broadcast.id),
    )
    await callback.answer()


@router.callback_query(IsOwner(), F.data.startswith("broadcast:confirm:"))
async def broadcast_confirm(
    callback: CallbackQuery,
    bot: Bot,
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
    await callback.message.answer(
        f"Рассылка #{broadcast.id} поставлена в отправку. "
        f"Получателей: {broadcast.recipient_count}.",
        reply_markup=owner_panel_keyboard(),
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


@router.message(IsOwnerBroadcasting(), F.text == "❌ Отмена", F.chat.type == "private")
async def broadcast_cancel_message(message: Message, broadcast_service: BroadcastService) -> None:
    if message.from_user is None:
        return
    async with SessionLocal() as session, session.begin():
        await broadcast_service.cancel_active_draft(session, owner_telegram_id=message.from_user.id)
    await message.answer("Рассылка отменена.", reply_markup=owner_panel_keyboard())


@router.message(IsOwnerBroadcasting(), F.chat.type == "private")
async def broadcast_capture_message(
    message: Message,
    settings: Settings,
    broadcast_service: BroadcastService,
) -> None:
    if message.from_user is None:
        return
    async with SessionLocal() as session, session.begin():
        state = await broadcast_service.active_owner_state(
            session, owner_telegram_id=message.from_user.id
        )
        if state != OwnerWorkflowState.CREATING_BROADCAST_CONTENT.value:
            appended = await broadcast_service.append_album_message(
                session, owner_telegram_id=message.from_user.id, message=message
            )
            if appended:
                return
            await message.answer("Выберите действие с текущим черновиком.")
            return
        try:
            broadcast = await broadcast_service.capture_content(
                session, owner_telegram_id=message.from_user.id, message=message
            )
        except UnsupportedRelayContentError as exc:
            await message.answer(str(exc), reply_markup=broadcast_cancel_keyboard())
            return
    await message.answer(
        f"Черновик #{broadcast.id} сохранён.\nДобавить кнопки к сообщению?",
        reply_markup=broadcast_button_selection_keyboard(settings),
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


def _format_broadcast_confirmation(broadcast, recipient_count: int) -> str:
    buttons = {
        BroadcastButtonSelection.NONE.value: "без кнопок",
        BroadcastButtonSelection.INSTAGRAM.value: "Instagram",
        BroadcastButtonSelection.SITE.value: "официальный сайт",
        BroadcastButtonSelection.BOTH.value: "Instagram + сайт",
    }.get(broadcast.button_selection, "без кнопок")
    preview = (broadcast.content_preview or "Без текста")[:500]
    return (
        "Подтвердите массовую отправку.\n\n"
        f"Получателей: {recipient_count}\n"
        f"Сообщение: {preview}\n"
        f"Кнопки: {buttons}\n\n"
        "После подтверждения сообщение будет отправлено клиентам."
    )
