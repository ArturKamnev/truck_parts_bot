from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.config import DEFAULT_MODEL, Settings
from app.db.models import AIMessage
from app.handlers import customer as customer_handlers
from app.services.ai_service import AIService, iter_openrouter_sse_deltas
from app.services.ai_streaming_lock import AIStreamingLockRegistry
from app.services.knowledge_service import KnowledgeService
from app.utils.enums import AIMessageRole
from app.utils.exceptions import AIServiceNetworkError


class SessionFactory:
    def __init__(self, session) -> None:
        self._session = session

    def __call__(self):
        return self

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, exc_type, exc, tb):
        return None


class EditableMessage:
    def __init__(self, text: str) -> None:
        self.text = text
        self.edits: list[dict] = []
        self.message_id = 10

    async def edit_text(self, text: str, **kwargs) -> None:
        self.text = text
        self.edits.append({"text": text, **kwargs})


class FakeMessage:
    def __init__(self, *, user_id: int, text: str) -> None:
        self.from_user = SimpleNamespace(
            id=user_id,
            username=f"user{user_id}",
            first_name=f"User{user_id}",
            last_name=None,
        )
        self.chat = SimpleNamespace(id=user_id, type="private")
        self.message_id = 1
        self.text = text
        self.caption = None
        self.media_group_id = None
        self.answers: list[dict] = []
        self.editable_answers: list[EditableMessage] = []

    async def answer(self, text: str, reply_markup=None, **kwargs):
        self.answers.append({"text": text, "reply_markup": reply_markup, **kwargs})
        editable = EditableMessage(text)
        self.editable_answers.append(editable)
        return editable


class FakeBot:
    token = "123:test"

    def __init__(self) -> None:
        self.sent_messages: list[dict] = []
        self.copied_messages: list[dict] = []

    async def send_message(self, **kwargs):
        self.sent_messages.append(kwargs)
        return EditableMessage(kwargs["text"])

    async def copy_message(self, **kwargs):
        self.copied_messages.append(kwargs)
        return SimpleNamespace(message_id=kwargs["message_id"])


class StreamingAIService(AIService):
    def __init__(
        self,
        settings: Settings,
        settings_service,
        *,
        deltas: list[str] | None = None,
        stream_error: Exception | None = None,
    ) -> None:
        super().__init__(settings, settings_service, KnowledgeService())
        self.deltas = deltas or []
        self.stream_error = stream_error
        self.stream_calls = 0
        self.answer_calls = 0

    async def stream_chat_completion(self, **kwargs):
        self.stream_calls += 1
        for delta in self.deltas:
            yield delta
        if self.stream_error is not None:
            raise self.stream_error

    async def answer(self, session, *, customer_id: int):
        self.answer_calls += 1
        return "fallback answer", DEFAULT_MODEL


async def _lines(items: list[str]):
    for item in items:
        yield item


async def test_streaming_parser_yields_text_deltas_and_stops_on_done() -> None:
    lines = [
        'data: {"choices":[{"delta":{"content":"Hel"}}]}',
        "",
        'data: {"choices":[{"delta":{"content":"lo"}}]}',
        "",
        "data: [DONE]",
        "",
        'data: {"choices":[{"delta":{"content":"ignored"}}]}',
        "",
    ]

    assert [item async for item in iter_openrouter_sse_deltas(_lines(lines))] == ["Hel", "lo"]


async def test_streaming_parser_ignores_malformed_chunk() -> None:
    lines = [
        "data: not-json",
        "",
        'data: {"choices":[{"delta":{"content":"ok"}}]}',
        "",
    ]

    assert [item async for item in iter_openrouter_sse_deltas(_lines(lines))] == ["ok"]


@pytest.fixture
def streaming_settings() -> Settings:
    return Settings(
        BOT_TOKEN="123:test",
        OPENROUTER_API_KEY="sk-test",
        APP_ENV="development",
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
        OWNER_ID=999,
        MANAGER_IDS="101",
        DEFAULT_MODEL=DEFAULT_MODEL,
        AI_HISTORY_LIMIT=6,
        AI_STREAMING_ENABLED=True,
        AI_STREAM_USE_TELEGRAM_DRAFT=False,
        AI_STREAM_MIN_CHARS=1,
    )


@pytest.fixture
def disabled_streaming_settings() -> Settings:
    return Settings(
        BOT_TOKEN="123:test",
        OPENROUTER_API_KEY="sk-test",
        APP_ENV="development",
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
        OWNER_ID=999,
        MANAGER_IDS="101",
        DEFAULT_MODEL=DEFAULT_MODEL,
        AI_HISTORY_LIMIT=6,
        AI_STREAMING_ENABLED=False,
    )


async def test_customer_ai_chat_text_uses_streaming_and_saves_final_once(
    monkeypatch,
    session,
    streaming_settings: Settings,
    settings_service,
    ticket_service,
    relay_service,
) -> None:
    monkeypatch.setattr(customer_handlers, "SessionLocal", SessionFactory(session))
    ai_service = StreamingAIService(
        streaming_settings, settings_service, deltas=["Hello", " world"]
    )
    message = FakeMessage(user_id=500, text="Hi")

    await customer_handlers.private_text_message(
        message,
        FakeBot(),
        ticket_service,
        relay_service,
        ai_service,
        AIStreamingLockRegistry(),
    )

    rows = list(await session.scalars(select(AIMessage).order_by(AIMessage.id)))
    assert ai_service.stream_calls == 1
    assert ai_service.answer_calls == 0
    assert [row.role for row in rows] == [AIMessageRole.USER.value, AIMessageRole.ASSISTANT.value]
    assert rows[-1].content == "Hello world"


