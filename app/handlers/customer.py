from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message

from app.db.session import SessionLocal
from app.filters.roles import IsCustomer
from app.keyboards.customer import (
    ASK_AI,
    BROADCASTS_DISABLED,
    BROADCASTS_ENABLED,
    CANCEL_ACTIVE_REQUEST,
    CANCEL_MANAGER_REQUEST,
    CLOSE_MANAGER_CHAT,
    CONTACT_MANAGER,
    customer_cancel_confirmation_keyboard,
    customer_keyboard,
    manager_chat_customer_keyboard,
    requesting_manager_keyboard,
    waiting_manager_keyboard,
)
from app.keyboards.manager import manager_keyboard
from app.keyboards.owner import owner_panel_keyboard
from app.services.ai_service import AIService
from app.services.ai_streaming_lock import AIStreamingLockRegistry, default_streaming_locks
from app.services.authorization_service import AuthorizationService
from app.services.relay_service import RelayService
from app.services.settings_service import SettingsService
from app.services.telegram_stream_renderer import TelegramPartialResponseRenderer
from app.services.ticket_service import TicketService
from app.utils.enums import AIMessageRole, CustomerMode, TicketMessageSenderType, TicketStatus
from app.utils.exceptions import (
    AIServiceError,
    DuplicateActiveTicketError,
    UnsupportedRelayContentError,
)

logger = logging.getLogger(__name__)
router = Router(name="customer")

CUSTOMER_MENU_TEXTS = {
    ASK_AI,
    CONTACT_MANAGER,
    CANCEL_MANAGER_REQUEST,
    CANCEL_ACTIVE_REQUEST,
    CLOSE_MANAGER_CHAT,
    BROADCASTS_ENABLED,
    BROADCASTS_DISABLED,
}


@router.message(CommandStart(), F.chat.type == "private")
async def start(
    message: Message,
    ticket_service: TicketService,
    authorization: AuthorizationService,
    settings_service: SettingsService,
) -> None:
    if message.from_user is None:
        return
    role = authorization.detect_role(message.from_user.id)
    async with SessionLocal() as session, session.begin():
        user = await ticket_service.upsert_user_from_telegram(
            session,
            telegram_user_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
        )
        active_ticket = (
            await ticket_service.get_active_ticket(session, customer_id=user.id)
            if role == "customer"
            else None
        )
        active_model = await settings_service.get_active_model(session) if role == "owner" else None
        logger.info(
            "private_message_route user_id=%s role=%s route=start mode=%s ticket_status=%s",
            message.from_user.id,
            role,
            user.mode,
            active_ticket.status if active_ticket else None,
        )
    if role == "owner":
        await message.answer(
            f"Панель владельца\nАктивная модель: {active_model}",
            reply_markup=owner_panel_keyboard(),
        )
        return
    if role == "manager":
        await message.answer("Панель менеджера открыта.", reply_markup=manager_keyboard())
        return
    await message.answer(
        "Здравствуйте! Я AI-ассистент компании. Напишите вопрос или выберите действие.",
        reply_markup=customer_keyboard(broadcasts_enabled=user.broadcasts_enabled),
    )


@router.message(
    IsCustomer(),
    F.text.in_({BROADCASTS_ENABLED, BROADCASTS_DISABLED}),
    F.chat.type == "private",
)
async def toggle_broadcasts(message: Message, ticket_service: TicketService) -> None:
    if message.from_user is None:
        return
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
    await message.answer(text, reply_markup=customer_keyboard(broadcasts_enabled=enabled))


@router.message(IsCustomer(), F.text == ASK_AI, F.chat.type == "private")
async def ask_ai_button(message: Message, ticket_service: TicketService) -> None:
    if message.from_user is None:
        return
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
    if active_ticket is not None:
        await message.answer(
            _active_ticket_text(active_ticket.status),
            reply_markup=_ticket_keyboard(active_ticket.status),
        )
        return
    await message.answer(
        "Напишите ваш вопрос, и я отвечу по базе знаний компании.",
        reply_markup=customer_keyboard(),
    )


