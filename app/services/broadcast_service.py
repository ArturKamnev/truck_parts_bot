from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import Settings
from app.db.models import Broadcast, BroadcastDelivery, OperatorSession, User
from app.db.session import SessionLocal
from app.services.authorization_service import AuthorizationService
from app.services.relay_service import MessageRelayService
from app.utils.enums import (
    BroadcastButtonSelection,
    BroadcastDeliveryStatus,
    BroadcastStatus,
    OwnerWorkflowState,
    TicketMessageContentType,
)
from app.utils.exceptions import AuthorizationError, TicketStateError, UnsupportedRelayContentError

logger = logging.getLogger(__name__)


class BroadcastService:
    def __init__(
        self,
        settings: Settings,
        authorization: AuthorizationService,
        relay_service: MessageRelayService,
    ) -> None:
        self._settings = settings
        self._authorization = authorization
        self._relay_service = relay_service
        self._send_task: asyncio.Task | None = None

    async def start_draft(self, session: AsyncSession, *, owner_telegram_id: int) -> Broadcast:
        self._ensure_owner(owner_telegram_id)
        await self.cancel_active_draft(session, owner_telegram_id=owner_telegram_id)
        broadcast = Broadcast(created_by_telegram_id=owner_telegram_id)
        session.add(broadcast)
        await session.flush()
        owner_session = await self._operator_session(session, owner_telegram_id)
        owner_session.selected_ticket_id = None
        owner_session.active_broadcast_id = broadcast.id
        owner_session.workflow_state = OwnerWorkflowState.CREATING_BROADCAST_CONTENT.value
        owner_session.updated_at = datetime.now(UTC)
        return broadcast

    async def cancel_active_draft(
        self, session: AsyncSession, *, owner_telegram_id: int
    ) -> Broadcast | None:
        self._ensure_owner(owner_telegram_id)
        owner_session = await self._operator_session(session, owner_telegram_id)
        broadcast = None
        if owner_session.active_broadcast_id is not None:
            broadcast = await session.get(Broadcast, owner_session.active_broadcast_id)
            if broadcast and broadcast.status in {
                BroadcastStatus.DRAFT.value,
                BroadcastStatus.READY.value,
            }:
                broadcast.status = BroadcastStatus.CANCELLED.value
                broadcast.completed_at = datetime.now(UTC)
        owner_session.workflow_state = None
        owner_session.active_broadcast_id = None
        owner_session.updated_at = datetime.now(UTC)
        return broadcast

    async def active_owner_state(
        self, session: AsyncSession, *, owner_telegram_id: int
    ) -> str | None:
        if not self._authorization.is_owner(owner_telegram_id):
            return None
        owner_session = await session.get(OperatorSession, owner_telegram_id)
        return owner_session.workflow_state if owner_session else None

    async def get_active_draft(
        self, session: AsyncSession, *, owner_telegram_id: int
    ) -> Broadcast | None:
        if not self._authorization.is_owner(owner_telegram_id):
            return None
        owner_session = await session.get(OperatorSession, owner_telegram_id)
        if owner_session is None or owner_session.active_broadcast_id is None:
            return None
        return await session.get(Broadcast, owner_session.active_broadcast_id)

    async def capture_content(
        self,
        session: AsyncSession,
        *,
        owner_telegram_id: int,
        message: Any,
    ) -> Broadcast:
        self._ensure_owner(owner_telegram_id)
        broadcast = await self.get_active_draft(session, owner_telegram_id=owner_telegram_id)
        if broadcast is None:
            raise TicketStateError("Нет активного черновика рассылки.")
        metadata = self._relay_service.metadata_from_message(message)
        if metadata.media_group_id and metadata.content_type not in {
            TicketMessageContentType.PHOTO,
            TicketMessageContentType.VIDEO,
        }:
            raise UnsupportedRelayContentError("В альбоме поддерживаются только фото и видео.")
        broadcast.source_chat_id = metadata.source_chat_id
        broadcast.source_message_id = metadata.source_message_id
        broadcast.media_group_id = metadata.media_group_id
        if metadata.media_group_id and metadata.source_message_id:
            broadcast.media_group_message_ids = [metadata.source_message_id]
        else:
            broadcast.media_group_message_ids = None
        broadcast.content_type = metadata.content_type.value
        broadcast.content_preview = metadata.text_preview
        broadcast.status = BroadcastStatus.DRAFT.value
        owner_session = await self._operator_session(session, owner_telegram_id)
        owner_session.workflow_state = OwnerWorkflowState.CHOOSING_BROADCAST_BUTTONS.value
        owner_session.updated_at = datetime.now(UTC)
        await session.flush()
        return broadcast

    async def append_album_message(
        self, session: AsyncSession, *, owner_telegram_id: int, message: Any
    ) -> bool:
        broadcast = await self.get_active_draft(session, owner_telegram_id=owner_telegram_id)
        if broadcast is None or not broadcast.media_group_id:
            return False
        if getattr(message, "media_group_id", None) != broadcast.media_group_id:
            return False
        metadata = self._relay_service.metadata_from_message(message)
        if metadata.content_type not in {
            TicketMessageContentType.PHOTO,
            TicketMessageContentType.VIDEO,
        }:
            return False
        ids = list(broadcast.media_group_message_ids or [])
        if metadata.source_message_id and metadata.source_message_id not in ids:
            ids.append(metadata.source_message_id)
            broadcast.media_group_message_ids = sorted(ids)
            await session.flush()
        return True

    async def set_buttons(
        self,
        session: AsyncSession,
        *,
        owner_telegram_id: int,
        broadcast_id: int,
        selection: BroadcastButtonSelection,
    ) -> Broadcast:
        self._ensure_owner(owner_telegram_id)
        if not self.is_button_selection_available(selection):
            raise AuthorizationError("Эта кнопка не настроена.")
        broadcast = await self._owned_broadcast(session, owner_telegram_id, broadcast_id)
        if broadcast.status not in {BroadcastStatus.DRAFT.value, BroadcastStatus.READY.value}:
            raise TicketStateError("Черновик уже нельзя изменить.")
        broadcast.button_selection = selection.value
        broadcast.status = BroadcastStatus.READY.value
        owner_session = await self._operator_session(session, owner_telegram_id)
        owner_session.workflow_state = OwnerWorkflowState.PREVIEWING_BROADCAST.value
        await session.flush()
        return broadcast

    async def request_final_confirmation(
        self, session: AsyncSession, *, owner_telegram_id: int, broadcast_id: int
    ) -> tuple[Broadcast, int]:
        broadcast = await self._owned_broadcast(session, owner_telegram_id, broadcast_id)
        if broadcast.status != BroadcastStatus.READY.value:
            raise TicketStateError("Сначала подготовьте рассылку.")
        recipient_count = await self.count_eligible_recipients(session)
        owner_session = await self._operator_session(session, owner_telegram_id)
        owner_session.workflow_state = OwnerWorkflowState.CONFIRMING_BROADCAST.value
        await session.flush()
        return broadcast, recipient_count

    async def start_sending(
        self, session: AsyncSession, *, owner_telegram_id: int, broadcast_id: int
    ) -> Broadcast:
        self._ensure_owner(owner_telegram_id)
        if await self.has_active_sending_job(session):
            raise TicketStateError("Уже выполняется другая рассылка.")
        broadcast = await self._owned_broadcast(session, owner_telegram_id, broadcast_id)
        if broadcast.status != BroadcastStatus.READY.value:
            raise TicketStateError("Рассылка не готова к отправке.")
        recipients = await self.eligible_recipients(session)
        broadcast.status = BroadcastStatus.SENDING.value
        broadcast.started_at = datetime.now(UTC)
        broadcast.recipient_count = len(recipients)
        broadcast.delivered_count = 0
        broadcast.failed_count = 0
        broadcast.blocked_count = 0
        for user in recipients:
            session.add(
                BroadcastDelivery(
                    broadcast_id=broadcast.id,
                    user_id=user.id,
                    status=BroadcastDeliveryStatus.PENDING.value,
                )
            )
        owner_session = await self._operator_session(session, owner_telegram_id)
        owner_session.workflow_state = None
        owner_session.active_broadcast_id = None
        await session.flush()
        return broadcast

    def launch_sending_job(self, bot: Bot, *, broadcast_id: int) -> None:
        self._send_task = asyncio.create_task(self._send_job(bot, broadcast_id))

    async def send_test(self, bot: Bot, session: AsyncSession, *, broadcast: Broadcast) -> None:
        await self.copy_broadcast_to_chat(
            bot, broadcast=broadcast, destination_chat_id=broadcast.created_by_telegram_id
        )

    async def copy_broadcast_to_chat(
        self, bot: Bot, *, broadcast: Broadcast, destination_chat_id: int
    ) -> None:
        reply_markup = self.buttons_markup(broadcast.button_selection)
        if broadcast.source_chat_id is None:
            raise TicketStateError("В черновике нет сообщения.")
        if broadcast.media_group_message_ids:
            await bot.copy_messages(
                chat_id=destination_chat_id,
                from_chat_id=broadcast.source_chat_id,
                message_ids=broadcast.media_group_message_ids,
            )
            if reply_markup:
                await bot.send_message(
                    chat_id=destination_chat_id,
                    text="Ссылки:",
                    reply_markup=reply_markup,
                )
            return
        if broadcast.source_message_id is None:
            raise TicketStateError("В черновике нет сообщения.")
        await bot.copy_message(
            chat_id=destination_chat_id,
            from_chat_id=broadcast.source_chat_id,
            message_id=broadcast.source_message_id,
            reply_markup=reply_markup,
        )

    async def count_eligible_recipients(self, session: AsyncSession) -> int:
        stmt = select(func.count()).select_from(User).where(*self._recipient_filters())
        return await session.scalar(stmt) or 0

    async def eligible_recipients(self, session: AsyncSession) -> list[User]:
        stmt = select(User).where(*self._recipient_filters()).order_by(User.id.asc())
        return list(await session.scalars(stmt))

    async def recent_broadcasts(self, session: AsyncSession, *, limit: int = 10) -> list[Broadcast]:
        stmt = (
            select(Broadcast)
            .order_by(Broadcast.created_at.desc(), Broadcast.id.desc())
            .limit(limit)
        )
        return list(await session.scalars(stmt))

    async def get_report(
        self, session: AsyncSession, *, owner_telegram_id: int, broadcast_id: int
    ) -> Broadcast:
        return await self._owned_broadcast(session, owner_telegram_id, broadcast_id)

    def is_button_selection_available(self, selection: BroadcastButtonSelection) -> bool:
        if selection == BroadcastButtonSelection.NONE:
            return True
        if selection == BroadcastButtonSelection.INSTAGRAM:
            return bool(self._settings.instagram_url)
        if selection == BroadcastButtonSelection.SITE:
            return bool(self._settings.official_site_url)
        if selection == BroadcastButtonSelection.BOTH:
            return bool(self._settings.instagram_url and self._settings.official_site_url)
        return False

    def buttons_markup(self, selection_value: str | None) -> InlineKeyboardMarkup | None:
        selection = BroadcastButtonSelection(selection_value or BroadcastButtonSelection.NONE.value)
        rows = []
        if selection in {BroadcastButtonSelection.INSTAGRAM, BroadcastButtonSelection.BOTH}:
            if self._settings.instagram_url:
                rows.append(
                    [
                        InlineKeyboardButton(
                            text="Перейти в Instagram", url=self._settings.instagram_url
                        )
                    ]
                )
        if selection in {BroadcastButtonSelection.SITE, BroadcastButtonSelection.BOTH}:
            if self._settings.official_site_url:
                rows.append(
                    [
                        InlineKeyboardButton(
                            text="Официальный сайт", url=self._settings.official_site_url
                        )
                    ]
                )
        return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None

    async def has_active_sending_job(self, session: AsyncSession) -> bool:
        if self._send_task and not self._send_task.done():
            return True
        count = await session.scalar(
            select(func.count())
            .select_from(Broadcast)
            .where(Broadcast.status == BroadcastStatus.SENDING.value)
        )
        return bool(count)

    async def _send_job(self, bot: Bot, broadcast_id: int) -> None:
        delay = 1 / max(self._settings.broadcast_rate_per_second, 1)
        async with SessionLocal() as session:
            broadcast = await session.get(Broadcast, broadcast_id)
            if broadcast is None:
                return
            deliveries = await self._pending_deliveries(session, broadcast_id=broadcast_id)
            await session.commit()

        for delivery in deliveries:
            async with SessionLocal() as session, session.begin():
                delivery = await session.get(
                    BroadcastDelivery,
                    delivery.id,
                    options=[selectinload(BroadcastDelivery.user)],
                )
                broadcast = await session.get(Broadcast, broadcast_id)
                if delivery is None or broadcast is None:
                    continue
                await self._attempt_delivery(bot, session, broadcast, delivery)
            await asyncio.sleep(delay)

        async with SessionLocal() as session, session.begin():
            await self._refresh_counts(session, broadcast_id=broadcast_id)
            broadcast = await session.get(Broadcast, broadcast_id)
            if broadcast is not None and broadcast.status == BroadcastStatus.SENDING.value:
                broadcast.status = BroadcastStatus.COMPLETED.value
                broadcast.completed_at = datetime.now(UTC)

    async def _attempt_delivery(
        self,
        bot: Bot,
        session: AsyncSession,
        broadcast: Broadcast,
        delivery: BroadcastDelivery,
    ) -> None:
        delivery.attempted_at = datetime.now(UTC)
        try:
            await self.copy_broadcast_to_chat(
                bot, broadcast=broadcast, destination_chat_id=delivery.user.telegram_user_id
            )
        except TelegramRetryAfter as exc:
            await asyncio.sleep(exc.retry_after)
            try:
                await self.copy_broadcast_to_chat(
                    bot, broadcast=broadcast, destination_chat_id=delivery.user.telegram_user_id
                )
            except TelegramRetryAfter:
                delivery.status = BroadcastDeliveryStatus.FAILED.value
                delivery.error_code = "rate_limit_retry_exhausted"
                return
        except TelegramForbiddenError:
            delivery.status = BroadcastDeliveryStatus.BLOCKED.value
            delivery.error_code = "blocked_or_unavailable"
            delivery.user.is_unavailable = True
            return
        except TelegramBadRequest:
            delivery.status = BroadcastDeliveryStatus.FAILED.value
            delivery.error_code = "telegram_bad_request"
            return
        delivery.status = BroadcastDeliveryStatus.DELIVERED.value
        delivery.delivered_at = datetime.now(UTC)

    async def _pending_deliveries(
        self, session: AsyncSession, *, broadcast_id: int
    ) -> list[BroadcastDelivery]:
        stmt = (
            select(BroadcastDelivery)
            .where(
                BroadcastDelivery.broadcast_id == broadcast_id,
                BroadcastDelivery.status == BroadcastDeliveryStatus.PENDING.value,
            )
            .order_by(BroadcastDelivery.id.asc())
        )
        return list(await session.scalars(stmt))

    async def _refresh_counts(self, session: AsyncSession, *, broadcast_id: int) -> None:
        delivered = await self._delivery_count(
            session, broadcast_id, BroadcastDeliveryStatus.DELIVERED
        )
        failed = await self._delivery_count(session, broadcast_id, BroadcastDeliveryStatus.FAILED)
        blocked = await self._delivery_count(session, broadcast_id, BroadcastDeliveryStatus.BLOCKED)
        await session.execute(
            update(Broadcast)
            .where(Broadcast.id == broadcast_id)
            .values(delivered_count=delivered, failed_count=failed, blocked_count=blocked)
        )

    async def _delivery_count(
        self, session: AsyncSession, broadcast_id: int, status: BroadcastDeliveryStatus
    ) -> int:
        return (
            await session.scalar(
                select(func.count())
                .select_from(BroadcastDelivery)
                .where(
                    BroadcastDelivery.broadcast_id == broadcast_id,
                    BroadcastDelivery.status == status.value,
                )
            )
            or 0
        )

    def _recipient_filters(self):
        blocked_ids = set(self._settings.manager_ids)
        blocked_ids.add(self._settings.owner_id)
        return (
            User.broadcasts_enabled.is_(True),
            User.is_unavailable.is_(False),
            User.telegram_user_id.not_in(blocked_ids),
        )

    async def _operator_session(
        self, session: AsyncSession, operator_telegram_id: int
    ) -> OperatorSession:
        operator_session = await session.get(OperatorSession, operator_telegram_id)
        if operator_session is None:
            operator_session = OperatorSession(operator_telegram_id=operator_telegram_id)
            session.add(operator_session)
            await session.flush()
        return operator_session

    async def _owned_broadcast(
        self, session: AsyncSession, owner_telegram_id: int, broadcast_id: int
    ) -> Broadcast:
        self._ensure_owner(owner_telegram_id)
        broadcast = await session.get(Broadcast, broadcast_id)
        if broadcast is None or broadcast.created_by_telegram_id != owner_telegram_id:
            raise AuthorizationError("Недостаточно прав")
        return broadcast

    def _ensure_owner(self, telegram_user_id: int) -> None:
        if not self._authorization.is_owner(telegram_user_id):
            raise AuthorizationError("Недостаточно прав")
