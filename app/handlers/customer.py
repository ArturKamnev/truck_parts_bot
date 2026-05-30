# ruff: noqa: E501
from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message

from app.db.models import OperatorSession, User
from app.db.session import SessionLocal
from app.filters.roles import IsCustomer
from app.keyboards.constants import (
    CUSTOMER_ASK_AI,
    CUSTOMER_BROADCASTS_OFF,
    CUSTOMER_BROADCASTS_ON,
    CUSTOMER_CANCEL,
    CUSTOMER_CANCEL_REQUEST,
    CUSTOMER_CLOSE_CHAT,
    CUSTOMER_CONTACT_MANAGER,
)
from app.keyboards.inline import customer_cancel_confirmation_keyboard
from app.services.ai_service import AIService
from app.services.ai_streaming_lock import AIStreamingLockRegistry, default_streaming_locks
from app.services.authorization_service import AuthorizationService
from app.services.broadcast_service import BroadcastService
from app.services.keyboard_service import KeyboardService
from app.services.relay_service import RelayService
from app.services.settings_service import SettingsService
from app.services.telegram_stream_renderer import TelegramPartialResponseRenderer
from app.services.ticket_service import TicketService
from app.services.ui_state_service import UIStateService
from app.utils.enums import (
    AIMessageRole,
    CustomerMode,
    OwnerWorkflowState,
    TicketMessageSenderType,
)
from app.utils.exceptions import (
    AIServiceError,
    DuplicateActiveTicketError,
    UnsupportedRelayContentError,
)

logger = logging.getLogger(__name__)
router = Router(name="customer")

CUSTOMER_MENU_TEXTS = {
    CUSTOMER_ASK_AI,
    CUSTOMER_CONTACT_MANAGER,
    CUSTOMER_CANCEL,
    CUSTOMER_CANCEL_REQUEST,
    CUSTOMER_CLOSE_CHAT,
    CUSTOMER_BROADCASTS_ON,
    CUSTOMER_BROADCASTS_OFF,
}


def _get_ui_services(
    message: Message | CallbackQuery,
    ticket_service: TicketService | None,
    authorization: AuthorizationService | None,
    settings_service: SettingsService | None,
    ui_state_service: UIStateService | None,
    keyboard_service: KeyboardService | None = None,
) -> tuple[UIStateService, KeyboardService]:
    kb = keyboard_service or KeyboardService()
    if ui_state_service is not None:
        return ui_state_service, kb

    auth = authorization
    if auth is None and ticket_service is not None:
        auth = getattr(ticket_service, "_authorization", None)
    if auth is None:
        from app.config import get_settings

        auth = AuthorizationService(get_settings())

    ts = ticket_service or TicketService(auth)
    settings = None
    if settings_service:
        settings = settings_service._settings
    else:
        from app.config import get_settings

        settings = get_settings()

    ui = UIStateService(settings, auth, kb, ts, settings_service or SettingsService(settings, auth))
    return ui, kb


@router.message(Command("menu"), F.chat.type == "private")
async def menu_command(
    message: Message,
    bot: Bot | None = None,
    ui_state_service: UIStateService | None = None,
) -> None:
    if message.from_user is None:
        return
    active_bot = bot or getattr(message, "bot", None)
    async with SessionLocal() as session:
        ui, _ = _get_ui_services(message, None, None, None, ui_state_service)
        await ui.show_current_menu(
            active_bot, session, message.from_user.id, message=message, reason="menu_command"
        )


