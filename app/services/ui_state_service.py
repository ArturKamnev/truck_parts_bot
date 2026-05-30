# ruff: noqa: E501
from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db.models import OperatorSession
from app.keyboards.inline import (
    broadcast_button_selection_keyboard,
    broadcast_confirm_keyboard,
    broadcast_preview_keyboard,
    model_selection_keyboard,
    ticket_chat_keyboard,
)
from app.services.authorization_service import AuthorizationService
from app.services.keyboard_service import KeyboardService
from app.services.settings_service import SettingsService
from app.services.ticket_service import TicketService
from app.utils.enums import CustomerMode, OwnerWorkflowState, TicketStatus

logger = logging.getLogger(__name__)


class UIStateService:
    def __init__(
        self,
        settings: Settings,
        authorization: AuthorizationService,
        keyboard_service: KeyboardService,
        ticket_service: TicketService,
        settings_service: SettingsService,
    ) -> None:
        self.settings = settings
        self.authorization = authorization
        self.keyboard_service = keyboard_service
        self.ticket_service = ticket_service
        self.settings_service = settings_service

    async def show_current_menu(
        self,
        bot: Bot | None,
        session: AsyncSession,
        user_id: int,
        *,
        message: Message | None = None,
        custom_text: str | None = None,
        reason: str | None = None,
    ) -> None:
        # Load user and detect role
        user = await self.ticket_service.upsert_user_from_telegram(
            session,
            telegram_user_id=user_id,
            username=None,
            first_name=None,
            last_name=None,
        )
        role = self.authorization.detect_role(user_id)

        text = ""
        reply_markup: ReplyKeyboardMarkup | ReplyKeyboardRemove = ReplyKeyboardRemove()
        inline_markup: InlineKeyboardMarkup | None = None
        state_log_name = ""

        # Fetch operator session if support role
        op_session = None
        if role in {"owner", "manager"}:
            op_session = await session.get(OperatorSession, user_id)
            if op_session is None:
                op_session = OperatorSession(operator_telegram_id=user_id)
                session.add(op_session)
                await session.flush()

        if role == "owner":
            active_model = await self.settings_service.get_active_model(session)
            workflow_state = op_session.workflow_state if op_session else None
            selected_ticket_id = op_session.selected_ticket_id if op_session else None

            # Check owner sub-states
            if workflow_state in {
                OwnerWorkflowState.CREATING_BROADCAST_CONTENT.value,
                OwnerWorkflowState.CHOOSING_BROADCAST_BUTTONS.value,
                OwnerWorkflowState.PREVIEWING_BROADCAST.value,
                OwnerWorkflowState.CONFIRMING_BROADCAST.value,
            }:
                from app.db.models import Broadcast

                draft = None
                if op_session and op_session.active_broadcast_id:
                    draft = await session.get(Broadcast, op_session.active_broadcast_id)

                if workflow_state == OwnerWorkflowState.CREATING_BROADCAST_CONTENT.value:
                    text = "Отправьте сообщение для рассылки. Можно отправить текст, фото, видео, документ или файл с подписью."
                elif workflow_state == OwnerWorkflowState.CHOOSING_BROADCAST_BUTTONS.value:
                    text = f"Черновик #{draft.id if draft else ''} сохранён.\nДобавить кнопки к сообщению?"
                    inline_markup = broadcast_button_selection_keyboard(self.settings)
                elif workflow_state == OwnerWorkflowState.PREVIEWING_BROADCAST.value:
                    text = "Предпросмотр рассылки:"
                    inline_markup = broadcast_preview_keyboard()
                elif workflow_state == OwnerWorkflowState.CONFIRMING_BROADCAST.value:
                    from app.utils.enums import BroadcastButtonSelection

                    buttons = {
                        BroadcastButtonSelection.NONE.value: "без кнопок",
                        BroadcastButtonSelection.INSTAGRAM.value: "Instagram",
                        BroadcastButtonSelection.SITE.value: "официальный сайт",
                        BroadcastButtonSelection.BOTH.value: "Instagram + сайт",
                    }.get(draft.button_selection if draft else "none", "без кнопок")
                    preview = (draft.content_preview or "Без текста")[:500] if draft else ""
                    text = (
                        "Подтвердите массовую отправку.\n\n"
                        f"Получателей: {draft.recipient_count if draft else 0}\n"
                        f"Сообщение: {preview}\n"
                        f"Кнопки: {buttons}\n\n"
                        "После подтверждения сообщение будет отправлено клиентам."
                    )
                    inline_markup = broadcast_confirm_keyboard(draft.id) if draft else None
                state_log_name = f"broadcast_{workflow_state}"
            elif workflow_state == "MODEL_SELECTION":
                text = f"Выберите модель AI\nАктивная модель: {active_model}"
                inline_markup = model_selection_keyboard(active_model)
                state_log_name = "model_selection"
            elif selected_ticket_id is not None:
                text = await self._ticket_chat_text(session, selected_ticket_id)
                inline_markup = ticket_chat_keyboard(selected_ticket_id)
                state_log_name = "supervisor_ticket_reply"
            else:
                text = f"Панель владельца\nАктивная модель: {active_model}"
                state_log_name = "normal_panel"

            reply_markup = self.keyboard_service.get_owner_keyboard(
                workflow_state, selected_ticket_id
            )

        elif role == "manager":
            selected_ticket_id = op_session.selected_ticket_id if op_session else None
            notifications_enabled = await self.ticket_service.get_manager_notifications_enabled(
                session, manager_telegram_id=user_id
            )

            if selected_ticket_id is not None:
                text = await self._ticket_chat_text(session, selected_ticket_id)
                inline_markup = ticket_chat_keyboard(selected_ticket_id)
                state_log_name = "manager_ticket_reply"
            else:
                text = "Панель менеджера открыта. Выберите действие."
                state_log_name = "manager_main_menu"

            reply_markup = self.keyboard_service.get_manager_keyboard(
                selected_ticket_id, notifications_enabled
            )

        else:  # customer
            active_ticket = await self.ticket_service.get_active_ticket(
                session, customer_id=user.id
            )
            effective_mode = user.mode

            if user.mode == CustomerMode.REQUESTING_MANAGER.value:
                if active_ticket is not None:
                    user.mode = CustomerMode.WAITING_MANAGER.value
                    effective_mode = CustomerMode.WAITING_MANAGER.value
                    await session.flush()

            if active_ticket is None and effective_mode in {
                CustomerMode.WAITING_MANAGER.value,
                CustomerMode.MANAGER_CHAT.value,
            }:
                user.mode = CustomerMode.AI_CHAT.value
                effective_mode = CustomerMode.AI_CHAT.value
                await session.flush()

            if effective_mode == CustomerMode.REQUESTING_MANAGER.value:
                text = "Опишите ваш вопрос одним сообщением или приложите фото, видео или документ. Менеджер увидит ваше обращение."
                state_log_name = "customer_requesting"
            elif active_ticket is not None:
                if active_ticket.status == TicketStatus.OPEN.value:
                    text = "У вас уже есть открытое обращение. Ожидаем свободного менеджера. Вы можете отправить дополнительные сообщения или файлы."
                    state_log_name = "customer_waiting"
                else:  # CLAIMED
                    text = "Менеджер уже подключен. Напишите сообщение в этот чат."
                    state_log_name = "customer_chatting"
            else:
                text = (
                    "Здравствуйте! Я AI-ассистент компании. Напишите вопрос или выберите действие."
                )
                state_log_name = "customer_ai_chat"

            reply_markup = self.keyboard_service.get_customer_keyboard(
                effective_mode, user.broadcasts_enabled
            )

        if custom_text is not None:
            text = custom_text

        # Log transition cleanly
        logger.info(
            "UIStateRefresh user_id=%s role=%s state=%s reason=%s keyboard=%s",
            user_id,
            role,
            state_log_name,
            reason or "unspecified",
            type(reply_markup).__name__,
        )

        # Send state message
        if message is not None:
            await message.answer(
                text=text,
                reply_markup=reply_markup,
            )
            if inline_markup:
                await message.answer(
                    text="Дополнительные опции:",
                    reply_markup=inline_markup,
                )
        elif bot is not None:
            await bot.send_message(
                chat_id=user_id,
                text=text,
                reply_markup=reply_markup,
            )
            if inline_markup:
                await bot.send_message(
                    chat_id=user_id,
                    text="Дополнительные опции:",
                    reply_markup=inline_markup,
                )
        else:
            logger.warning(
                "No message or bot context provided to send UI refresh to user_id=%s", user_id
            )

    async def _ticket_chat_text(self, session: AsyncSession, ticket_id: int) -> str:
        ticket = await self.ticket_service.get_ticket(session, ticket_id=ticket_id)
        messages = await self.ticket_service.get_recent_ticket_messages(
            session, ticket_id=ticket.id, limit=6
        )
        username = f" @{ticket.customer.username}" if ticket.customer.username else ""
        status = "В работе" if ticket.status == TicketStatus.CLAIMED.value else "Открыто"
        history = "\n".join(
            f"{message.sender_type}: {message.text_preview or message.content}"
            for message in messages
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
