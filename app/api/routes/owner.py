from __future__ import annotations

from datetime import UTC, datetime, timedelta
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import (
    get_current_user,
    get_current_user_session,
    get_settings_service,
    get_broadcast_service,
    get_ticket_service,
)
from app.api.schemas.tickets import (
    BulkActionRequest,
    BulkActionResponse,
    OwnerOverviewResponse,
    OwnerStatsResponse,
    TicketResponse,
)
from app.config import get_settings, Settings
from app.db.models import OperatorSession, Ticket, StaffMember, User
from app.db.session import get_session
from app.services.media_service import store_upload
from app.services.statistics_service import StatisticsService
from app.services.ticket_service import TicketService
from app.utils.enums import BroadcastButtonSelection, StaffRole, StaffStatus, TicketStatus
from app.utils.exceptions import AuthorizationError, TicketStateError

router = APIRouter(prefix="/owner", tags=["owner"])


def verify_owner_role(session_payload: dict = Depends(get_current_user_session)) -> None:
    if session_payload["role"] != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Only owner is allowed to access owner endpoints",
        )


def verify_owner_or_co_owner_role(
    session_payload: dict = Depends(get_current_user_session),
) -> None:
    if session_payload["role"] not in {"owner", "co_owner"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Only owner and co-owner are allowed to access owner endpoints",
        )


# --- Schemas ---
class PromoteManagerRequest(BaseModel):
    notes: str | None = None


class StaffMemberResponse(BaseModel):
    id: int
    telegram_user_id: int
    role: str
    status: str
    added_by_telegram_id: int | None
    added_at: datetime
    disabled_at: datetime | None
    notes: str | None
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    display_name: str | None = None


class BotUserResponse(BaseModel):
    id: int
    telegram_user_id: int
    username: str | None
    first_name: str | None
    last_name: str | None


class ManagerStatsResponse(BaseModel):
    telegram_user_id: int
    tickets_claimed: int
    tickets_closed: int


async def _staff_response(session: AsyncSession, staff: StaffMember) -> StaffMemberResponse:
    user_stmt = select(User).where(User.telegram_user_id == staff.telegram_user_id)
    user = await session.scalar(user_stmt)
    username = user.username if user else None
    first_name = user.first_name if user else None
    last_name = user.last_name if user else None
    if user:
        parts = [p for p in (user.first_name, user.last_name) if p]
        display_name = " ".join(parts) if parts else (user.username or f"User {user.telegram_user_id}")
    else:
        display_name = f"Telegram ID {staff.telegram_user_id}"
    return StaffMemberResponse(
        id=staff.id,
        telegram_user_id=staff.telegram_user_id,
        role=staff.role,
        status=staff.status,
        added_by_telegram_id=staff.added_by_telegram_id,
        added_at=staff.added_at,
        disabled_at=staff.disabled_at,
        notes=staff.notes,
        username=username,
        first_name=first_name,
        last_name=last_name,
        display_name=display_name,
    )


async def _unassign_active_tickets(session: AsyncSession, telegram_user_id: int) -> None:
    await session.execute(
        update(Ticket)
        .where(
            Ticket.assigned_manager_telegram_id == telegram_user_id,
            Ticket.status == TicketStatus.CLAIMED.value,
        )
        .values(
            status=TicketStatus.OPEN.value,
            assigned_manager_telegram_id=None,
            claimed_at=None,
        )
    )
    await session.execute(
        update(OperatorSession)
        .where(OperatorSession.operator_telegram_id == telegram_user_id)
        .values(selected_ticket_id=None, updated_at=datetime.now(UTC))
    )


# --- Endpoints ---

@router.get("/tickets", response_model=list[TicketResponse], dependencies=[Depends(verify_owner_or_co_owner_role)])
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


@router.get("/stats", response_model=OwnerStatsResponse, dependencies=[Depends(verify_owner_or_co_owner_role)])
async def get_owner_stats(
    session: AsyncSession = Depends(get_session),
) -> OwnerStatsResponse:
    """
    Returns global bot statistics for the owner dashboard.
    """
    stats_service = StatisticsService()
    stats = await stats_service.owner_stats(session)
    return OwnerStatsResponse(**stats)