@router.message(Command("cancel"), F.chat.type == "private")
async def cancel_command(
    message: Message,
    bot: Bot | None = None,
    authorization: AuthorizationService | None = None,
    ticket_service: TicketService | None = None,
    broadcast_service: BroadcastService | None = None,
    ui_state_service: UIStateService | None = None,
) -> None:
    if message.from_user is None:
        return
    active_bot = bot or getattr(message, "bot", None)
    auth = authorization
    if auth is None and ticket_service is not None:
        auth = getattr(ticket_service, "_authorization", None)
    if auth is None:
        from app.config import get_settings

        auth = AuthorizationService(get_settings())

    ts = ticket_service or TicketService(auth)
    bs = broadcast_service or BroadcastService(None, auth, None)
    ui, _ = _get_ui_services(message, ts, auth, None, ui_state_service)

    user_id = message.from_user.id
    role = auth.detect_role(user_id)

    async with SessionLocal() as session, session.begin():
        if role == "owner":
            op_session = await session.get(OperatorSession, user_id)
            workflow_state = op_session.workflow_state if op_session else None
            selected_ticket_id = op_session.selected_ticket_id if op_session else None

            if workflow_state in {
                OwnerWorkflowState.CREATING_BROADCAST_CONTENT.value,
                OwnerWorkflowState.CHOOSING_BROADCAST_BUTTONS.value,
                OwnerWorkflowState.PREVIEWING_BROADCAST.value,
                OwnerWorkflowState.CONFIRMING_BROADCAST.value,
            }:
                await bs.cancel_active_draft(session, owner_telegram_id=user_id)
                await message.answer("Рассылка отменена.")
                await ui.show_current_menu(
                    active_bot, session, user_id, message=message, reason="owner_cancel_broadcast"
                )
            elif workflow_state == "MODEL_SELECTION":
                if op_session:
                    op_session.workflow_state = None
                await message.answer("Выбор модели отменён.")
                await ui.show_current_menu(
                    active_bot,
                    session,
                    user_id,
                    message=message,
                    reason="owner_cancel_model_selection",
                )
            elif selected_ticket_id is not None:
                await ts.clear_selected_ticket(session, operator_telegram_id=user_id)
                await message.answer("Выход из режима ответа.")
                await ui.show_current_menu(
                    active_bot,
                    session,
                    user_id,
                    message=message,
                    reason="owner_cancel_ticket_reply",
                )
            else:
                await message.answer("Нет активного временного режима для отмены.")
                await ui.show_current_menu(
                    active_bot, session, user_id, message=message, reason="owner_cancel_none"
                )

        elif role == "manager":
            op_session = await session.get(OperatorSession, user_id)
            selected_ticket_id = op_session.selected_ticket_id if op_session else None

            if selected_ticket_id is not None:
                await ts.clear_selected_ticket(session, operator_telegram_id=user_id)
                await message.answer("Выход из режима ответа.")
                await ui.show_current_menu(
                    active_bot,
                    session,
                    user_id,
                    message=message,
                    reason="manager_cancel_ticket_reply",
                )
            else:
                await message.answer("Нет active-режима для отмены.")
                await ui.show_current_menu(
                    active_bot, session, user_id, message=message, reason="manager_cancel_none"
                )

        else:  # customer
            customer = await ts.upsert_customer_from_telegram(
                session,
                telegram_user_id=user_id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name,
            )
            if customer.mode == CustomerMode.REQUESTING_MANAGER.value:
                customer.mode = CustomerMode.AI_CHAT.value
                await message.answer("Запрос отменён.")
                await ui.show_current_menu(
                    active_bot,
                    session,
                    user_id,
                    message=message,
                    reason="customer_cancel_requesting",
                )
            elif customer.mode in {
                CustomerMode.WAITING_MANAGER.value,
                CustomerMode.MANAGER_CHAT.value,
            }:
                await message.answer(
                    "Чтобы отменить обращение или завершить диалог, используйте соответствующую кнопку на клавиатуре."
                )
                await ui.show_current_menu(
                    active_bot,
                    session,
                    user_id,
                    message=message,
                    reason="customer_cancel_active_ticket_prevented",
                )
            else:
                await message.answer("Нет активного режима для отмены.")
                await ui.show_current_menu(
                    active_bot, session, user_id, message=message, reason="customer_cancel_none"
                )


@router.message(CommandStart(), F.chat.type == "private")
async def start(
    message: Message,
    ticket_service: TicketService,
    authorization: AuthorizationService,
    settings_service: SettingsService | None = None,
    bot: Bot | None = None,
    ui_state_service: UIStateService | None = None,
) -> None:
    if message.from_user is None:
        return
    active_bot = bot or getattr(message, "bot", None)
    async with SessionLocal() as session, session.begin():
        await ticket_service.upsert_user_from_telegram(
            session,
            telegram_user_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
        )
    async with SessionLocal() as session:
        ui, _ = _get_ui_services(
            message, ticket_service, authorization, settings_service, ui_state_service
        )
        await ui.show_current_menu(
            active_bot, session, message.from_user.id, message=message, reason="start_command"
        )