@router.message(IsCustomer(), F.text == CONTACT_MANAGER, F.chat.type == "private")
async def contact_manager(message: Message, ticket_service: TicketService) -> None:
    if message.from_user is None:
        return
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
            await message.answer(
                _active_ticket_text(active_ticket.status),
                reply_markup=_ticket_keyboard(active_ticket.status),
            )
            return
        try:
            await ticket_service.begin_manager_request(session, customer=customer)
        except DuplicateActiveTicketError:
            await message.answer(
                "У вас уже есть активное обращение. Менеджер ответит здесь.",
                reply_markup=waiting_manager_keyboard(),
            )
            return
    await message.answer(
        "Опишите ваш вопрос одним сообщением или приложите фото, видео или документ. "
        "Менеджер увидит ваше обращение.",
        reply_markup=requesting_manager_keyboard(),
    )


@router.message(
    IsCustomer(),
    F.text.in_({CANCEL_MANAGER_REQUEST, CANCEL_ACTIVE_REQUEST, CLOSE_MANAGER_CHAT}),
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
) -> None:
    if callback.from_user is None or callback.data is None:
        return
    if callback.data.endswith(":no"):
        await callback.message.answer("Хорошо, продолжаем.", reply_markup=customer_keyboard())
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
        await bot.send_message(
            chat_id=manager_to_notify,
            text=f"Клиент отменил обращение #{ticket_id}.",
        )
    await callback.message.answer(
        "Обращение отменено. Теперь можно снова задавать вопросы AI-ассистенту.",
        reply_markup=customer_keyboard(),
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
) -> None:
    if message.from_user is None or message.text is None:
        return
    if message.text in CUSTOMER_MENU_TEXTS:
        return
    if message.text.startswith("/"):
        await message.answer("Выберите действие в меню или напишите вопрос обычным сообщением.")
        return
    await _handle_customer_content(
        message, bot, ticket_service, relay_service, ai_service, streaming_locks
    )


@router.message(IsCustomer(), F.chat.type == "private")
async def private_media_message(
    message: Message,
    bot: Bot,
    ticket_service: TicketService,
    relay_service: RelayService,
    ai_service: AIService,
    streaming_locks: AIStreamingLockRegistry | None = None,
) -> None:
    if message.from_user is None:
        return
    await _handle_customer_content(
        message, bot, ticket_service, relay_service, ai_service, streaming_locks
    )


