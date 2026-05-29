from __future__ import annotations

from functools import lru_cache
from typing import Annotated
from urllib.parse import urlparse

from pydantic import Field, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

AVAILABLE_MODELS = {
    "deepseek/deepseek-v4-flash:free": "DeepSeek V4 Flash — fast default",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free": (
        "NVIDIA Nemotron 3 Nano Omni — reasoning"
    ),
    "google/gemma-4-31b-it:free": "Google Gemma 4 31B — multilingual",
}

DEFAULT_MODEL = "deepseek/deepseek-v4-flash:free"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: str = Field(alias="BOT_TOKEN")
    openrouter_api_key: str = Field(alias="OPENROUTER_API_KEY")
    app_env: str = Field(default="development", alias="APP_ENV")
    database_url: str = Field(default="sqlite+aiosqlite:///./bot.db", alias="DATABASE_URL")
    owner_id: int = Field(alias="OWNER_ID")
    manager_ids: Annotated[list[int], NoDecode] = Field(alias="MANAGER_IDS")
    default_model: str = Field(default=DEFAULT_MODEL, alias="DEFAULT_MODEL")
    openrouter_app_name: str = Field(default="Company Support Bot", alias="OPENROUTER_APP_NAME")
    openrouter_site_url: str | None = Field(default=None, alias="OPENROUTER_SITE_URL")
    ai_history_limit: int = Field(default=12, ge=2, le=50, alias="AI_HISTORY_LIMIT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    instagram_url: str | None = Field(default=None, alias="INSTAGRAM_URL")
    official_site_url: str | None = Field(default=None, alias="OFFICIAL_SITE_URL")
    broadcast_rate_per_second: int = Field(
        default=20, ge=1, le=30, alias="BROADCAST_RATE_PER_SECOND"
    )

    @field_validator("app_env")
    @classmethod
    def normalize_app_env(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"development", "production"}:
            raise ValueError("APP_ENV must be development or production")
        return normalized

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("DATABASE_URL must be a string")
        stripped = value.strip()
        if not stripped:
            raise ValueError("DATABASE_URL must not be empty")
        if stripped.startswith("postgres://"):
            return "postgresql+asyncpg://" + stripped.removeprefix("postgres://")
        if stripped.startswith("postgresql://"):
            return "postgresql+asyncpg://" + stripped.removeprefix("postgresql://")
        return stripped

    @field_validator("manager_ids", mode="before")
    @classmethod
    def parse_manager_ids(cls, value: str | list[int]) -> list[int]:
        if isinstance(value, str):
            return [int(item.strip()) for item in value.split(",") if item.strip()]
        return value

    @field_validator("manager_ids")
    @classmethod
    def validate_manager_count(cls, value: list[int], info: ValidationInfo) -> list[int]:
        unique_ids = set(value)
        if len(unique_ids) != len(value):
            raise ValueError("MANAGER_IDS must not contain duplicates")

        app_env = info.data.get("app_env", "development")
        if app_env == "development" and len(value) < 1:
            raise ValueError("MANAGER_IDS must contain at least one numeric Telegram ID")
        if app_env == "production" and len(value) != 11:
            raise ValueError("MANAGER_IDS must contain exactly 11 numeric Telegram IDs")
        return value

    @field_validator("default_model")
    @classmethod
    def validate_default_model(cls, value: str) -> str:
        if value not in AVAILABLE_MODELS:
            raise ValueError("DEFAULT_MODEL must be one of the seeded AVAILABLE_MODELS")
        return value

    @field_validator("instagram_url", "official_site_url", mode="before")
    @classmethod
    def normalize_optional_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            return None
        parsed = urlparse(stripped)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Configured broadcast URLs must be absolute http(s) URLs")
        if parsed.username or parsed.password:
            raise ValueError("Configured broadcast URLs must not contain credentials")
        return stripped

    @property
    def manager_id_set(self) -> set[int]:
        return set(self.manager_ids)


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