@router.get("/overview", response_model=OwnerOverviewResponse, dependencies=[Depends(verify_owner_or_co_owner_role)])
async def get_owner_overview(
    session: AsyncSession = Depends(get_session),
    settings_srv = Depends(get_settings_service),
) -> OwnerOverviewResponse:
    active_model = await settings_srv.get_active_model(session)
    overview = await StatisticsService().owner_overview(session, active_model=active_model)
    return OwnerOverviewResponse(**overview)


@router.get("/managers", response_model=list[StaffMemberResponse], dependencies=[Depends(verify_owner_or_co_owner_role)])
async def list_managers(
    session: AsyncSession = Depends(get_session),
) -> list[StaffMemberResponse]:
    """
    Returns a list of all staff members (managers).
    """
    stmt = (
        select(StaffMember, User)
        .outerjoin(User, User.telegram_user_id == StaffMember.telegram_user_id)
        .order_by(StaffMember.added_at.desc())
    )
    result = await session.execute(stmt)
    rows = result.all()
    
    response = []
    for staff, user in rows:
        username = user.username if user else None
        first_name = user.first_name if user else None
        last_name = user.last_name if user else None
        
        display_name = ""
        if user:
            parts = [p for p in (user.first_name, user.last_name) if p]
            display_name = " ".join(parts) if parts else (user.username or f"User {user.telegram_user_id}")
        else:
            display_name = f"Telegram ID {staff.telegram_user_id}"

        response.append(
            StaffMemberResponse(
                id=staff.id,
                telegram_user_id=staff.telegram_user_id,
                role=staff.role,
                status=staff.status,
                added_by_telegram_id=staff.added_by_telegram_id,
                added_at=staff.added_at,
                disabled_at=staff.disabled_at,
                notes=staff.notes,
                username=username,
                first_name=first_name,
                last_name=last_name,
                display_name=display_name,
            )
        )
    return response


@router.get("/users", response_model=list[BotUserResponse], dependencies=[Depends(verify_owner_or_co_owner_role)])
async def list_bot_users(
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> list[BotUserResponse]:
    """
    Returns a list of registered users in the database, excluding the owner.
    """
    stmt = select(User).where(User.telegram_user_id != settings.owner_id).order_by(User.created_at.desc())
    result = await session.scalars(stmt)
    users = result.all()
    
    return [
        BotUserResponse(
            id=u.id,
            telegram_user_id=u.telegram_user_id,
            username=u.username,
            first_name=u.first_name,
            last_name=u.last_name,
        )
        for u in users
    ]


@router.post("/managers/{telegram_user_id}/promote", response_model=StaffMemberResponse, dependencies=[Depends(verify_owner_or_co_owner_role)])
async def promote_manager(
    telegram_user_id: int,
    req: PromoteManagerRequest,
    current_user_session: dict = Depends(get_current_user_session),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> StaffMemberResponse:
    """
    Promotes or re-enables a user as an active manager.
    """
    if telegram_user_id == settings.owner_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The root owner cannot be promoted as a standard manager.",
        )

    actor_id = current_user_session["telegram_user_id"]
    actor_role = current_user_session["role"]
    
    # Check if they already exist in staff_members
    stmt = select(StaffMember).where(StaffMember.telegram_user_id == telegram_user_id)
    staff = await session.scalar(stmt)
    if staff and staff.role == StaffRole.CO_OWNER.value and actor_role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the root owner can change co-owner role assignments.",
        )
    
    if staff:
        staff.status = StaffStatus.ACTIVE.value
        staff.role = StaffRole.MANAGER.value
        staff.disabled_at = None
        staff.added_by_telegram_id = actor_id
        if req.notes is not None:
            staff.notes = req.notes
    else:
        staff = StaffMember(
            telegram_user_id=telegram_user_id,
            role=StaffRole.MANAGER.value,
            status=StaffStatus.ACTIVE.value,
            added_by_telegram_id=actor_id,
            notes=req.notes,
        )
        session.add(staff)
        
    await session.commit()
    await session.refresh(staff)
    return await _staff_response(session, staff)