@router.message(
    IsCustomer(),
    F.text.in_({CUSTOMER_BROADCASTS_ON, CUSTOMER_BROADCASTS_OFF}),
    F.chat.type == "private",
)
async def toggle_broadcasts(
    message: Message,
    ticket_service: TicketService,
    bot: Bot | None = None,
    ui_state_service: UIStateService | None = None,
) -> None:
    if message.from_user is None:
        return
    active_bot = bot or getattr(message, "bot", None)
    async with SessionLocal() as session, session.begin():
        customer = await ticket_service.upsert_customer_from_telegram(
            session,
            telegram_user_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
        )
        customer.broadcasts_enabled = not customer.broadcasts_enabled
        enabled = customer.broadcasts_enabled
    text = "Рассылки включены." if enabled else "Рассылки выключены."
    async with SessionLocal() as session:
        ui, _ = _get_ui_services(message, ticket_service, None, None, ui_state_service)
        await ui.show_current_menu(
            active_bot,
            session,
            message.from_user.id,
            message=message,
            custom_text=text,
            reason="toggle_broadcasts",
        )


@router.message(IsCustomer(), F.text == CUSTOMER_ASK_AI, F.chat.type == "private")
async def ask_ai_button(
    message: Message,
    ticket_service: TicketService,
    bot: Bot | None = None,
    ui_state_service: UIStateService | None = None,
) -> None:
    if message.from_user is None:
        return
    active_bot = bot or getattr(message, "bot", None)
    async with SessionLocal() as session, session.begin():
        customer = await ticket_service.upsert_customer_from_telegram(
            session,
            telegram_user_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
        )
        active_ticket = await ticket_service.get_active_ticket(session, customer_id=customer.id)
        if active_ticket is None:
            customer.mode = CustomerMode.AI_CHAT.value
    async with SessionLocal() as session:
        ui, _ = _get_ui_services(message, ticket_service, None, None, ui_state_service)
        await ui.show_current_menu(
            active_bot, session, message.from_user.id, message=message, reason="ask_ai_button"
        )


@router.message(IsCustomer(), F.text == CUSTOMER_CONTACT_MANAGER, F.chat.type == "private")
async def contact_manager(
    message: Message,
    ticket_service: TicketService,
    bot: Bot | None = None,
    ui_state_service: UIStateService | None = None,
) -> None:
    if message.from_user is None:
        return
    active_bot = bot or getattr(message, "bot", None)
    logger.info(
        "private_message_route user_id=%s role=customer route=contact_manager",
        message.from_user.id,
    )
    async with SessionLocal() as session, session.begin():
        customer = await ticket_service.upsert_customer_from_telegram(
            session,
            telegram_user_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
        )
        active_ticket = await ticket_service.get_active_ticket(session, customer_id=customer.id)
        if active_ticket is not None:
            ui, _ = _get_ui_services(message, ticket_service, None, None, ui_state_service)
            await ui.show_current_menu(
                active_bot,
                session,
                message.from_user.id,
                message=message,
                reason="contact_manager_active_exists",
            )
            return
        try:
            await ticket_service.begin_manager_request(session, customer=customer)
        except DuplicateActiveTicketError:
            pass
    async with SessionLocal() as session:
        ui, _ = _get_ui_services(message, ticket_service, None, None, ui_state_service)
        await ui.show_current_menu(
            active_bot,
            session,
            message.from_user.id,
            message=message,
            reason="contact_manager_begin",
        )


@router.message(
    IsCustomer(),
    F.text.in_({CUSTOMER_CANCEL, CUSTOMER_CANCEL_REQUEST, CUSTOMER_CLOSE_CHAT}),
    F.chat.type == "private",
)
async def request_customer_cancel_confirmation(message: Message) -> None:
    await message.answer(
        "Подтвердите отмену обращения.",
        reply_markup=customer_cancel_confirmation_keyboard(),
    )


