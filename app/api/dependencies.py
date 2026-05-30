from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
from typing import Any
from urllib.parse import parse_qsl

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings, Settings
from app.db.models import User
from app.db.session import get_session

logger = logging.getLogger(__name__)


def validate_telegram_init_data(init_data: str, bot_token: str, max_age: int) -> dict[str, Any] | None:
    """
    Validates the Telegram Mini App initData query string using the BOT_TOKEN.
    Returns the parsed user dictionary if valid and not expired, otherwise None.
    """
    try:
        # Parse query string parameters
        parsed = dict(parse_qsl(init_data, keep_blank_values=True))
        if "hash" not in parsed:
            logger.warning("Telegram initData missing 'hash' parameter")
            return None
        
        received_hash = parsed.pop("hash")

        # Sort the key-value pairs alphabetically and join with newlines
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))

        # Secret key = HMAC_SHA256(key=b"WebAppData", msg=bot_token)
        secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()

        # Calculated hash = HMAC_SHA256(key=secret_key, msg=data_check_string)
        calculated_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()

        if not hmac.compare_digest(calculated_hash, received_hash):
            logger.warning("Telegram initData signature verification failed")
            return None

        # Expiration check
        auth_date_str = parsed.get("auth_date")
        if not auth_date_str:
            logger.warning("Telegram initData missing 'auth_date'")
            return None

        try:
            auth_date = int(auth_date_str)
        except ValueError:
            logger.warning("Telegram initData 'auth_date' is not a valid integer")
            return None

        current_time = int(time.time())
        if current_time - auth_date > max_age:
            logger.warning("Telegram initData is expired (auth_date: %d, current: %d)", auth_date, current_time)
            return None

        # Parse user field
        user_json_str = parsed.get("user")
        if not user_json_str:
            logger.warning("Telegram initData missing 'user' field")
            return None

        user_data = json.loads(user_json_str)
        if "id" not in user_data:
            logger.warning("Telegram user data missing 'id'")
            return None

        return user_data

    except Exception as exc:
        logger.error("Exception occurred during Telegram initData validation: %s", exc, exc_info=True)
        return None


def create_signed_session_token(telegram_user_id: int, role: str, secret: str, max_age: int) -> str:
    """
    Creates a signed session token containing telegram_user_id, role, iat, and exp.
    Format: base64(payload).signature
    """
    now = int(time.time())
    payload = {
        "telegram_user_id": telegram_user_id,
        "role": role,
        "iat": now,
        "exp": now + max_age,
    }
    
    payload_bytes = json.dumps(payload).encode("utf-8")
    payload_base64 = base64.urlsafe_b64encode(payload_bytes).decode("utf-8").rstrip("=")
    
    # Sign base64 payload
    sig = hmac.new(secret.encode("utf-8"), payload_base64.encode("utf-8"), hashlib.sha256).digest()
    sig_base64 = base64.urlsafe_b64encode(sig).decode("utf-8").rstrip("=")
    
    return f"{payload_base64}.{sig_base64}"


def verify_signed_session_token(token: str, secret: str) -> dict[str, Any] | None:
    """
    Verifies the signature and expiration of a signed session token.
    Returns the parsed payload if valid, otherwise None.
    """
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return None
        
        payload_base64, sig_base64 = parts[0], parts[1]
        
        # Verify HMAC signature in constant time
        expected_sig = hmac.new(secret.encode("utf-8"), payload_base64.encode("utf-8"), hashlib.sha256).digest()
        expected_sig_base64 = base64.urlsafe_b64encode(expected_sig).decode("utf-8").rstrip("=")
        
        if not hmac.compare_digest(sig_base64.encode("utf-8"), expected_sig_base64.encode("utf-8")):
            return None
        
        # Add padding back to base64 if needed
        missing_padding = len(payload_base64) % 4
        if missing_padding:
            payload_base64 += "=" * (4 - missing_padding)
            
        payload_bytes = base64.urlsafe_b64decode(payload_base64.encode("utf-8"))
        payload = json.loads(payload_bytes.decode("utf-8"))
        
        # Verify payload fields and expiration
        if not all(k in payload for k in ("telegram_user_id", "role", "iat", "exp")):
            return None
            
        if payload["exp"] < int(time.time()):
            return None
            
        return payload
        
    except Exception:
        return None


async def get_current_user_session(
    authorization: str | None = Header(None, alias="Authorization"),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """
    Dependency that extracts and verifies the signed session token from Authorization header.
    Expects format: "Bearer <token>"
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )
        
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format. Expected Bearer token.",
        )
    
    token = authorization.split("Bearer ")[1].strip()
    payload = verify_signed_session_token(token, settings.miniapp_session_secret)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token",
        )
        
    return payload


async def get_current_user(
    session: AsyncSession = Depends(get_session),
    payload: dict[str, Any] = Depends(get_current_user_session),
) -> User:
    """
    Dependency that fetches the authenticated User object from the database.
    """
    telegram_user_id = payload["telegram_user_id"]
    stmt = select(User).where(User.telegram_user_id == telegram_user_id)
    user = await session.scalar(stmt)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user not found in database",
        )
    return user


async def get_bot(settings: Settings = Depends(get_settings)):
    from aiogram import Bot
    bot = Bot(token=settings.bot_token)
    try:
        yield bot
    finally:
        await bot.session.close()


def get_authorization_service(settings: Settings = Depends(get_settings)):
    from app.services.authorization_service import AuthorizationService
    return AuthorizationService(settings)


def get_ticket_service(authorization=Depends(get_authorization_service)):
    from app.services.ticket_service import TicketService
    return TicketService(authorization)


def get_relay_service(
    settings: Settings = Depends(get_settings),
    ticket_service=Depends(get_ticket_service),
):
    from app.services.relay_service import RelayService
    return RelayService(settings, ticket_service)


def get_ui_state_service(
    settings: Settings = Depends(get_settings),
    authorization=Depends(get_authorization_service),
    ticket_service=Depends(get_ticket_service),
):
    from app.services.ui_state_service import UIStateService
    from app.services.keyboard_service import KeyboardService
    from app.services.settings_service import SettingsService
    keyboard_service = KeyboardService()
    settings_service = SettingsService(settings, authorization)
    return UIStateService(
        settings,
        authorization,
        keyboard_service,
        ticket_service,
        settings_service,
    )