@router.post("/managers/{telegram_user_id}/disable", response_model=StaffMemberResponse, dependencies=[Depends(verify_owner_or_co_owner_role)])
async def disable_manager(
    telegram_user_id: int,
    current_user_session: dict = Depends(get_current_user_session),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> StaffMemberResponse:
    """
    Disables/deactivates a manager.
    """
    if telegram_user_id == settings.owner_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The root owner cannot be disabled or demoted.",
        )

    stmt = select(StaffMember).where(StaffMember.telegram_user_id == telegram_user_id)
    staff = await session.scalar(stmt)
    if not staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff member not found in database",
        )
    if staff.role == StaffRole.CO_OWNER.value and current_user_session["role"] != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the root owner can remove co-owners.",
        )
        
    staff.status = StaffStatus.DISABLED.value
    staff.disabled_at = datetime.now(UTC)
    await _unassign_active_tickets(session, telegram_user_id)
    await session.commit()
    await session.refresh(staff)
    return await _staff_response(session, staff)


@router.post("/co-owners/{telegram_user_id}/promote", response_model=StaffMemberResponse, dependencies=[Depends(verify_owner_role)])
async def promote_co_owner(
    telegram_user_id: int,
    req: PromoteManagerRequest,
    current_user_session: dict = Depends(get_current_user_session),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> StaffMemberResponse:
    if telegram_user_id == settings.owner_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The root owner is already the highest-priority owner.",
        )

    stmt = select(StaffMember).where(StaffMember.telegram_user_id == telegram_user_id)
    staff = await session.scalar(stmt)
    if staff:
        staff.status = StaffStatus.ACTIVE.value
        staff.role = StaffRole.CO_OWNER.value
        staff.disabled_at = None
        staff.added_by_telegram_id = current_user_session["telegram_user_id"]
        if req.notes is not None:
            staff.notes = req.notes
    else:
        staff = StaffMember(
            telegram_user_id=telegram_user_id,
            role=StaffRole.CO_OWNER.value,
            status=StaffStatus.ACTIVE.value,
            added_by_telegram_id=current_user_session["telegram_user_id"],
            notes=req.notes,
        )
        session.add(staff)

    await session.commit()
    await session.refresh(staff)
    return await _staff_response(session, staff)


@router.post("/co-owners/{telegram_user_id}/disable", response_model=StaffMemberResponse, dependencies=[Depends(verify_owner_role)])
async def disable_co_owner(
    telegram_user_id: int,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> StaffMemberResponse:
    if telegram_user_id == settings.owner_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The root owner cannot be disabled or demoted.",
        )

    stmt = select(StaffMember).where(StaffMember.telegram_user_id == telegram_user_id)
    staff = await session.scalar(stmt)
    if not staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff member not found in database",
        )
    if staff.role != StaffRole.CO_OWNER.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Target user is not a co-owner.",
        )

    staff.status = StaffStatus.DISABLED.value
    staff.disabled_at = datetime.now(UTC)
    await _unassign_active_tickets(session, telegram_user_id)
    await session.commit()
    await session.refresh(staff)
    return await _staff_response(session, staff)


@router.get("/managers/{telegram_user_id}/stats", response_model=ManagerStatsResponse, dependencies=[Depends(verify_owner_or_co_owner_role)])
async def get_manager_statistics(
    telegram_user_id: int,
    session: AsyncSession = Depends(get_session),
) -> ManagerStatsResponse:
    """
    Returns ticket assignment and closed statistics for a manager user ID.
    """
    # 1. Total tickets claimed by manager
    claimed_stmt = select(func.count(Ticket.id)).where(
        Ticket.assigned_manager_telegram_id == telegram_user_id
    )
    tickets_claimed = await session.scalar(claimed_stmt) or 0
    
    # 2. Total tickets closed by manager
    closed_stmt = select(func.count(Ticket.id)).where(
        Ticket.closed_by_telegram_id == telegram_user_id
    )
    tickets_closed = await session.scalar(closed_stmt) or 0
    
    return ManagerStatsResponse(
        telegram_user_id=telegram_user_id,
        tickets_claimed=tickets_claimed,
        tickets_closed=tickets_closed,
    )


