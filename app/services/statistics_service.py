from __future__ import annotations

from datetime import UTC, datetime, time

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AIMessage, Ticket, User
from app.utils.enums import TicketStatus


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

    async def _ticket_status_counts(self, session: AsyncSession) -> dict[str, int]:
        rows = await session.execute(
            select(Ticket.status, func.count(Ticket.id)).group_by(Ticket.status)
        )
        return {status: count for status, count in rows}
