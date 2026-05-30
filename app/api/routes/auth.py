from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    create_signed_session_token,
    get_current_user,
    get_current_user_session,
    validate_telegram_init_data,
)
from app.api.schemas.auth import TelegramAuthRequest, TelegramAuthResponse, UserProfileResponse, MeResponse
from app.config import get_settings, Settings
from app.db.models import User
from app.db.session import get_session
from app.services.authorization_service import AuthorizationService
from app.services.ticket_service import TicketService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["authentication"])


@router.post("/auth/telegram", response_model=TelegramAuthResponse)
async def telegram_auth(
    payload: TelegramAuthRequest,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> TelegramAuthResponse:
    """
    Validates Telegram WebApp initData, synchronizes user profile,
    and returns a signed session token.
    """
    # 1. Validate initData
    tg_user = validate_telegram_init_data(
        init_data=payload.initData,
        bot_token=settings.bot_token,
        max_age=settings.miniapp_auth_max_age_seconds,
        app_env=settings.app_env,
    )
    if tg_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid, expired, or malformed Telegram WebApp initData",
        )

    telegram_user_id = tg_user["id"]

    # 2. Resolve Role (Owner > Manager > Customer)
    authorization_service = AuthorizationService(settings)
    role = await authorization_service.detect_role_db(telegram_user_id, session)

    # 3. Synchronize user profile in database using the existing TicketService helper
    ticket_service = TicketService(authorization_service)
    user = await ticket_service.upsert_user_from_telegram(
        session,
        telegram_user_id=telegram_user_id,
        username=tg_user.get("username"),
        first_name=tg_user.get("first_name"),
        last_name=tg_user.get("last_name"),
    )
    # Commit change
    await session.commit()

    # 4. Generate signed session token
    token = create_signed_session_token(
        telegram_user_id=telegram_user_id,
        role=role,
        secret=settings.miniapp_session_secret,
        max_age=settings.miniapp_auth_max_age_seconds,
    )

    profile = UserProfileResponse(
        telegram_user_id=user.telegram_user_id,
        role=role,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        broadcasts_enabled=user.broadcasts_enabled,
        miniapp_url=settings.miniapp_url,
    )

    return TelegramAuthResponse(token=token, profile=profile)


from app.db.models import OperatorSession

@router.get("/me", response_model=MeResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
    session_payload: dict = Depends(get_current_user_session),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> MeResponse:
    """
    Protected endpoint to fetch the current user profile from database.
    """
    role = session_payload["role"]
    
    parts = [p for p in (current_user.first_name, current_user.last_name) if p]
    display_name = " ".join(parts) if parts else (current_user.username or f"User {current_user.telegram_user_id}")
    
    customer_mode = current_user.mode if role == "customer" else None
    
    selected_ticket_id = None
    if role in ("manager", "owner"):
        op_sess = await session.get(OperatorSession, current_user.telegram_user_id)
        if op_sess:
            selected_ticket_id = op_sess.selected_ticket_id
            
    feature_flags = {
        "ai_streaming_enabled": settings.ai_streaming_enabled,
    }
    
    return MeResponse(
        telegram_user_id=current_user.telegram_user_id,
        role=role,
        username=current_user.username,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        display_name=display_name,
        customer_mode=customer_mode,
        selected_ticket_id=selected_ticket_id,
        feature_flags=feature_flags,
        broadcasts_enabled=current_user.broadcasts_enabled,
        miniapp_url=settings.miniapp_url,
    )