@router.post(
    "/tickets/clear-closed",
    response_model=BulkActionResponse,
    dependencies=[Depends(verify_owner_or_co_owner_role)],
)
async def clear_closed_tickets_from_view(
    req: BulkActionRequest,
    session: AsyncSession = Depends(get_session),
) -> BulkActionResponse:
    if not req.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Explicit confirmation is required.",
        )
    count = await session.scalar(
        select(func.count()).select_from(Ticket).where(Ticket.status == TicketStatus.CLOSED.value)
    ) or 0
    return BulkActionResponse(
        affected_count=count,
        detail="Closed tickets are safe to clear from the Mini App view; database records were preserved.",
    )


@router.post(
    "/tickets/clear-cancelled",
    response_model=BulkActionResponse,
    dependencies=[Depends(verify_owner_or_co_owner_role)],
)
async def clear_cancelled_tickets_from_view(
    req: BulkActionRequest,
    session: AsyncSession = Depends(get_session),
) -> BulkActionResponse:
    if not req.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Explicit confirmation is required.",
        )
    count = await session.scalar(
        select(func.count())
        .select_from(Ticket)
        .where(Ticket.status == TicketStatus.CANCELLED_BY_CUSTOMER.value)
    ) or 0
    return BulkActionResponse(
        affected_count=count,
        detail="Cancelled tickets are safe to clear from the Mini App view; database records were preserved.",
    )


@router.post(
    "/tickets/close-stale",
    response_model=BulkActionResponse,
    dependencies=[Depends(verify_owner_or_co_owner_role)],
)
async def close_stale_open_tickets(
    req: BulkActionRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    ticket_service: TicketService = Depends(get_ticket_service),
) -> BulkActionResponse:
    if not req.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Explicit confirmation is required.",
        )
    cutoff = datetime.now(UTC) - timedelta(days=req.days)
    stale_tickets = list(
        await session.scalars(
            select(Ticket)
            .where(Ticket.status == TicketStatus.OPEN.value, Ticket.created_at <= cutoff)
            .order_by(Ticket.created_at.asc())
            .limit(100)
        )
    )
    for ticket in stale_tickets:
        await ticket_service.close_ticket(
            session,
            ticket_id=ticket.id,
            actor_telegram_id=current_user.telegram_user_id,
        )
    await session.commit()
    return BulkActionResponse(
        affected_count=len(stale_tickets),
        detail="Stale open tickets were closed through TicketService.",
    )


class ActiveModelResponse(BaseModel):
    active_model: str
    available_models: dict[str, str]


class SwitchModelRequest(BaseModel):
    model_id: str


class BroadcastResponse(BaseModel):
    id: int
    created_by_telegram_id: int
    status: str
    content_type: str | None = None
    content_preview: str | None
    file_name: str | None = None
    mime_type: str | None = None
    file_size: int | None = None
    button_selection: str
    recipient_count: int
    delivered_count: int
    failed_count: int
    blocked_count: int
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class BroadcastPreviewResponse(BroadcastResponse):
    eligible_recipient_count: int
    available_buttons: dict[str, bool]


class BroadcastContentRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4096)


class BroadcastButtonsRequest(BaseModel):
    selection: str = Field("none", description="none, instagram, site, or both")


def _broadcast_response(b) -> BroadcastResponse:
    return BroadcastResponse(
        id=b.id,
        created_by_telegram_id=b.created_by_telegram_id,
        status=b.status,
        content_type=b.content_type,
        content_preview=b.content_preview,
        file_name=b.file_name,
        mime_type=b.mime_type,
        file_size=b.file_size,
        button_selection=b.button_selection,
        recipient_count=b.recipient_count,
        delivered_count=b.delivered_count,
        failed_count=b.failed_count,
        blocked_count=b.blocked_count,
        created_at=b.created_at,
        started_at=b.started_at,
        completed_at=b.completed_at,
    )


