from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import DEFAULT_MODEL, Settings
from app.db.base import Base
from app.services.ai_service import AIService
from app.services.authorization_service import AuthorizationService
from app.services.broadcast_service import BroadcastService
from app.services.knowledge_service import KnowledgeService
from app.services.relay_service import RelayService
from app.services.settings_service import SettingsService
from app.services.ticket_service import TicketService


@pytest.fixture
def settings() -> Settings:
    return Settings(
        BOT_TOKEN="123:test",
        OPENROUTER_API_KEY="sk-test",
        APP_ENV="development",
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
        OWNER_ID=999,
        MANAGER_IDS="101",
        DEFAULT_MODEL=DEFAULT_MODEL,
        AI_HISTORY_LIMIT=6,
    )


@pytest.fixture
def authorization(settings: Settings) -> AuthorizationService:
    return AuthorizationService(settings)


@pytest.fixture
def settings_service(settings: Settings, authorization: AuthorizationService) -> SettingsService:
    return SettingsService(settings, authorization)


@pytest.fixture
def ticket_service(authorization: AuthorizationService) -> TicketService:
    return TicketService(authorization)


@pytest.fixture
def ai_service(settings: Settings, settings_service: SettingsService) -> AIService:
    return AIService(settings, settings_service, KnowledgeService())


@pytest.fixture
def relay_service(
    settings: Settings, ticket_service: TicketService, ai_service: AIService
) -> RelayService:
    return RelayService(settings, ticket_service, ai_service)


@pytest.fixture
def broadcast_service(
    settings: Settings,
    authorization: AuthorizationService,
    relay_service: RelayService,
) -> BroadcastService:
    return BroadcastService(settings, authorization, relay_service)


@pytest.fixture
async def session() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with sessionmaker() as session:
        yield session
    await engine.dispose()


class FakeBot:
    def __init__(self) -> None:
        self.sent_messages: list[dict] = []
        self.copied_messages: list[dict] = []
        self.copied_message_groups: list[dict] = []
        self.copy_failures: dict[int, Exception] = {}
        self.copy_attempts: dict[int, int] = {}

    async def send_message(self, **kwargs):
        self.sent_messages.append(kwargs)
        return SimpleNamespace(message_id=len(self.sent_messages), text=kwargs.get("text"))

    async def send_photo(self, **kwargs):
        self.sent_messages.append({"method": "send_photo", **kwargs})
        return SimpleNamespace(
            message_id=len(self.sent_messages),
            photo=[SimpleNamespace(file_id="photo-file-id", file_unique_id="photo-unique-id")],
        )

    async def send_video(self, **kwargs):
        self.sent_messages.append({"method": "send_video", **kwargs})
        return SimpleNamespace(
            message_id=len(self.sent_messages),
            video=SimpleNamespace(file_id="video-file-id", file_unique_id="video-unique-id"),
        )

    async def send_audio(self, **kwargs):
        self.sent_messages.append({"method": "send_audio", **kwargs})
        return SimpleNamespace(
            message_id=len(self.sent_messages),
            audio=SimpleNamespace(file_id="audio-file-id", file_unique_id="audio-unique-id"),
        )

    async def send_document(self, **kwargs):
        self.sent_messages.append({"method": "send_document", **kwargs})
        return SimpleNamespace(
            message_id=len(self.sent_messages),
            document=SimpleNamespace(
                file_id="document-file-id",
                file_unique_id="document-unique-id",
            ),
        )

    async def copy_message(self, **kwargs):
        chat_id = kwargs["chat_id"]
        self.copy_attempts[chat_id] = self.copy_attempts.get(chat_id, 0) + 1
        failure = self.copy_failures.get(chat_id)
        if failure is not None:
            raise failure
        self.copied_messages.append(kwargs)
        return SimpleNamespace(message_id=kwargs["message_id"])

    async def copy_messages(self, **kwargs):
        self.copied_message_groups.append(kwargs)
        return [SimpleNamespace(message_id=message_id) for message_id in kwargs["message_ids"]]


@pytest.fixture
def fake_bot() -> FakeBot:
    return FakeBot()
