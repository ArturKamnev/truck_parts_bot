from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import (
    AuditEvent,
    ManagerPreference,
    OperatorSession,
    Ticket,
    TicketMessage,
    User,
)
from app.services.authorization_service import AuthorizationService
from app.utils.enums import (
    CustomerMode,
    TicketMessageContentType,
    TicketMessageDeliveryStatus,
    TicketMessageSenderType,
    TicketStatus,
)
from app.utils.exceptions import AuthorizationError, DuplicateActiveTicketError, TicketStateError

ACTIVE_TICKET_STATUSES = (TicketStatus.OPEN.value, TicketStatus.CLAIMED.value)


class TicketService:
    def __init__(self, authorization: AuthorizationService) -> None:
        self._authorization = authorization

    async def upsert_customer_from_telegram(
        self,
        session: AsyncSession,
        *,
        telegram_user_id: int,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
        language_code: str | None = None,
    ) -> User:
        return await self.upsert_user_from_telegram(
            session,
            telegram_user_id=telegram_user_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            language_code=language_code,
        )

    async def upsert_user_from_telegram(
        self,
        session: AsyncSession,
        *,
        telegram_user_id: int,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
        language_code: str | None = None,
    ) -> User:
        stmt = select(User).where(User.telegram_user_id == telegram_user_id)
        user = await session.scalar(stmt)
        now = datetime.now(UTC)
        
        from app.i18n.translator import detect_language_code
        detected_lang = detect_language_code(language_code) if language_code else None

        if user is None:
            user = User(
                telegram_user_id=telegram_user_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                mode=CustomerMode.AI_CHAT.value,
                last_seen_at=now,
                preferred_language=detected_lang,
            )
            session.add(user)
        else:
            user.username = username
            user.first_name = first_name
            user.last_name = last_name
            user.last_seen_at = now
            if detected_lang and (not user.preferred_language or not user.preferred_language.strip()):
                user.preferred_language = detected_lang
        await session.flush()
        return user

    async def get_active_ticket(self, session: AsyncSession, *, customer_id: int) -> Ticket | None:
        stmt = (
            select(Ticket)
            .options(selectinload(Ticket.customer))
            .where(Ticket.customer_id == customer_id, Ticket.status.in_(ACTIVE_TICKET_STATUSES))
            .order_by(Ticket.id.desc())
            .limit(1)
        )
        return await session.scalar(stmt)

    async def get_ticket(self, session: AsyncSession, *, ticket_id: int) -> Ticket:
        ticket = await session.get(Ticket, ticket_id, options=[selectinload(Ticket.customer)])
        if ticket is None:
            raise TicketStateError("Ticket not found")
        return ticket

    async def list_open_tickets(self, session: AsyncSession, *, limit: int = 20) -> list[Ticket]:
        stmt = (
            select(Ticket)
            .options(selectinload(Ticket.customer))
            .where(Ticket.status == TicketStatus.OPEN.value)
            .order_by(Ticket.created_at.asc(), Ticket.id.asc())
            .limit(limit)
        )
        return list(await session.scalars(stmt))

    async def list_manager_active_tickets(
        self, session: AsyncSession, *, manager_telegram_id: int, limit: int = 20
    ) -> list[Ticket]:
        stmt = (
            select(Ticket)
            .options(selectinload(Ticket.customer))
            .where(
                Ticket.status == TicketStatus.CLAIMED.value,
                Ticket.assigned_manager_telegram_id == manager_telegram_id,
            )
            .order_by(Ticket.claimed_at.desc(), Ticket.id.desc())
            .limit(limit)
        )
        return list(await session.scalars(stmt))

    async def list_active_tickets(self, session: AsyncSession, *, limit: int = 20) -> list[Ticket]:
        stmt = (
            select(Ticket)
            .options(selectinload(Ticket.customer))
            .where(Ticket.status.in_(ACTIVE_TICKET_STATUSES))
            .order_by(Ticket.created_at.desc(), Ticket.id.desc())
            .limit(limit)
        )
        return list(await session.scalars(stmt))

    async def begin_manager_request(self, session: AsyncSession, *, customer: User) -> None:
        active_ticket = await self.get_active_ticket(session, customer_id=customer.id)
        if active_ticket is not None:
            raise DuplicateActiveTicketError("Customer already has an active ticket")
        customer.mode = CustomerMode.REQUESTING_MANAGER.value
        await session.flush()

    async def get_recent_ticket_messages(
        self, session: AsyncSession, *, ticket_id: int, limit: int = 8
    ) -> list[TicketMessage]:
        stmt = (
            select(TicketMessage)
            .where(TicketMessage.ticket_id == ticket_id)
            .order_by(TicketMessage.created_at.desc(), TicketMessage.id.desc())
            .limit(limit)
        )
        rows = list(await session.scalars(stmt))
        rows.reverse()
        return rows

    async def create_ticket(
        self,
        session: AsyncSession,
        *,
        customer: User,
        original_request: str,
        content_type: TicketMessageContentType | str = TicketMessageContentType.TEXT,
        source_chat_id: int | None = None,
        source_message_id: int | None = None,
        media_group_id: str | None = None,
        delivery_status: TicketMessageDeliveryStatus | str = TicketMessageDeliveryStatus.STORED,
    ) -> Ticket:
        active_ticket = await self.get_active_ticket(session, customer_id=customer.id)
        if active_ticket is not None:
            raise DuplicateActiveTicketError("Customer already has an active ticket")

        customer.mode = CustomerMode.WAITING_MANAGER.value
        ticket = Ticket(customer_id=customer.id, status=TicketStatus.OPEN.value)
        session.add(ticket)
        await session.flush()
        self.add_ticket_message(
            session,
            ticket=ticket,
            sender_type=TicketMessageSenderType.CUSTOMER,
            sender_telegram_id=customer.telegram_user_id,
            content=original_request,
            content_type=content_type,
            source_chat_id=source_chat_id,
            source_message_id=source_message_id,
            text_preview=original_request,
            media_group_id=media_group_id,
            delivery_status=delivery_status,
        )
        self._audit(
            session,
            event_type="ticket_created",
            actor_telegram_id=customer.telegram_user_id,
            customer_id=customer.id,
            ticket_id=ticket.id,
        )
        await session.flush()
        return ticket

    async def claim_ticket(
        self, session: AsyncSession, *, ticket_id: int, manager_telegram_id: int
    ) -> Ticket:
        if not self._authorization.can_use_support_tools(manager_telegram_id):
            raise AuthorizationError("Not allowed to claim tickets")

        now = datetime.now(UTC)
        result = await session.execute(
            update(Ticket)
            .where(Ticket.id == ticket_id, Ticket.status == TicketStatus.OPEN.value)
            .values(
                status=TicketStatus.CLAIMED.value,
                assigned_manager_telegram_id=manager_telegram_id,
                claimed_at=now,
            )
        )
        if result.rowcount != 1:
            ticket = await self.get_ticket(session, ticket_id=ticket_id)
            await session.refresh(ticket)
            if ticket.status == TicketStatus.CLAIMED.value:
                if ticket.assigned_manager_telegram_id == manager_telegram_id:
                    await self.select_ticket(
                        session, operator_telegram_id=manager_telegram_id, ticket=ticket
                    )
                    return ticket
                raise TicketStateError("Это обращение уже взял другой менеджер.")
            raise TicketStateError("Only open tickets can be claimed")

        ticket = await self.get_ticket(session, ticket_id=ticket_id)
        await session.refresh(ticket)
        ticket.customer.mode = CustomerMode.MANAGER_CHAT.value
        await self.select_ticket(session, operator_telegram_id=manager_telegram_id, ticket=ticket)
        self.add_ticket_message(
            session,
            ticket=ticket,
            sender_type=TicketMessageSenderType.SYSTEM,
            sender_telegram_id=manager_telegram_id,
            content="Ticket claimed",
        )
        self._audit(
            session,
            event_type="ticket_claimed",
            actor_telegram_id=manager_telegram_id,
            customer_id=ticket.customer_id,
            ticket_id=ticket.id,
        )
        await session.flush()
        return ticket

    async def select_ticket(
        self, session: AsyncSession, *, operator_telegram_id: int, ticket: Ticket
    ) -> OperatorSession:
        if not self.can_send_manager_reply(ticket, operator_telegram_id):
            raise AuthorizationError("Not allowed to select this ticket")
        operator_session = await session.get(OperatorSession, operator_telegram_id)
        if operator_session is None:
            operator_session = OperatorSession(operator_telegram_id=operator_telegram_id)
            session.add(operator_session)
        operator_session.selected_ticket_id = ticket.id
        operator_session.updated_at = datetime.now(UTC)
        if (
            self._authorization.is_owner(operator_telegram_id)
            and ticket.status == TicketStatus.OPEN.value
        ):
            ticket.customer.mode = CustomerMode.MANAGER_CHAT.value
        await session.flush()
        return operator_session

    async def get_selected_ticket(
        self, session: AsyncSession, *, operator_telegram_id: int
    ) -> Ticket | None:
        operator_session = await session.get(OperatorSession, operator_telegram_id)
        if operator_session is None or operator_session.selected_ticket_id is None:
            return None
        ticket = await self.get_ticket(session, ticket_id=operator_session.selected_ticket_id)
        if not self.can_send_manager_reply(ticket, operator_telegram_id):
            operator_session.selected_ticket_id = None
            await session.flush()
            return None
        return ticket

    async def clear_selected_ticket(
        self,
        session: AsyncSession,
        *,
        operator_telegram_id: int | None = None,
        ticket_id: int | None = None,
    ) -> None:
        if operator_telegram_id is None and ticket_id is None:
            return
        previously_selected_ticket_id = ticket_id
        if operator_telegram_id is not None and previously_selected_ticket_id is None:
            operator_session = await session.get(OperatorSession, operator_telegram_id)
            if operator_session is not None:
                previously_selected_ticket_id = operator_session.selected_ticket_id
        stmt = update(OperatorSession).values(selected_ticket_id=None, updated_at=datetime.now(UTC))
        if operator_telegram_id is not None:
            stmt = stmt.where(OperatorSession.operator_telegram_id == operator_telegram_id)
        if ticket_id is not None:
            stmt = stmt.where(OperatorSession.selected_ticket_id == ticket_id)
        await session.execute(stmt)
        await session.flush()
        if previously_selected_ticket_id is not None:
            await self.restore_waiting_mode_if_unassigned(
                session, ticket_id=previously_selected_ticket_id
            )

    async def close_ticket(
        self, session: AsyncSession, *, ticket_id: int, actor_telegram_id: int
    ) -> Ticket:
        ticket = await self.get_ticket(session, ticket_id=ticket_id)
        can_owner_close = (
            self._authorization.is_owner(actor_telegram_id)
            and ticket.status in ACTIVE_TICKET_STATUSES
        )
        if not can_owner_close and not self.can_send_manager_reply(ticket, actor_telegram_id):
            raise AuthorizationError("Not allowed to close this ticket")
        if ticket.status not in ACTIVE_TICKET_STATUSES:
            return ticket

        ticket.status = TicketStatus.CLOSED.value
        ticket.closed_at = datetime.now(UTC)
        ticket.closed_by_telegram_id = actor_telegram_id
        ticket.customer.mode = CustomerMode.AI_CHAT.value
        await self.clear_selected_ticket(session, ticket_id=ticket.id)
        self.add_ticket_message(
            session,
            ticket=ticket,
            sender_type=TicketMessageSenderType.SYSTEM,
            sender_telegram_id=actor_telegram_id,
            content="Ticket closed",
        )
        self._audit(
            session,
            event_type="ticket_closed",
            actor_telegram_id=actor_telegram_id,
            customer_id=ticket.customer_id,
            ticket_id=ticket.id,
        )
        await session.flush()
        return ticket

    async def restore_waiting_mode_if_unassigned(
        self, session: AsyncSession, *, ticket_id: int
    ) -> None:
        ticket = await self.get_ticket(session, ticket_id=ticket_id)
        if (
            ticket.status == TicketStatus.OPEN.value
            and ticket.assigned_manager_telegram_id is None
            and ticket.customer.mode == CustomerMode.MANAGER_CHAT.value
        ):
            ticket.customer.mode = CustomerMode.WAITING_MANAGER.value
            await session.flush()

    async def cancel_by_customer(
        self, session: AsyncSession, *, customer: User, actor_telegram_id: int
    ) -> Ticket | None:
        ticket = await self.get_active_ticket(session, customer_id=customer.id)
        customer.mode = CustomerMode.AI_CHAT.value
        if ticket is None:
            await session.flush()
            return None

        ticket.status = TicketStatus.CANCELLED_BY_CUSTOMER.value
        ticket.closed_at = datetime.now(UTC)
        ticket.closed_by_telegram_id = actor_telegram_id
        await self.clear_selected_ticket(session, ticket_id=ticket.id)
        self.add_ticket_message(
            session,
            ticket=ticket,
            sender_type=TicketMessageSenderType.SYSTEM,
            sender_telegram_id=actor_telegram_id,
            content="Customer left manager chat",
        )
        self._audit(
            session,
            event_type="ticket_cancelled_by_customer",
            actor_telegram_id=actor_telegram_id,
            customer_id=customer.id,
            ticket_id=ticket.id,
        )
        await session.flush()
        return ticket

    def can_send_manager_reply(self, ticket: Ticket, actor_telegram_id: int) -> bool:
        if self._authorization.is_owner(actor_telegram_id):
            return ticket.status in ACTIVE_TICKET_STATUSES
        if not self._authorization.is_manager(actor_telegram_id):
            return False
        return (
            ticket.status == TicketStatus.CLAIMED.value
            and ticket.assigned_manager_telegram_id == actor_telegram_id
        )

    def can_view_manager_ticket(self, ticket: Ticket, actor_telegram_id: int) -> bool:
        if self._authorization.is_owner(actor_telegram_id):
            return ticket.status in ACTIVE_TICKET_STATUSES
        if self._authorization.is_manager(actor_telegram_id):
            return ticket.status == TicketStatus.OPEN.value or (
                ticket.status == TicketStatus.CLAIMED.value
                and ticket.assigned_manager_telegram_id == actor_telegram_id
            )
        return False

    def add_ticket_message(
        self,
        session: AsyncSession,
        *,
        ticket: Ticket,
        sender_type: TicketMessageSenderType,
        sender_telegram_id: int | None,
        content: str,
        content_type: TicketMessageContentType | str = TicketMessageContentType.TEXT,
        source_chat_id: int | None = None,
        source_message_id: int | None = None,
        text_preview: str | None = None,
        media_group_id: str | None = None,
        delivery_status: TicketMessageDeliveryStatus | str = TicketMessageDeliveryStatus.STORED,
    ) -> TicketMessage:
        if isinstance(content_type, TicketMessageContentType):
            content_type_value = content_type.value
        else:
            content_type_value = content_type
        delivery_status_value = (
            delivery_status.value
            if isinstance(delivery_status, TicketMessageDeliveryStatus)
            else delivery_status
        )
        message = TicketMessage(
            ticket_id=ticket.id,
            sender_type=sender_type.value,
            sender_telegram_id=sender_telegram_id,
            content_type=content_type_value,
            source_chat_id=source_chat_id,
            source_message_id=source_message_id,
            text_preview=text_preview or content,
            media_group_id=media_group_id,
            delivery_status=delivery_status_value,
            content=content,
        )
        session.add(message)
        return message

    async def set_ticket_message_delivery_status(
        self,
        session: AsyncSession,
        *,
        ticket_message_id: int,
        delivery_status: TicketMessageDeliveryStatus,
    ) -> None:
        await session.execute(
            update(TicketMessage)
            .where(TicketMessage.id == ticket_message_id)
            .values(delivery_status=delivery_status.value)
        )

    async def selected_owner_ids_for_ticket(
        self, session: AsyncSession, *, ticket_id: int
    ) -> list[int]:
        rows = await session.scalars(
            select(OperatorSession.operator_telegram_id).where(
                OperatorSession.selected_ticket_id == ticket_id
            )
        )
        return [operator_id for operator_id in rows if self._authorization.is_owner(operator_id)]

    async def get_manager_notifications_enabled(
        self, session: AsyncSession, *, manager_telegram_id: int
    ) -> bool:
        preference = await session.get(ManagerPreference, manager_telegram_id)
        if preference is None:
            preference = ManagerPreference(manager_telegram_id=manager_telegram_id)
            session.add(preference)
            await session.flush()
            return True
        return preference.new_ticket_notifications_enabled

    async def set_manager_notifications_enabled(
        self,
        session: AsyncSession,
        *,
        manager_telegram_id: int,
        enabled: bool,
    ) -> ManagerPreference:
        preference = await session.get(ManagerPreference, manager_telegram_id)
        if preference is None:
            preference = ManagerPreference(manager_telegram_id=manager_telegram_id)
            session.add(preference)
        preference.new_ticket_notifications_enabled = enabled
        preference.updated_at = datetime.now(UTC)
        await session.flush()
        return preference

    def _audit(
        self,
        session: AsyncSession,
        *,
        event_type: str,
        actor_telegram_id: int | None,
        customer_id: int | None = None,
        ticket_id: int | None = None,
        metadata_json: dict | None = None,
    ) -> None:
        session.add(
            AuditEvent(
                event_type=event_type,
                actor_telegram_id=actor_telegram_id,
                customer_id=customer_id,
                ticket_id=ticket_id,
                metadata_json=metadata_json or {},
            )
        )