@router.get("/settings/active-model", response_model=ActiveModelResponse, dependencies=[Depends(verify_owner_role)])
async def get_active_model(
    session: AsyncSession = Depends(get_session),
    settings_srv = Depends(get_settings_service),
) -> ActiveModelResponse:
    """
    Returns the currently active AI model and all available models.
    """
    from app.config import AVAILABLE_MODELS
    active = await settings_srv.get_active_model(session)
    return ActiveModelResponse(active_model=active, available_models=AVAILABLE_MODELS)


@router.post("/settings/active-model", response_model=str, dependencies=[Depends(verify_owner_role)])
async def switch_active_model(
    req: SwitchModelRequest,
    current_user_session: dict = Depends(get_current_user_session),
    session: AsyncSession = Depends(get_session),
    settings_srv = Depends(get_settings_service),
) -> str:
    """
    Switches the active AI model in settings. Enforces the root OWNER check.
    """
    from app.utils.exceptions import TicketStateError, AuthorizationError
    actor_id = current_user_session["telegram_user_id"]
    try:
        active = await settings_srv.switch_active_model(
            session, actor_telegram_id=actor_id, model_id=req.model_id
        )
        await session.commit()
        return active
    except TicketStateError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except AuthorizationError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )


@router.get("/broadcasts", response_model=list[BroadcastResponse], dependencies=[Depends(verify_owner_or_co_owner_role)])
async def list_recent_broadcasts(
    session: AsyncSession = Depends(get_session),
    broadcast_srv = Depends(get_broadcast_service),
) -> list[BroadcastResponse]:
    """
    Returns a history of recent broadcasts with high-level statistics only.
    """
    broadcasts = await broadcast_srv.recent_broadcasts(session, limit=20)
    return [_broadcast_response(b) for b in broadcasts]


@router.get("/broadcasts/{broadcast_id}", response_model=BroadcastResponse, dependencies=[Depends(verify_owner_or_co_owner_role)])
async def get_broadcast_details(
    broadcast_id: int,
    session: AsyncSession = Depends(get_session),
) -> BroadcastResponse:
    from app.db.models import Broadcast

    broadcast = await session.get(Broadcast, broadcast_id)
    if broadcast is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Broadcast not found")
    return _broadcast_response(broadcast)


@router.post("/broadcasts/drafts", response_model=BroadcastResponse, dependencies=[Depends(verify_owner_or_co_owner_role)])
async def create_broadcast_draft(
    current_user_session: dict = Depends(get_current_user_session),
    session: AsyncSession = Depends(get_session),
    broadcast_srv = Depends(get_broadcast_service),
) -> BroadcastResponse:
    try:
        broadcast = await broadcast_srv.start_draft(
            session, owner_telegram_id=current_user_session["telegram_user_id"]
        )
        await session.commit()
        await session.refresh(broadcast)
        return _broadcast_response(broadcast)
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))


