from __future__ import annotations

from datetime import UTC, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import AIMessage, Broadcast, StaffMember, Ticket, TicketMessage, User
from app.utils.enums import AIMessageRole, StaffStatus, TicketMessageSenderType, TicketStatus


class StatisticsService:
    async def owner_stats(self, session: AsyncSession) -> dict:
        today_start = datetime.combine(datetime.now(UTC).date(), time.min, tzinfo=UTC)

        total_customers = await session.scalar(select(func.count()).select_from(User))
        new_customers_today = await session.scalar(
            select(func.count()).select_from(User).where(User.created_at >= today_start)
        )
        total_ai_messages = await session.scalar(select(func.count()).select_from(AIMessage))
        total_tickets = await session.scalar(select(func.count()).select_from(Ticket))

        status_counts = await self._ticket_status_counts(session)
        per_manager_rows = await session.execute(
            select(Ticket.assigned_manager_telegram_id, func.count(Ticket.id))
            .where(Ticket.assigned_manager_telegram_id.is_not(None))
            .group_by(Ticket.assigned_manager_telegram_id)
        )
        per_manager = {int(manager_id): count for manager_id, count in per_manager_rows}

        claimed = list(
            await session.scalars(select(Ticket).where(Ticket.claimed_at.is_not(None)).limit(500))
        )
        claim_seconds = [
            (ticket.claimed_at - ticket.created_at).total_seconds()
            for ticket in claimed
            if ticket.claimed_at and ticket.created_at
        ]
        avg_first_claim_seconds = (
            round(sum(claim_seconds) / len(claim_seconds), 2) if claim_seconds else None
        )

        return {
            "total_customers": total_customers or 0,
            "new_customers_today": new_customers_today or 0,
            "total_ai_messages": total_ai_messages or 0,
            "total_tickets": total_tickets or 0,
            "open_tickets": status_counts.get(TicketStatus.OPEN.value, 0),
            "claimed_tickets": status_counts.get(TicketStatus.CLAIMED.value, 0),
            "closed_tickets": status_counts.get(TicketStatus.CLOSED.value, 0),
            "tickets_per_manager": per_manager,
            "avg_first_claim_seconds": avg_first_claim_seconds,
        }

    async def manager_stats(self, session: AsyncSession, *, manager_telegram_id: int) -> dict:
        claimed = await session.scalar(
            select(func.count())
            .select_from(Ticket)
            .where(Ticket.assigned_manager_telegram_id == manager_telegram_id)
        )
        closed = await session.scalar(
            select(func.count())
            .select_from(Ticket)
            .where(
                Ticket.assigned_manager_telegram_id == manager_telegram_id,
                Ticket.status == TicketStatus.CLOSED.value,
            )
        )
        active = await session.scalar(
            select(func.count())
            .select_from(Ticket)
            .where(
                Ticket.assigned_manager_telegram_id == manager_telegram_id,
                Ticket.status == TicketStatus.CLAIMED.value,
            )
        )
        return {
            "claimed_tickets": claimed or 0,
            "closed_tickets": closed or 0,
            "active_tickets": active or 0,
        }

    async def owner_overview(
        self, session: AsyncSession, *, active_model: str | None = None
    ) -> dict:
        now = datetime.now(UTC)
        active_since = now - timedelta(days=7)
        status_counts = await self._ticket_status_counts(session)

        total_users = await session.scalar(select(func.count()).select_from(User)) or 0
        active_users = await session.scalar(
            select(func.count()).select_from(User).where(User.last_seen_at >= active_since)
        ) or 0
        total_tickets = await session.scalar(select(func.count()).select_from(Ticket)) or 0
        ai_requests_count = await session.scalar(
            select(func.count())
            .select_from(AIMessage)
            .where(AIMessage.role == AIMessageRole.USER.value)
        ) or 0

        avg_first_claim_seconds = await self._avg_first_claim_seconds(session)
        manager_performance = await self._manager_performance(session)
        broadcast_summary = await self._broadcast_summary(session)
        language_distribution = await self._language_distribution(session)
        ticket_trend = await self._ticket_trend(session)

        return {
            "total_users": total_users,
            "active_users": active_users,
            "total_tickets": total_tickets,
            "open_tickets": status_counts.get(TicketStatus.OPEN.value, 0),
            "active_chats": status_counts.get(TicketStatus.CLAIMED.value, 0),
            "closed_tickets": status_counts.get(TicketStatus.CLOSED.value, 0),
            "cancelled_tickets": status_counts.get(
                TicketStatus.CANCELLED_BY_CUSTOMER.value, 0
            ),
            "pending_chats": status_counts.get(TicketStatus.OPEN.value, 0),
            "avg_first_claim_seconds": avg_first_claim_seconds,
            "active_model": active_model,
            "ai_requests_count": ai_requests_count,
            "tickets_by_status": [
                {"label": status, "value": count}
                for status, count in sorted(status_counts.items())
            ],
            "ticket_trend": ticket_trend,
            "manager_performance": manager_performance,
            "broadcast_summary": broadcast_summary,
            "language_distribution": language_distribution,
        }

    async def manager_overview(
        self, session: AsyncSession, *, manager_telegram_id: int
    ) -> dict:
        closed_statuses = (
            TicketStatus.CLOSED.value,
            TicketStatus.CANCELLED_BY_CUSTOMER.value,
        )
        my_active_chats = await session.scalar(
            select(func.count()).select_from(Ticket).where(
                Ticket.assigned_manager_telegram_id == manager_telegram_id,
                Ticket.status == TicketStatus.CLAIMED.value,
            )
        ) or 0
        my_closed_chats = await session.scalar(
            select(func.count()).select_from(Ticket).where(
                Ticket.assigned_manager_telegram_id == manager_telegram_id,
                Ticket.status.in_(closed_statuses),
            )
        ) or 0
        my_claimed_chats = await session.scalar(
            select(func.count()).select_from(Ticket).where(
                Ticket.assigned_manager_telegram_id == manager_telegram_id
            )
        ) or 0
        available_queue = await session.scalar(
            select(func.count()).select_from(Ticket).where(
                Ticket.status == TicketStatus.OPEN.value
            )
        ) or 0
        pending_replies = await self._pending_manager_replies(
            session, manager_telegram_id=manager_telegram_id
        )
        avg_close_seconds = await self._avg_close_seconds(
            session, manager_telegram_id=manager_telegram_id
        )
        status_counts = await self._ticket_status_counts(
            session, manager_telegram_id=manager_telegram_id
        )

        return {
            "my_active_chats": my_active_chats,
            "my_closed_chats": my_closed_chats,
            "my_claimed_chats": my_claimed_chats,
            "pending_replies": pending_replies,
            "available_queue": available_queue,
            "avg_close_seconds": avg_close_seconds,
            "tickets_by_status": [
                {"label": status, "value": count}
                for status, count in sorted(status_counts.items())
            ],
            "ticket_trend": await self._ticket_trend(
                session, manager_telegram_id=manager_telegram_id
            ),
        }

    async def customer_overview(self, session: AsyncSession, *, customer: User) -> dict:
        tickets = list(
            await session.scalars(
                select(Ticket)
                .options(selectinload(Ticket.customer))
                .where(Ticket.customer_id == customer.id)
                .order_by(Ticket.created_at.desc(), Ticket.id.desc())
            )
        )
        active_statuses = {TicketStatus.OPEN.value, TicketStatus.CLAIMED.value}
        closed_statuses = {
            TicketStatus.CLOSED.value,
            TicketStatus.CANCELLED_BY_CUSTOMER.value,
        }
        active_ticket = next((ticket for ticket in tickets if ticket.status in active_statuses), None)
        status_counts: dict[str, int] = {}
        for ticket in tickets:
            status_counts[ticket.status] = status_counts.get(ticket.status, 0) + 1

        return {
            "active_ticket": active_ticket,
            "active_chats": sum(1 for ticket in tickets if ticket.status in active_statuses),
            "saved_chats": len(tickets),
            "closed_chats": sum(1 for ticket in tickets if ticket.status in closed_statuses),
            "broadcasts_enabled": customer.broadcasts_enabled,
            "total_tickets": len(tickets),
            "tickets_by_status": [
                {"label": status, "value": count}
                for status, count in sorted(status_counts.items())
            ],
        }

    async def _ticket_status_counts(
        self, session: AsyncSession, *, manager_telegram_id: int | None = None
    ) -> dict[str, int]:
        stmt = select(Ticket.status, func.count(Ticket.id)).group_by(Ticket.status)
        if manager_telegram_id is not None:
            stmt = stmt.where(Ticket.assigned_manager_telegram_id == manager_telegram_id)
        rows = await session.execute(stmt)
        return {status: count for status, count in rows}

    async def _avg_first_claim_seconds(self, session: AsyncSession) -> float | None:
        claimed = list(
            await session.scalars(select(Ticket).where(Ticket.claimed_at.is_not(None)).limit(500))
        )
        claim_seconds = [
            (ticket.claimed_at - ticket.created_at).total_seconds()
            for ticket in claimed
            if ticket.claimed_at and ticket.created_at
        ]
        return round(sum(claim_seconds) / len(claim_seconds), 2) if claim_seconds else None

    async def _avg_close_seconds(
        self, session: AsyncSession, *, manager_telegram_id: int
    ) -> float | None:
        tickets = list(
            await session.scalars(
                select(Ticket)
                .where(
                    Ticket.assigned_manager_telegram_id == manager_telegram_id,
                    Ticket.closed_at.is_not(None),
                )
                .limit(500)
            )
        )
        close_seconds = [
            (ticket.closed_at - ticket.created_at).total_seconds()
            for ticket in tickets
            if ticket.closed_at and ticket.created_at
        ]
        return round(sum(close_seconds) / len(close_seconds), 2) if close_seconds else None

    async def _manager_performance(self, session: AsyncSession) -> list[dict]:
        rows = await session.execute(
            select(StaffMember, User)
            .outerjoin(User, User.telegram_user_id == StaffMember.telegram_user_id)
            .where(StaffMember.status == StaffStatus.ACTIVE.value)
            .order_by(StaffMember.added_at.desc())
        )
        staff_rows = rows.all()
        performance = []
        for staff, user in staff_rows:
            claimed = await session.scalar(
                select(func.count()).select_from(Ticket).where(
                    Ticket.assigned_manager_telegram_id == staff.telegram_user_id
                )
            ) or 0
            active = await session.scalar(
                select(func.count()).select_from(Ticket).where(
                    Ticket.assigned_manager_telegram_id == staff.telegram_user_id,
                    Ticket.status == TicketStatus.CLAIMED.value,
                )
            ) or 0
            closed = await session.scalar(
                select(func.count()).select_from(Ticket).where(
                    Ticket.closed_by_telegram_id == staff.telegram_user_id
                )
            ) or 0
            if user:
                parts = [p for p in (user.first_name, user.last_name) if p]
                display_name = " ".join(parts) if parts else (user.username or f"User {user.telegram_user_id}")
            else:
                display_name = f"Telegram ID {staff.telegram_user_id}"
            performance.append(
                {
                    "telegram_user_id": staff.telegram_user_id,
                    "display_name": display_name,
                    "role": staff.role,
                    "status": staff.status,
                    "active_tickets": active,
                    "claimed_tickets": claimed,
                    "closed_tickets": closed,
                }
            )
        return performance

    async def _broadcast_summary(self, session: AsyncSession) -> dict:
        row = await session.execute(
            select(
                func.count(Broadcast.id),
                func.coalesce(func.sum(Broadcast.delivered_count), 0),
                func.coalesce(func.sum(Broadcast.failed_count), 0),
                func.coalesce(func.sum(Broadcast.blocked_count), 0),
                func.coalesce(func.sum(Broadcast.recipient_count), 0),
            )
        )
        total, delivered, failed, blocked, recipients = row.one()
        return {
            "total": total or 0,
            "delivered": delivered or 0,
            "failed": failed or 0,
            "blocked": blocked or 0,
            "recipients": recipients or 0,
        }

    async def _language_distribution(self, session: AsyncSession) -> list[dict]:
        rows = await session.execute(
            select(User.preferred_language, func.count(User.id)).group_by(User.preferred_language)
        )
        return [
            {"label": language or "unknown", "value": count}
            for language, count in rows
        ]

    async def _ticket_trend(
        self, session: AsyncSession, *, manager_telegram_id: int | None = None, days: int = 7
    ) -> list[dict]:
        now = datetime.now(UTC)
        start = now - timedelta(days=days - 1)
        stmt = select(Ticket).where(
            (Ticket.created_at >= datetime.combine(start.date(), time.min, tzinfo=UTC))
            | (
                Ticket.closed_at.is_not(None)
                & (Ticket.closed_at >= datetime.combine(start.date(), time.min, tzinfo=UTC))
            )
        )
        if manager_telegram_id is not None:
            stmt = stmt.where(Ticket.assigned_manager_telegram_id == manager_telegram_id)
        tickets = list(await session.scalars(stmt))
        buckets = {
            (now.date() - timedelta(days=offset)).isoformat(): {"created": 0, "closed": 0}
            for offset in range(days - 1, -1, -1)
        }
        for ticket in tickets:
            created_key = ticket.created_at.date().isoformat() if ticket.created_at else None
            if created_key in buckets:
                buckets[created_key]["created"] += 1
            closed_key = ticket.closed_at.date().isoformat() if ticket.closed_at else None
            if closed_key in buckets:
                buckets[closed_key]["closed"] += 1
        return [
            {"date": day, "created": values["created"], "closed": values["closed"]}
            for day, values in buckets.items()
        ]

    async def _pending_manager_replies(
        self, session: AsyncSession, *, manager_telegram_id: int
    ) -> int:
        active_tickets = list(
            await session.scalars(
                select(Ticket).where(
                    Ticket.assigned_manager_telegram_id == manager_telegram_id,
                    Ticket.status == TicketStatus.CLAIMED.value,
                )
            )
        )
        pending = 0
        for ticket in active_tickets:
            last_message = await session.scalar(
                select(TicketMessage)
                .where(TicketMessage.ticket_id == ticket.id)
                .order_by(TicketMessage.id.desc())
                .limit(1)
            )
            if last_message and last_message.sender_type == TicketMessageSenderType.CUSTOMER.value:
                pending += 1
        return pending