async def test_streaming_disabled_uses_non_streaming_flow(
    monkeypatch,
    session,
    disabled_streaming_settings: Settings,
    settings_service,
    ticket_service,
    relay_service,
) -> None:
    monkeypatch.setattr(customer_handlers, "SessionLocal", SessionFactory(session))
    ai_service = StreamingAIService(
        disabled_streaming_settings, settings_service, deltas=["unused"]
    )
    message = FakeMessage(user_id=500, text="Hi")

    await customer_handlers.private_text_message(
        message,
        FakeBot(),
        ticket_service,
        relay_service,
        ai_service,
        AIStreamingLockRegistry(),
    )

    assert ai_service.stream_calls == 0
    assert ai_service.answer_calls == 1
    assert message.answers[-1]["text"] == "fallback answer"


async def test_stream_failure_before_text_falls_back_to_non_streaming(
    monkeypatch,
    session,
    streaming_settings: Settings,
    settings_service,
    ticket_service,
    relay_service,
) -> None:
    monkeypatch.setattr(customer_handlers, "SessionLocal", SessionFactory(session))
    ai_service = StreamingAIService(
        streaming_settings, settings_service, stream_error=AIServiceNetworkError("network")
    )
    message = FakeMessage(user_id=500, text="Hi")

    await customer_handlers.private_text_message(
        message,
        FakeBot(),
        ticket_service,
        relay_service,
        ai_service,
        AIStreamingLockRegistry(),
    )

    rows = list(await session.scalars(select(AIMessage).order_by(AIMessage.id)))
    assert ai_service.answer_calls == 1
    assert rows[-1].content == "fallback answer"


async def test_manager_chat_mode_never_calls_ai_streaming(
    monkeypatch,
    session,
    streaming_settings: Settings,
    settings_service,
    ticket_service,
    relay_service,
) -> None:
    monkeypatch.setattr(customer_handlers, "SessionLocal", SessionFactory(session))
    async with session.begin():
        customer = await ticket_service.upsert_customer_from_telegram(
            session,
            telegram_user_id=500,
            username="customer",
            first_name="Customer",
            last_name=None,
        )
        ticket = await ticket_service.create_ticket(
            session, customer=customer, original_request="help"
        )
        await ticket_service.claim_ticket(session, ticket_id=ticket.id, manager_telegram_id=101)

    ai_service = StreamingAIService(streaming_settings, settings_service, deltas=["nope"])
    message = FakeMessage(user_id=500, text="For manager")

    await customer_handlers.private_text_message(
        message,
        FakeBot(),
        ticket_service,
        relay_service,
        ai_service,
        AIStreamingLockRegistry(),
    )

    assert ai_service.stream_calls == 0
    assert ai_service.answer_calls == 0


async def test_concurrent_streams_for_two_users_do_not_share_buffers(
    monkeypatch,
    session,
    streaming_settings: Settings,
    settings_service,
    ticket_service,
    relay_service,
) -> None:
    monkeypatch.setattr(customer_handlers, "SessionLocal", SessionFactory(session))

    class PerUserAIService(StreamingAIService):
        async def stream_chat_completion(self, **kwargs):
            self.stream_calls += 1
            user_text = kwargs["messages"][-1]["content"]
            yield f"answer for {user_text}"

    ai_service = PerUserAIService(streaming_settings, settings_service)
    locks = AIStreamingLockRegistry()

    await customer_handlers.private_text_message(
        FakeMessage(user_id=500, text="first"),
        FakeBot(),
        ticket_service,
        relay_service,
        ai_service,
        locks,
    )
    await customer_handlers.private_text_message(
        FakeMessage(user_id=501, text="second"),
        FakeBot(),
        ticket_service,
        relay_service,
        ai_service,
        locks,
    )

    result = await session.scalars(select(AIMessage).order_by(AIMessage.id))
    contents = [row.content for row in result]
    assert "answer for first" in contents
    assert "answer for second" in contents


async def test_second_message_during_active_stream_is_rejected(
    monkeypatch,
    session,
    streaming_settings: Settings,
    settings_service,
    ticket_service,
    relay_service,
) -> None:
    monkeypatch.setattr(customer_handlers, "SessionLocal", SessionFactory(session))
    locks = AIStreamingLockRegistry()
    async with session.begin():
        customer = await ticket_service.upsert_customer_from_telegram(
            session,
            telegram_user_id=500,
            username="customer",
            first_name="Customer",
            last_name=None,
        )
    assert await locks.acquire(customer.id)

    ai_service = StreamingAIService(streaming_settings, settings_service, deltas=["unused"])
    message = FakeMessage(user_id=500, text="again")

    await customer_handlers.private_text_message(
        message,
        FakeBot(),
        ticket_service,
        relay_service,
        ai_service,
        locks,
    )

    await locks.release(customer.id)
    assert ai_service.stream_calls == 0
    assert message.answers[-1]["text"] == "Дождитесь окончания текущего ответа."