@router.callback_query(IsCustomer(), F.data.startswith("customer:cancel:"))
async def customer_cancel_callback(
    callback: CallbackQuery,
    bot: Bot,
    ticket_service: TicketService,
    ui_state_service: UIStateService | None = None,
) -> None:
    if callback.from_user is None or callback.data is None:
        return
    active_bot = bot or getattr(callback, "bot", None)
    if callback.data.endswith(":no"):
        async with SessionLocal() as session:
            ui, _ = _get_ui_services(callback, ticket_service, None, None, ui_state_service)
            await callback.message.answer("Хорошо, продолжаем.")
            await ui.show_current_menu(
                active_bot,
                session,
                callback.from_user.id,
                message=callback.message,
                reason="cancel_confirm_no",
            )
        await callback.answer()
        return

    manager_to_notify: int | None = None
    ticket_id: int | None = None
    async with SessionLocal() as session, session.begin():
        customer = await ticket_service.upsert_customer_from_telegram(
            session,
            telegram_user_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
            last_name=callback.from_user.last_name,
        )
        ticket = await ticket_service.cancel_by_customer(
            session, customer=customer, actor_telegram_id=callback.from_user.id
        )
        if ticket:
            manager_to_notify = ticket.assigned_manager_telegram_id
            ticket_id = ticket.id
    if manager_to_notify and ticket_id:
        try:
            await active_bot.send_message(
                chat_id=manager_to_notify,
                text=f"Клиент отменил обращение #{ticket_id}.",
            )
        except Exception:
            pass
    async with SessionLocal() as session:
        ui, _ = _get_ui_services(callback, ticket_service, None, None, ui_state_service)
        await callback.message.answer(
            "Обращение отменено. Теперь можно снова задавать вопросы AI-ассистенту."
        )
        await ui.show_current_menu(
            active_bot,
            session,
            callback.from_user.id,
            message=callback.message,
            reason="cancel_confirm_yes",
        )
    await callback.answer("Отменено")


@router.message(IsCustomer(), F.text, F.chat.type == "private")
async def private_text_message(
    message: Message,
    bot: Bot,
    ticket_service: TicketService,
    relay_service: RelayService,
    ai_service: AIService,
    streaming_locks: AIStreamingLockRegistry | None = None,
    ui_state_service: UIStateService | None = None,
    keyboard_service: KeyboardService | None = None,
) -> None:
    if message.from_user is None or message.text is None:
        return
    if message.text in CUSTOMER_MENU_TEXTS:
        return
    if message.text.startswith("/"):
        if message.text in {"/menu", "/cancel", "/start"}:
            return
        await message.answer("Выберите действие в меню или напишите вопрос обычным сообщением.")
        active_bot = bot or getattr(message, "bot", None)
        async with SessionLocal() as session:
            ui, _ = _get_ui_services(message, ticket_service, None, None, ui_state_service)
            await ui.show_current_menu(
                active_bot, session, message.from_user.id, message=message, reason="unknown_command"
            )
        return
    await _handle_customer_content(
        message,
        bot,
        ticket_service,
        relay_service,
        ai_service,
        streaming_locks,
        ui_state_service,
        keyboard_service,
    )


@router.message(IsCustomer(), F.chat.type == "private")
async def private_media_message(
    message: Message,
    bot: Bot,
    ticket_service: TicketService,
    relay_service: RelayService,
    ai_service: AIService,
    streaming_locks: AIStreamingLockRegistry | None = None,
    ui_state_service: UIStateService | None = None,
    keyboard_service: KeyboardService | None = None,
) -> None:
    if message.from_user is None:
        return
    await _handle_customer_content(
        message,
        bot,
        ticket_service,
        relay_service,
        ai_service,
        streaming_locks,
        ui_state_service,
        keyboard_service,
    )