async def _handle_customer_content(
    message: Message,
    bot: Bot,
    ticket_service: TicketService,
    relay_service: RelayService,
    ai_service: AIService,
    streaming_locks: AIStreamingLockRegistry | None = None,
) -> None:
    if message.from_user is None:
        return
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
                await message.answer(
                    "Этот тип сообщения нельзя безопасно передать менеджеру. "
                    "Отправьте текст, фото, видео, документ, GIF, аудио или голосовое сообщение.",
                    reply_markup=requesting_manager_keyboard(),
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
            await relay_service.notify_managers_about_new_ticket(bot, session, ticket=ticket)
            await message.answer(
                "Ваше обращение принято. Менеджер ответит вам в этом чате. "
                "Вы можете отправить дополнительные сообщения или файлы.",
                reply_markup=waiting_manager_keyboard(),
            )
            return

        if active_ticket is not None:
            try:
                delivered = await relay_service.relay_customer_message(
                    bot, session, ticket=active_ticket, customer=customer, message=message
                )
            except UnsupportedRelayContentError as exc:
                await message.answer(str(exc), reply_markup=_ticket_keyboard(active_ticket.status))
                return
            if delivered:
                await message.answer(
                    "Сообщение передано менеджеру.",
                    reply_markup=_ticket_keyboard(active_ticket.status),
                )
            else:
                await message.answer(
                    "Сообщение сохранено. Менеджер увидит его, когда возьмёт обращение.",
                    reply_markup=waiting_manager_keyboard(),
                )
            return

        if getattr(message, "text", None) is None:
            await message.answer(
                "Файлы можно отправить после выбора «Связаться с менеджером».",
                reply_markup=customer_keyboard(),
            )
            return

        customer.mode = CustomerMode.AI_CHAT.value
        customer_id = customer.id

    streaming_locks = streaming_locks or default_streaming_locks
    acquired = await streaming_locks.acquire(customer_id)
    if not acquired:
        await message.answer(
            "Дождитесь окончания текущего ответа.",
            reply_markup=customer_keyboard(),
        )
        return

    try:
        if getattr(ai_service, "streaming_enabled", False):
            await _answer_customer_with_streaming(message, bot, ai_service, customer_id=customer_id)
        else:
            await _answer_customer_without_streaming(message, ai_service, customer_id=customer_id)
    finally:
        await streaming_locks.release(customer_id)


async def _answer_customer_without_streaming(
    message: Message,
    ai_service: AIService,
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
        try:
            answer, model_id = await ai_service.answer(session, customer_id=customer_id)
        except AIServiceError:
            logger.info("AI answer failed for telegram_user_id=%s", message.from_user.id)
            await message.answer(
                "Не удалось получить ответ AI-ассистента. "
                "Попробуйте ещё раз или свяжитесь с менеджером.",
                reply_markup=customer_keyboard(),
            )
            return
        await ai_service.save_message(
            session,
            customer_id=customer_id,
            role=AIMessageRole.ASSISTANT,
            content=answer,
            model_id=model_id,
        )
    await message.answer(answer, reply_markup=customer_keyboard())


async def _answer_customer_with_streaming(
    message: Message,
    bot: Bot,
    ai_service: AIService,
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
        request = await ai_service.prepare_chat_completion(session, customer_id=customer_id)

    settings = ai_service.settings
    renderer = TelegramPartialResponseRenderer.from_settings(settings)
    await renderer.start(message, bot)

    chunks: list[str] = []
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
            await renderer.finalize(bot, message.chat.id, answer, reply_markup=customer_keyboard())
            await _save_assistant_answer(ai_service, customer_id, answer, request.model_id)
            return

        logger.info("AI stream failed before text for telegram_user_id=%s", message.from_user.id)
        await _fallback_to_non_streaming_after_stream_failure(
            message, bot, renderer, ai_service, customer_id=customer_id
        )
        return

    answer = "".join(chunks).strip()
    if not answer:
        await _fallback_to_non_streaming_after_stream_failure(
            message, bot, renderer, ai_service, customer_id=customer_id
        )
        return

    await renderer.finalize(bot, message.chat.id, answer, reply_markup=customer_keyboard())
    await _save_assistant_answer(ai_service, customer_id, answer, request.model_id)


async def _fallback_to_non_streaming_after_stream_failure(
    message: Message,
    bot: Bot,
    renderer: TelegramPartialResponseRenderer,
    ai_service: AIService,
    *,
    customer_id: int,
) -> None:
    try:
        async with SessionLocal() as session, session.begin():
            answer, model_id = await ai_service.answer(session, customer_id=customer_id)
            await ai_service.save_message(
                session,
                customer_id=customer_id,
                role=AIMessageRole.ASSISTANT,
                content=answer,
                model_id=model_id,
            )
    except AIServiceError:
        logger.info("AI fallback answer failed for telegram_user_id=%s", message.from_user.id)
        await renderer.finalize(
            bot,
            message.chat.id,
            "Не удалось получить ответ AI-ассистента. "
            "Попробуйте ещё раз или свяжитесь с менеджером.",
            reply_markup=customer_keyboard(),
        )
        return

    await renderer.finalize(bot, message.chat.id, answer, reply_markup=customer_keyboard())


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
    suffix = (
        "Ответ был прерван. Попробуйте задать вопрос ещё раз или свяжитесь с менеджером."
    )
    if partial:
        return f"{partial}\n\n{suffix}"
    return suffix


def _active_ticket_text(status: str) -> str:
    if status == TicketStatus.OPEN.value:
        return "У вас уже есть открытое обращение. Ожидаем свободного менеджера."
    if status == TicketStatus.CLAIMED.value:
        return "Менеджер уже подключен. Напишите сообщение в этот чат."
    return "У вас уже есть активное обращение."


def _ticket_keyboard(status: str):
    if status == TicketStatus.CLAIMED.value:
        return manager_chat_customer_keyboard()
    return waiting_manager_keyboard()
