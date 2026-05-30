from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import get_current_user_session
from app.api.schemas.tickets import OwnerStatsResponse, TicketResponse
from app.db.models import Ticket
from app.db.session import get_session
from app.services.statistics_service import StatisticsService

router = APIRouter(prefix="/owner", tags=["owner"])


def verify_owner_role(session_payload: dict = Depends(get_current_user_session)) -> None:
    if session_payload["role"] != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Only owner is allowed to access owner endpoints",
        )


@router.get("/tickets", response_model=list[TicketResponse], dependencies=[Depends(verify_owner_role)])
async def list_all_tickets(
    session: AsyncSession = Depends(get_session),
) -> list[TicketResponse]:
    """
    Returns a list of all tickets in the system.
    """
    stmt = (
        select(Ticket)
        .options(selectinload(Ticket.customer))
        .order_by(Ticket.created_at.desc())
    )
    result = await session.scalars(stmt)
    tickets = result.all()
    
    return [
        TicketResponse(
            id=ticket.id,
            customer_id=ticket.customer_id,
            status=ticket.status,
            assigned_manager_telegram_id=ticket.assigned_manager_telegram_id,
            created_at=ticket.created_at,
            claimed_at=ticket.claimed_at,
            closed_at=ticket.closed_at,
            customer_username=ticket.customer.username,
            customer_first_name=ticket.customer.first_name,
            customer_last_name=ticket.customer.last_name,
        )
        for ticket in tickets
    ]


@router.get("/stats", response_model=OwnerStatsResponse, dependencies=[Depends(verify_owner_role)])
async def get_owner_stats(
    session: AsyncSession = Depends(get_session),
) -> OwnerStatsResponse:
    """
    Returns global bot statistics for the owner dashboard.
    """
    stats_service = StatisticsService()
    stats = await stats_service.owner_stats(session)
    return OwnerStatsResponse(**stats)