async def _handle_customer_content(
    message: Message,
    bot: Bot,
    ticket_service: TicketService,
    relay_service: RelayService,
    ai_service: AIService,
    streaming_locks: AIStreamingLockRegistry | None = None,
    ui_state_service: UIStateService | None = None,
    keyboard_service: KeyboardService | None = None,
) -> None:
    if message.from_user is None:
        return
    active_bot = bot or getattr(message, "bot", None)
    ui, kb = _get_ui_services(
        message, ticket_service, None, None, ui_state_service, keyboard_service
    )

    async with SessionLocal() as session, session.begin():
        customer = await ticket_service.upsert_customer_from_telegram(
            session,
            telegram_user_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
        )
        active_ticket = await ticket_service.get_active_ticket(session, customer_id=customer.id)
        logger.info(
            "private_message_route user_id=%s role=customer route=customer_content mode=%s "
            "ticket_status=%s",
            message.from_user.id,
            customer.mode,
            active_ticket.status if active_ticket else None,
        )

        if customer.mode == CustomerMode.REQUESTING_MANAGER.value:
            try:
                metadata = relay_service.metadata_from_message(message)
                ticket = await ticket_service.create_ticket(
                    session,
                    customer=customer,
                    original_request=metadata.text_preview,
                    content_type=metadata.content_type,
                    source_chat_id=metadata.source_chat_id,
                    source_message_id=metadata.source_message_id,
                    media_group_id=metadata.media_group_id,
                )
            except (DuplicateActiveTicketError, UnsupportedRelayContentError):
                await ui.show_current_menu(
                    active_bot,
                    session,
                    message.from_user.id,
                    message=message,
                    custom_text="Этот тип сообщения нельзя безопасно передать менеджеру. Отправьте текст, фото, видео, документ, GIF, аудио или голосовое сообщение.",
                    reason="unsupported_relay_content",
                )
                return

            recent_ai = await ai_service.get_recent_history(session, customer_id=customer.id)
            if recent_ai:
                context = "\n".join(f"{msg.role}: {msg.content}" for msg in recent_ai[-6:])
                ticket_service.add_ticket_message(
                    session,
                    ticket=ticket,
                    sender_type=TicketMessageSenderType.SYSTEM,
                    sender_telegram_id=None,
                    content=f"Recent AI context:\n{context}",
                )
            await relay_service.notify_managers_about_new_ticket(active_bot, session, ticket=ticket)
            await ui.show_current_menu(
                active_bot,
                session,
                message.from_user.id,
                message=message,
                custom_text="Ваше обращение принято. Менеджер ответит вам в этом чате. Вы можете отправить дополнительные сообщения или файлы.",
                reason="ticket_created_success",
            )
            return

        if active_ticket is not None:
            try:
                delivered = await relay_service.relay_customer_message(
                    active_bot, session, ticket=active_ticket, customer=customer, message=message
                )
            except UnsupportedRelayContentError as exc:
                await ui.show_current_menu(
                    active_bot,
                    session,
                    message.from_user.id,
                    message=message,
                    custom_text=str(exc),
                    reason="relay_unsupported_during_ticket",
                )
                return
            if delivered:
                await ui.show_current_menu(
                    active_bot,
                    session,
                    message.from_user.id,
                    message=message,
                    custom_text="Сообщение передано менеджеру.",
                    reason="customer_message_delivered",
                )
            else:
                await ui.show_current_menu(
                    active_bot,
                    session,
                    message.from_user.id,
                    message=message,
                    custom_text="Сообщение сохранено. Менеджер увидит его, когда возьмёт обращение.",
                    reason="customer_message_stored",
                )
            return

        if getattr(message, "text", None) is None:
            await ui.show_current_menu(
                active_bot,
                session,
                message.from_user.id,
                message=message,
                custom_text="Файлы можно отправить после выбора «Связаться с менеджером».",
                reason="unsupported_media_in_ai_chat",
            )
            return

        customer.mode = CustomerMode.AI_CHAT.value
        customer_id = customer.id

    streaming_locks = streaming_locks or default_streaming_locks
    acquired = await streaming_locks.acquire(customer_id)
    if not acquired:
        async with SessionLocal() as session:
            await ui.show_current_menu(
                active_bot,
                session,
                message.from_user.id,
                message=message,
                custom_text="Дождитесь окончания текущего ответа.",
                reason="ai_stream_locked",
            )
        return

    try:
        if getattr(ai_service, "streaming_enabled", False):
            await _answer_customer_with_streaming(
                message, active_bot, ai_service, kb, customer_id=customer_id
            )
        else:
            await _answer_customer_without_streaming(
                message, ai_service, kb, customer_id=customer_id
            )
    finally:
        await streaming_locks.release(customer_id)


async def _answer_customer_without_streaming(
    message: Message,
    ai_service: AIService,
    keyboard_service: KeyboardService,
    *,
    customer_id: int,
) -> None:
    async with SessionLocal() as session, session.begin():
        await ai_service.save_message(
            session,
            customer_id=customer_id,
            role=AIMessageRole.USER,
            content=message.text or "",
        )
        customer = await session.get(User, customer_id)
        broadcasts_enabled = customer.broadcasts_enabled if customer else True
        try:
            answer, model_id = await ai_service.answer(session, customer_id=customer_id)
        except AIServiceError:
            logger.info("AI answer failed for telegram_user_id=%s", message.from_user.id)
            kb = keyboard_service.get_customer_keyboard(
                CustomerMode.AI_CHAT.value, broadcasts_enabled
            )
            await message.answer(
                "Не удалось получить ответ AI-ассистента. Попробуйте ещё раз или свяжитесь с менеджером.",
                reply_markup=kb,
            )
            return
        await ai_service.save_message(
            session,
            customer_id=customer_id,
            role=AIMessageRole.ASSISTANT,
            content=answer,
            model_id=model_id,
        )
    kb = keyboard_service.get_customer_keyboard(CustomerMode.AI_CHAT.value, broadcasts_enabled)
    await message.answer(answer, reply_markup=kb)


