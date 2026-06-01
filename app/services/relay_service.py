from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db.models import Ticket, TicketMessage, User
from app.db.session import SessionLocal
from app.services.ai_service import AIService
from app.services.ticket_service import TicketService
from app.utils.enums import (
    TicketMessageContentType,
    TicketMessageDeliveryStatus,
    TicketMessageSenderType,
    TicketStatus,
)
from app.utils.exceptions import AuthorizationError, UnsupportedRelayContentError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RelayMessageMetadata:
    content_type: TicketMessageContentType
    source_chat_id: int | None
    source_message_id: int | None
    text_preview: str
    media_group_id: str | None


class MessageRelayService:
    def __init__(
        self, settings: Settings, ticket_service: TicketService, ai_service: AIService | None = None
    ) -> None:
        self._settings = settings
        self._ticket_service = ticket_service
        self._ai_service = ai_service
        self._media_group_buffers: dict[tuple[int, int, str], list[int]] = defaultdict(list)
        self._media_group_tasks: dict[tuple[int, int, str], asyncio.Task] = {}

    async def notify_managers_about_new_ticket(
        self, bot: Bot, session: AsyncSession, *, ticket: Ticket
    ) -> None:
        manager_ids = await self._started_manager_ids_with_notifications(session)
        if not manager_ids:
            return
        latest = await self._latest_preview(session, ticket_id=ticket.id)
        text = (
            f"Новое обращение #{ticket.id}\n"
            f"Клиент: {self.customer_display_name(ticket.customer)}\n"
            f"Сообщение: {latest}"
        )
        for manager_id in manager_ids:
            try:
                await bot.send_message(chat_id=manager_id, text=text)
            except (TelegramBadRequest, TelegramForbiddenError) as exc:
                logger.info(
                    "Could not notify manager_id=%s ticket_id=%s: %s",
                    manager_id,
                    ticket.id,
                    exc,
                )

    async def relay_customer_message(
        self,
        bot: Bot,
        session: AsyncSession,
        *,
        ticket: Ticket,
        customer: User,
        message: Any | None = None,
        text: str | None = None,
    ) -> bool:
        metadata = self.metadata_from_message(message) if message is not None else None
        content = metadata.text_preview if metadata is not None else (text or "")
        if not content:
            raise UnsupportedRelayContentError("Этот тип сообщения пока нельзя передать менеджеру.")

        delivery_status = TicketMessageDeliveryStatus.STORED
        ticket_message = self._ticket_service.add_ticket_message(
            session,
            ticket=ticket,
            sender_type=TicketMessageSenderType.CUSTOMER,
            sender_telegram_id=customer.telegram_user_id,
            content=content,
            content_type=metadata.content_type if metadata else TicketMessageContentType.TEXT,
            source_chat_id=metadata.source_chat_id if metadata else None,
            source_message_id=metadata.source_message_id if metadata else None,
            text_preview=content,
            media_group_id=metadata.media_group_id if metadata else None,
            delivery_status=delivery_status,
        )
        await session.flush()

        destination_ids = await self._customer_message_destinations(session, ticket=ticket)
        if not destination_ids:
            return False

        delivered = True
        for destination_id in destination_ids:
            if message is None:
                await bot.send_message(
                    chat_id=destination_id,
                    text=f"Сообщение клиента по обращению #{ticket.id}:\n{content}",
                )
                continue
            copied = await self._copy_customer_message(
                bot,
                ticket=ticket,
                message=message,
                destination_chat_id=destination_id,
                ticket_message=ticket_message,
            )
            delivered = delivered and copied

        ticket_message.delivery_status = (
            TicketMessageDeliveryStatus.DELIVERED.value
            if delivered
            else TicketMessageDeliveryStatus.FAILED.value
        )
        return delivered

    async def relay_manager_message_to_customer(
        self,
        bot: Bot,
        session: AsyncSession,
        *,
        ticket: Ticket,
        actor_telegram_id: int,
        message: Any | None = None,
        text: str | None = None,
    ) -> None:
        if not await self._ticket_service.can_send_manager_reply_db(
            session, ticket, actor_telegram_id
        ):
            raise AuthorizationError("This operator cannot reply to the customer")
        metadata = self.metadata_from_message(message) if message is not None else None
        content = metadata.text_preview if metadata is not None else (text or "")
        if not content:
            raise UnsupportedRelayContentError(
                "Этот тип сообщения нельзя безопасно передать клиенту."
            )
        if content.startswith("/"):
            raise AuthorizationError("Commands are not relayed")

        role = await self._ticket_service._authorization.detect_role_db(actor_telegram_id, session)
        sender_type = TicketMessageSenderType.OWNER if role in {"owner", "co_owner"} else TicketMessageSenderType.MANAGER
        ticket_message = self._ticket_service.add_ticket_message(
            session,
            ticket=ticket,
            sender_type=sender_type,
            sender_telegram_id=actor_telegram_id,
            content=content,
            content_type=metadata.content_type if metadata else TicketMessageContentType.TEXT,
            source_chat_id=metadata.source_chat_id if metadata else None,
            source_message_id=metadata.source_message_id if metadata else None,
            text_preview=content,
            media_group_id=metadata.media_group_id if metadata else None,
        )
        await session.flush()

        if message is None:
            await bot.send_message(chat_id=ticket.customer.telegram_user_id, text=content)
            ticket_message.delivery_status = TicketMessageDeliveryStatus.DELIVERED.value
            return

        copied = await self._copy_message_or_album(
            bot,
            message=message,
            destination_chat_id=ticket.customer.telegram_user_id,
            ticket_message=ticket_message,
        )
        ticket_message.delivery_status = (
            TicketMessageDeliveryStatus.DELIVERED.value
            if copied
            else TicketMessageDeliveryStatus.FAILED.value
        )

    async def copy_ticket_history_to_chat(
        self, bot: Bot, session: AsyncSession, *, ticket_id: int, destination_chat_id: int
    ) -> None:
        messages = await self._ticket_messages(session, ticket_id=ticket_id, limit=50)
        if not messages:
            await bot.send_message(
                chat_id=destination_chat_id,
                text="История обращения пока пуста.",
            )
            return

        await bot.send_message(chat_id=destination_chat_id, text=f"История обращения #{ticket_id}:")
        text_lines: list[str] = []
        grouped: dict[str, list[TicketMessage]] = defaultdict(list)
        for item in messages:
            label = self._sender_label(item.sender_type)
            preview = item.text_preview or item.content
            if item.source_chat_id and item.source_message_id:
                if text_lines:
                    await bot.send_message(chat_id=destination_chat_id, text="\n".join(text_lines))
                    text_lines = []
                if item.media_group_id and item.content_type in {
                    TicketMessageContentType.PHOTO.value,
                    TicketMessageContentType.VIDEO.value,
                }:
                    grouped[item.media_group_id].append(item)
                else:
                    await bot.send_message(chat_id=destination_chat_id, text=f"{label}: {preview}")
                    await self._copy_stored_message(bot, item, destination_chat_id)
            else:
                text_lines.append(f"{label}: {preview}")

        if text_lines:
            await bot.send_message(chat_id=destination_chat_id, text="\n".join(text_lines))

        for group in grouped.values():
            first = group[0]
            first_preview = first.text_preview or first.content
            await bot.send_message(
                chat_id=destination_chat_id,
                text=f"{self._sender_label(first.sender_type)}: {first_preview}",
            )
            await self._copy_stored_media_group(bot, group, destination_chat_id)

    def metadata_from_message(self, message: Any) -> RelayMessageMetadata:
        content_type = self._content_type(message)
        text_preview = self._preview(message, content_type)
        if not text_preview:
            text_preview = self._content_type_label(content_type)
        return RelayMessageMetadata(
            content_type=content_type,
            source_chat_id=getattr(getattr(message, "chat", None), "id", None),
            source_message_id=getattr(message, "message_id", None),
            text_preview=text_preview[:2000],
            media_group_id=getattr(message, "media_group_id", None),
        )

    async def _copy_customer_message(
        self,
        bot: Bot,
        *,
        ticket: Ticket,
        message: Any,
        destination_chat_id: int,
        ticket_message: TicketMessage,
    ) -> bool:
        try:
            await bot.send_message(
                chat_id=destination_chat_id,
                text=f"Сообщение клиента по обращению #{ticket.id}:",
            )
        except (TelegramBadRequest, TelegramForbiddenError) as exc:
            logger.info("Could not send ticket header for ticket_id=%s: %s", ticket.id, exc)
            return False
        return await self._copy_message_or_album(
            bot,
            message=message,
            destination_chat_id=destination_chat_id,
            ticket_message=ticket_message,
        )

    async def _copy_message_or_album(
        self,
        bot: Bot,
        *,
        message: Any,
        destination_chat_id: int,
        ticket_message: TicketMessage,
    ) -> bool:
        media_group_id = getattr(message, "media_group_id", None)
        content_type = ticket_message.content_type
        if media_group_id and content_type in {
            TicketMessageContentType.PHOTO.value,
            TicketMessageContentType.VIDEO.value,
        }:
            ticket_message.delivery_status = TicketMessageDeliveryStatus.PENDING_MEDIA_GROUP.value
            self._buffer_media_group(
                bot,
                source_chat_id=getattr(message.chat, "id", None),
                source_message_id=message.message_id,
                destination_chat_id=destination_chat_id,
                media_group_id=media_group_id,
                ticket_message_id=ticket_message.id,
            )
            return True
        try:
            await bot.copy_message(
                chat_id=destination_chat_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id,
            )
            return True
        except (TelegramBadRequest, TelegramForbiddenError) as exc:
            logger.info("Could not copy message_id=%s: %s", message.message_id, exc)
            return False

    def _buffer_media_group(
        self,
        bot: Bot,
        *,
        source_chat_id: int | None,
        source_message_id: int,
        destination_chat_id: int,
        media_group_id: str,
        ticket_message_id: int,
    ) -> None:
        if source_chat_id is None:
            return
        key = (source_chat_id, destination_chat_id, media_group_id)
        self._media_group_buffers[key].append(source_message_id)
        task_key = (*key, str(ticket_message_id))
        existing = self._media_group_tasks.get(task_key)
        if existing and not existing.done():
            existing.cancel()
        self._media_group_tasks[task_key] = asyncio.create_task(
            self._flush_media_group_later(bot, key, ticket_message_id)
        )

    async def _flush_media_group_later(
        self, bot: Bot, key: tuple[int, int, str], ticket_message_id: int
    ) -> None:
        await asyncio.sleep(1.2)
        source_chat_id, destination_chat_id, _media_group_id = key
        message_ids = sorted(set(self._media_group_buffers.pop(key, [])))
        status = TicketMessageDeliveryStatus.DELIVERED
        try:
            if len(message_ids) > 1:
                await bot.copy_messages(
                    chat_id=destination_chat_id,
                    from_chat_id=source_chat_id,
                    message_ids=message_ids,
                )
            elif message_ids:
                await bot.copy_message(
                    chat_id=destination_chat_id,
                    from_chat_id=source_chat_id,
                    message_id=message_ids[0],
                )
        except (TelegramBadRequest, TelegramForbiddenError) as exc:
            logger.info("Could not copy media group=%s: %s", key, exc)
            status = TicketMessageDeliveryStatus.FAILED
        async with SessionLocal() as session, session.begin():
            await self._ticket_service.set_ticket_message_delivery_status(
                session, ticket_message_id=ticket_message_id, delivery_status=status
            )

    async def _copy_stored_message(
        self, bot: Bot, item: TicketMessage, destination_chat_id: int
    ) -> None:
        if item.source_chat_id is None or item.source_message_id is None:
            return
        try:
            await bot.copy_message(
                chat_id=destination_chat_id,
                from_chat_id=item.source_chat_id,
                message_id=item.source_message_id,
            )
        except (TelegramBadRequest, TelegramForbiddenError) as exc:
            logger.info("Could not copy stored ticket_message_id=%s: %s", item.id, exc)
            await bot.send_message(
                chat_id=destination_chat_id,
                text="Вложение больше недоступно для копирования.",
            )

    async def _copy_stored_media_group(
        self, bot: Bot, group: list[TicketMessage], destination_chat_id: int
    ) -> None:
        source_chat_id = group[0].source_chat_id
        message_ids = [item.source_message_id for item in group if item.source_message_id]
        if source_chat_id is None or not message_ids:
            return
        try:
            await bot.copy_messages(
                chat_id=destination_chat_id,
                from_chat_id=source_chat_id,
                message_ids=message_ids,
            )
        except (TelegramBadRequest, TelegramForbiddenError) as exc:
            logger.info("Could not copy stored media group=%s: %s", group[0].media_group_id, exc)
            await bot.send_message(
                chat_id=destination_chat_id,
                text="Альбом больше недоступен для копирования.",
            )

    async def _customer_message_destinations(
        self, session: AsyncSession, *, ticket: Ticket
    ) -> list[int]:
        if ticket.status == TicketStatus.CLAIMED.value and ticket.assigned_manager_telegram_id:
            return [ticket.assigned_manager_telegram_id]
        if ticket.status == TicketStatus.OPEN.value:
            return await self._ticket_service.selected_owner_ids_for_ticket(
                session, ticket_id=ticket.id
            )
        return []

    async def _started_manager_ids_with_notifications(self, session: AsyncSession) -> list[int]:
        from app.db.models import StaffMember
        from app.utils.enums import StaffStatus

        # Query active managers from DB
        stmt_staff = select(StaffMember.telegram_user_id).where(StaffMember.status == StaffStatus.ACTIVE.value)
        db_staff_ids = set((await session.scalars(stmt_staff)).all())

        # Merge with settings manager IDs
        all_candidate_ids = db_staff_ids.union(self._settings.manager_ids)

        # Exclude explicitly disabled staff
        stmt_disabled = select(StaffMember.telegram_user_id).where(StaffMember.status == StaffStatus.DISABLED.value)
        disabled_ids = set((await session.scalars(stmt_disabled)).all())

        active_candidate_ids = all_candidate_ids - disabled_ids

        rows = await session.scalars(
            select(User.telegram_user_id).where(
                User.telegram_user_id.in_(active_candidate_ids)
            )
        )
        started_ids = list(rows)
        enabled_ids = []
        for manager_id in started_ids:
            enabled = await self._ticket_service.get_manager_notifications_enabled(
                session, manager_telegram_id=manager_id
            )
            if enabled:
                enabled_ids.append(manager_id)
        return enabled_ids


    async def _latest_preview(self, session: AsyncSession, *, ticket_id: int) -> str:
        messages = await self._ticket_messages(session, ticket_id=ticket_id, limit=1)
        if not messages:
            return "нет сообщений"
        return (messages[-1].text_preview or messages[-1].content)[:500]

    async def _ticket_messages(
        self, session: AsyncSession, *, ticket_id: int, limit: int
    ) -> list[TicketMessage]:
        messages = await self._ticket_service.get_recent_ticket_messages(
            session, ticket_id=ticket_id, limit=limit
        )
        return messages

    def _content_type(self, message: Any) -> TicketMessageContentType:
        if getattr(message, "text", None):
            return TicketMessageContentType.TEXT
        for attr, content_type in (
            ("photo", TicketMessageContentType.PHOTO),
            ("video", TicketMessageContentType.VIDEO),
            ("document", TicketMessageContentType.DOCUMENT),
            ("animation", TicketMessageContentType.ANIMATION),
            ("audio", TicketMessageContentType.AUDIO),
            ("voice", TicketMessageContentType.VOICE),
            ("video_note", TicketMessageContentType.VIDEO_NOTE),
        ):
            if getattr(message, attr, None):
                return content_type
        raise UnsupportedRelayContentError(
            "Этот тип сообщения пока нельзя безопасно передать менеджеру."
        )

    def _preview(self, message: Any, content_type: TicketMessageContentType) -> str:
        text = getattr(message, "text", None) or getattr(message, "caption", None)
        if text:
            return text
        return self._content_type_label(content_type)

    def _content_type_label(self, content_type: TicketMessageContentType) -> str:
        labels = {
            TicketMessageContentType.PHOTO: "Фото",
            TicketMessageContentType.VIDEO: "Видео",
            TicketMessageContentType.DOCUMENT: "Документ",
            TicketMessageContentType.ANIMATION: "GIF",
            TicketMessageContentType.AUDIO: "Аудио",
            TicketMessageContentType.VOICE: "Голосовое сообщение",
            TicketMessageContentType.VIDEO_NOTE: "Видео-сообщение",
            TicketMessageContentType.TEXT: "Текст",
        }
        return labels[content_type]

    def _sender_label(self, sender_type: str) -> str:
        return {
            TicketMessageSenderType.CUSTOMER.value: "Клиент",
            TicketMessageSenderType.MANAGER.value: "Менеджер",
            TicketMessageSenderType.OWNER.value: "Супервизор",
            TicketMessageSenderType.SYSTEM.value: "Система",
        }.get(sender_type, sender_type)

    @staticmethod
    def customer_display_name(customer: User) -> str:
        parts = [part for part in [customer.first_name, customer.last_name] if part]
        if parts:
            return " ".join(parts)
        if customer.username:
            return customer.username
        return str(customer.telegram_user_id)


RelayService = MessageRelayService
