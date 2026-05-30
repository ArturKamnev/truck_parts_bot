from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class TelegramAuthRequest(BaseModel):
    initData: str = Field(..., description="Raw Telegram WebApp initData query string")


class UserProfileResponse(BaseModel):
    telegram_user_id: int = Field(..., description="Unique Telegram user ID")
    role: str = Field(..., description="Resolved user role: owner, manager, or customer")
    username: str | None = Field(None, description="Telegram username")
    first_name: str | None = Field(None, description="Telegram first name")
    last_name: str | None = Field(None, description="Telegram last name")
    broadcasts_enabled: bool = Field(True, description="Opt-in/out setting for broadcasts")
    miniapp_url: str | None = Field(None, description="Telegram Mini App link/URL")


class TelegramAuthResponse(BaseModel):
    token: str = Field(..., description="Signed session token for authorization")
    profile: UserProfileResponse = Field(..., description="Safe user profile information")


class MeResponse(BaseModel):
    telegram_user_id: int = Field(..., description="Unique Telegram user ID")
    role: str = Field(..., description="Resolved user role: owner, manager, or customer")
    username: str | None = Field(None, description="Telegram username")
    first_name: str | None = Field(None, description="Telegram first name")
    last_name: str | None = Field(None, description="Telegram last name")
    display_name: str = Field(..., description="Concatenated display name")
    customer_mode: str | None = Field(None, description="Customer mode if user is customer")
    selected_ticket_id: int | None = Field(None, description="Currently selected ticket ID if manager/owner")
    feature_flags: dict[str, Any] = Field(default_factory=dict, description="Active feature flags")
    broadcasts_enabled: bool = Field(True, description="Opt-in/out setting for broadcasts")
    miniapp_url: str | None = Field(None, description="Telegram Mini App link/URL")