async def _answer_customer_with_streaming(
    message: Message,
    bot: Bot,
    ai_service: AIService,
    keyboard_service: KeyboardService,
    *,
    customer_id: int,
) -> None:
    async with SessionLocal() as session, session.begin():
        await ai_service.save_message(
            session,
            customer_id=customer_id,
            role=AIMessageRole.USER,
            content=message.text or "",
        )
        customer = await session.get(User, customer_id)
        broadcasts_enabled = customer.broadcasts_enabled if customer else True
        request = await ai_service.prepare_chat_completion(session, customer_id=customer_id)

    settings = ai_service.settings
    renderer = TelegramPartialResponseRenderer.from_settings(settings)
    await renderer.start(message, bot)

    chunks: list[str] = []
    kb = keyboard_service.get_customer_keyboard(CustomerMode.AI_CHAT.value, broadcasts_enabled)
    try:
        async for delta in ai_service.stream_chat_completion(
            model=request.model_id,
            messages=request.messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        ):
            chunks.append(delta)
            await renderer.render_partial(bot, message.chat.id, "".join(chunks))
    except AIServiceError:
        if chunks:
            logger.info(
                "AI stream interrupted after partial text for telegram_user_id=%s",
                message.from_user.id,
            )
            answer = _interrupted_answer("".join(chunks))
            await renderer.finalize(bot, message.chat.id, answer, reply_markup=kb)
            await _save_assistant_answer(ai_service, customer_id, answer, request.model_id)
            return

        logger.info("AI stream failed before text for telegram_user_id=%s", message.from_user.id)
        await _fallback_to_non_streaming_after_stream_failure(
            message, bot, renderer, ai_service, keyboard_service, customer_id=customer_id
        )
        return

    answer = "".join(chunks).strip()
    if not answer:
        await _fallback_to_non_streaming_after_stream_failure(
            message, bot, renderer, ai_service, keyboard_service, customer_id=customer_id
        )
        return

    await renderer.finalize(bot, message.chat.id, answer, reply_markup=kb)
    await _save_assistant_answer(ai_service, customer_id, answer, request.model_id)


async def _fallback_to_non_streaming_after_stream_failure(
    message: Message,
    bot: Bot,
    renderer: TelegramPartialResponseRenderer,
    ai_service: AIService,
    keyboard_service: KeyboardService,
    *,
    customer_id: int,
) -> None:
    try:
        async with SessionLocal() as session, session.begin():
            answer, model_id = await ai_service.answer(session, customer_id=customer_id)
            customer = await session.get(User, customer_id)
            broadcasts_enabled = customer.broadcasts_enabled if customer else True
            await ai_service.save_message(
                session,
                customer_id=customer_id,
                role=AIMessageRole.ASSISTANT,
                content=answer,
                model_id=model_id,
            )
    except AIServiceError:
        logger.info("AI fallback answer failed for telegram_user_id=%s", message.from_user.id)
        kb = keyboard_service.get_customer_keyboard(CustomerMode.AI_CHAT.value, True)
        await renderer.finalize(
            bot,
            message.chat.id,
            "Не удалось получить ответ AI-ассистента. Попробуйте ещё раз или свяжитесь с менеджером.",
            reply_markup=kb,
        )
        return

    kb = keyboard_service.get_customer_keyboard(CustomerMode.AI_CHAT.value, broadcasts_enabled)
    await renderer.finalize(bot, message.chat.id, answer, reply_markup=kb)


async def _save_assistant_answer(
    ai_service: AIService,
    customer_id: int,
    answer: str,
    model_id: str,
) -> None:
    async with SessionLocal() as session, session.begin():
        await ai_service.save_message(
            session,
            customer_id=customer_id,
            role=AIMessageRole.ASSISTANT,
            content=answer,
            model_id=model_id,
        )


def _interrupted_answer(partial_text: str) -> str:
    partial = partial_text.strip()
    suffix = "Ответ был прерван. Попробуйте задать вопрос ещё раз или свяжитесь с менеджером."
    if partial:
        return f"{partial}\n\n{suffix}"
    return suffix