@router.put("/broadcasts/{broadcast_id}/content", response_model=BroadcastResponse, dependencies=[Depends(verify_owner_or_co_owner_role)])
async def set_broadcast_text_content(
    broadcast_id: int,
    req: BroadcastContentRequest,
    current_user_session: dict = Depends(get_current_user_session),
    session: AsyncSession = Depends(get_session),
    broadcast_srv = Depends(get_broadcast_service),
) -> BroadcastResponse:
    try:
        broadcast = await broadcast_srv.set_text_content(
            session,
            owner_telegram_id=current_user_session["telegram_user_id"],
            broadcast_id=broadcast_id,
            text=req.text,
        )
        await session.commit()
        await session.refresh(broadcast)
        return _broadcast_response(broadcast)
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except TicketStateError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/broadcasts/{broadcast_id}/attachment", response_model=BroadcastResponse, dependencies=[Depends(verify_owner_or_co_owner_role)])
async def set_broadcast_attachment(
    broadcast_id: int,
    file: UploadFile = File(...),
    caption: str | None = Form(None),
    current_user_session: dict = Depends(get_current_user_session),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    broadcast_srv = Depends(get_broadcast_service),
) -> BroadcastResponse:
    try:
        upload = await store_upload(file, settings)
        broadcast = await broadcast_srv.set_uploaded_attachment(
            session,
            owner_telegram_id=current_user_session["telegram_user_id"],
            broadcast_id=broadcast_id,
            upload=upload,
            caption=caption,
        )
        await session.commit()
        await session.refresh(broadcast)
        return _broadcast_response(broadcast)
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except TicketStateError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.put("/broadcasts/{broadcast_id}/buttons", response_model=BroadcastResponse, dependencies=[Depends(verify_owner_or_co_owner_role)])
async def set_broadcast_buttons(
    broadcast_id: int,
    req: BroadcastButtonsRequest,
    current_user_session: dict = Depends(get_current_user_session),
    session: AsyncSession = Depends(get_session),
    broadcast_srv = Depends(get_broadcast_service),
) -> BroadcastResponse:
    try:
        selection = BroadcastButtonSelection(req.selection)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported broadcast button selection",
        )
    try:
        broadcast = await broadcast_srv.set_buttons(
            session,
            owner_telegram_id=current_user_session["telegram_user_id"],
            broadcast_id=broadcast_id,
            selection=selection,
        )
        await session.commit()
        await session.refresh(broadcast)
        return _broadcast_response(broadcast)
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except TicketStateError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/broadcasts/{broadcast_id}/preview", response_model=BroadcastPreviewResponse, dependencies=[Depends(verify_owner_or_co_owner_role)])
async def preview_broadcast(
    broadcast_id: int,
    current_user_session: dict = Depends(get_current_user_session),
    session: AsyncSession = Depends(get_session),
    broadcast_srv = Depends(get_broadcast_service),
) -> BroadcastPreviewResponse:
    try:
        broadcast, recipient_count = await broadcast_srv.request_final_confirmation(
            session,
            owner_telegram_id=current_user_session["telegram_user_id"],
            broadcast_id=broadcast_id,
        )
        await session.commit()
        response = _broadcast_response(broadcast)
        return BroadcastPreviewResponse(
            **response.model_dump(),
            eligible_recipient_count=recipient_count,
            available_buttons={
                selection.value: broadcast_srv.is_button_selection_available(selection)
                for selection in BroadcastButtonSelection
            },
        )
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except TicketStateError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/broadcasts/{broadcast_id}/send", response_model=BroadcastResponse, dependencies=[Depends(verify_owner_or_co_owner_role)])
async def send_broadcast(
    broadcast_id: int,
    current_user_session: dict = Depends(get_current_user_session),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    broadcast_srv = Depends(get_broadcast_service),
) -> BroadcastResponse:
    try:
        broadcast = await broadcast_srv.start_sending(
            session,
            owner_telegram_id=current_user_session["telegram_user_id"],
            broadcast_id=broadcast_id,
        )
        await session.commit()
        await session.refresh(broadcast)
        from aiogram import Bot

        bot = Bot(token=settings.bot_token)
        broadcast_srv.launch_sending_job(
            bot, broadcast_id=broadcast.id, close_bot_on_finish=True
        )
        return _broadcast_response(broadcast)
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except TicketStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.post("/broadcasts/{broadcast_id}/cancel", response_model=BroadcastResponse, dependencies=[Depends(verify_owner_or_co_owner_role)])
async def cancel_broadcast(
    broadcast_id: int,
    current_user_session: dict = Depends(get_current_user_session),
    session: AsyncSession = Depends(get_session),
    broadcast_srv = Depends(get_broadcast_service),
) -> BroadcastResponse:
    try:
        broadcast = await broadcast_srv.get_report(
            session,
            owner_telegram_id=current_user_session["telegram_user_id"],
            broadcast_id=broadcast_id,
        )
        if broadcast.status not in {"DRAFT", "READY"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only draft or ready broadcasts can be cancelled",
            )
        broadcast.status = "CANCELLED"
        broadcast.completed_at = datetime.now(UTC)
        owner_session = await session.get(
            OperatorSession, current_user_session["telegram_user_id"]
        )
        if owner_session and owner_session.active_broadcast_id == broadcast.id:
            owner_session.active_broadcast_id = None
            owner_session.workflow_state = None
            owner_session.updated_at = datetime.now(UTC)
        await session.commit()
        await session.refresh(broadcast)
        return _broadcast_response(broadcast)
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
