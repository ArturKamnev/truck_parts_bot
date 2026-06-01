from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.config import AVAILABLE_MODELS, DEFAULT_MODEL, Settings
from app.services.authorization_service import AuthorizationService
from app.services.settings_service import SettingsService
from app.utils.exceptions import AuthorizationError


def test_owner_authorization(authorization: AuthorizationService) -> None:
    assert authorization.is_owner(999)
    assert not authorization.is_owner(101)
    assert not authorization.is_owner(None)


def test_manager_authorization(authorization: AuthorizationService) -> None:
    assert authorization.is_manager(101)
    assert not authorization.is_manager(999)
    assert not authorization.is_manager(555)


async def test_customer_cannot_switch_model(
    session,
    settings_service: SettingsService,
) -> None:
    model_id = next(iter(AVAILABLE_MODELS))
    with pytest.raises(AuthorizationError):
        await settings_service.switch_active_model(
            session,
            actor_telegram_id=555,
            model_id=model_id,
        )


def test_development_allows_one_manager() -> None:
    settings = Settings(
        BOT_TOKEN="123:test",
        OPENROUTER_API_KEY="sk-test",
        APP_ENV="development",
        DATABASE_URL="sqlite+aiosqlite:///./bot.db",
        OWNER_ID=999,
        MANAGER_IDS="999",
        DEFAULT_MODEL=DEFAULT_MODEL,
    )

    assert settings.manager_ids == [999]


def test_railway_postgres_database_url_is_normalized() -> None:
    settings = Settings(
        BOT_TOKEN="123:test",
        OPENROUTER_API_KEY="sk-test",
        APP_ENV="development",
        DATABASE_URL="postgres://user:pass@host:5432/railway",
        OWNER_ID=999,
        MANAGER_IDS="101",
        DEFAULT_MODEL=DEFAULT_MODEL,
    )

    assert settings.database_url == "postgresql+asyncpg://user:pass@host:5432/railway"


def test_standard_postgresql_database_url_is_normalized_to_asyncpg() -> None:
    settings = Settings(
        BOT_TOKEN="123:test",
        OPENROUTER_API_KEY="sk-test",
        APP_ENV="development",
        DATABASE_URL="postgresql://user:pass@host:5432/railway",
        OWNER_ID=999,
        MANAGER_IDS="101",
        DEFAULT_MODEL=DEFAULT_MODEL,
    )

    assert settings.database_url == "postgresql+asyncpg://user:pass@host:5432/railway"


def test_production_allows_flexible_manager_count() -> None:
    # 1. Production allows 1 manager
    settings_one = Settings(
        BOT_TOKEN="123:test",
        OPENROUTER_API_KEY="sk-test",
        APP_ENV="production",
        DATABASE_URL="postgresql+asyncpg://u:p@h:5432/db",
        OWNER_ID=999,
        MANAGER_IDS="101",
        DEFAULT_MODEL=DEFAULT_MODEL,
        MINIAPP_SESSION_SECRET="production_safe_session_secret_value_12345",
        MINIAPP_ORIGIN="https://miniapp.example.com",
    )
    assert settings_one.manager_ids == [101]

    # 2. Production allows empty MANAGER_IDS
    settings_empty = Settings(
        BOT_TOKEN="123:test",
        OPENROUTER_API_KEY="sk-test",
        APP_ENV="production",
        DATABASE_URL="postgresql+asyncpg://u:p@h:5432/db",
        OWNER_ID=999,
        MANAGER_IDS="",
        DEFAULT_MODEL=DEFAULT_MODEL,
        MINIAPP_SESSION_SECRET="production_safe_session_secret_value_12345",
        MINIAPP_ORIGIN="https://miniapp.example.com",
    )
    assert settings_empty.manager_ids == []
