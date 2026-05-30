from __future__ import annotations

import json
import pytest
from datetime import datetime, UTC
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.api.dependencies import create_signed_session_token, get_ai_service
from app.api.main import app
from app.config import get_settings, Settings
from app.db.models import User, AIMessage, StaffMember
from app.db.session import get_session
from app.services.ai_service import AIService
from app.utils.enums import AIMessageRole
from app.services.statistics_service import StatisticsService
from app.services.knowledge_service import KnowledgeService


@pytest.fixture
def app_override_session(session, settings: Settings):
    """
    Overriding database session and settings dependencies.
    """
    async def override_get_session():
        yield session

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_settings] = lambda: settings
    yield app
    app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_ai_chat_flow_success(app_override_session, settings: Settings, session, monkeypatch) -> None:
    # 1. Create a customer in the db
    now = datetime.now(UTC)
    customer = User(telegram_user_id=12345, username="test_cust", first_name="A", mode="AI_CHAT", last_seen_at=now)
    session.add(customer)
    await session.commit()
    await session.refresh(customer)

    # 2. Mock AIService.answer
    called = []
    async def mock_answer(*args, **kwargs):
        called.append(True)
        return "Hello user, how can I help you?", "gpt-4o"
    monkeypatch.setattr(AIService, "answer", mock_answer)

    # 3. Call first AI message
    token = create_signed_session_token(12345, "customer", settings.miniapp_session_secret, 3600)
    async with AsyncClient(transport=ASGITransport(app=app_override_session), base_url="http://test") as ac:
        res = await ac.post(
            "/api/ai/chat",
            json={"message": "First message"},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert res.status_code == 200
        assert res.json()["response"] == "Hello user, how can I help you?"
        assert res.json()["model_id"] == "gpt-4o"

    # Verify db messages
    stmt = select(AIMessage).where(AIMessage.customer_id == customer.id).order_by(AIMessage.id.asc())
    messages = list(await session.scalars(stmt))
    assert len(messages) == 2
    assert messages[0].role == AIMessageRole.USER.value
    assert messages[0].content == "First message"
    assert messages[1].role == AIMessageRole.ASSISTANT.value
    assert messages[1].content == "Hello user, how can I help you?"

    # 4. Call second AI message
    async with AsyncClient(transport=ASGITransport(app=app_override_session), base_url="http://test") as ac:
        res = await ac.post(
            "/api/ai/chat",
            json={"message": "Second message"},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert res.status_code == 200
        assert res.json()["response"] == "Hello user, how can I help you?"

    # Verify db messages again
    stmt = select(AIMessage).where(AIMessage.customer_id == customer.id).order_by(AIMessage.id.asc())
    messages = list(await session.scalars(stmt))
    assert len(messages) == 4
    assert messages[2].role == AIMessageRole.USER.value
    assert messages[2].content == "Second message"
    assert messages[3].role == AIMessageRole.ASSISTANT.value
    assert messages[3].content == "Hello user, how can I help you?"


@pytest.mark.anyio
async def test_ai_chat_flow_provider_failure(app_override_session, settings: Settings, session, monkeypatch) -> None:
    # 1. Create a customer in the db
    now = datetime.now(UTC)
    customer = User(telegram_user_id=123456, username="test_cust_fail", first_name="A", mode="AI_CHAT", last_seen_at=now)
    session.add(customer)
    await session.commit()
    await session.refresh(customer)

    # 2. Mock AIService.answer to fail
    async def mock_answer_fail(*args, **kwargs):
        raise ValueError("Simulated OpenRouter failure")
    monkeypatch.setattr(AIService, "answer", mock_answer_fail)

    # 3. Call AI message
    token = create_signed_session_token(123456, "customer", settings.miniapp_session_secret, 3600)
    async with AsyncClient(transport=ASGITransport(app=app_override_session), base_url="http://test") as ac:
        res = await ac.post(
            "/api/ai/chat",
            json={"message": "Attempt that fails"},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert res.status_code == 502
        assert "Не удалось получить ответ ИИ" in res.json()["detail"]

    # Verify that the user message was saved and committed, and assistant message is NOT saved
    stmt = select(AIMessage).where(AIMessage.customer_id == customer.id).order_by(AIMessage.id.asc())
    messages = list(await session.scalars(stmt))
    assert len(messages) == 1
    assert messages[0].role == AIMessageRole.USER.value
    assert messages[0].content == "Attempt that fails"


@pytest.mark.anyio
async def test_ai_history_filtering(session, settings_service) -> None:
    ai_service = AIService(None, settings_service, KnowledgeService())

    # 1. Create messages in DB
    customer_id = 9999
    # Valid messages
    m1 = AIMessage(customer_id=customer_id, role=AIMessageRole.USER.value, content="Hello")
    m2 = AIMessage(customer_id=customer_id, role=AIMessageRole.ASSISTANT.value, content="Hi")
    # Invalid messages
    m3 = AIMessage(customer_id=customer_id, role=AIMessageRole.USER.value, content="") # empty
    m4 = AIMessage(customer_id=customer_id, role=AIMessageRole.ASSISTANT.value, content="не удалось получить ответ от ИИ")
    m5 = AIMessage(customer_id=customer_id, role=AIMessageRole.ASSISTANT.value, content="Ответ был прерван")
    m6 = AIMessage(customer_id=customer_id, role=AIMessageRole.ASSISTANT.value, content='{"choices": [], "error": "yes"}') # Raw JSON
    # Valid containing braces (should NOT be filtered)
    m7 = AIMessage(customer_id=customer_id, role=AIMessageRole.USER.value, content="My JSON is {val: 123}")
    
    session.add_all([m1, m2, m3, m4, m5, m6, m7])
    await session.commit()

    history = await ai_service.get_recent_history(session, customer_id=customer_id)
    contents = [msg.content for msg in history]
    
    assert "Hello" in contents
    assert "Hi" in contents
    assert "My JSON is {val: 123}" in contents
    assert "" not in contents
    assert "не удалось получить ответ от ИИ" not in contents
    assert "Ответ был прерван" not in contents
    assert '{"choices": [], "error": "yes"}' not in contents


@pytest.mark.anyio
async def test_ai_prompt_language(session, settings_service) -> None:
    ai_service = AIService(None, settings_service, KnowledgeService())
    
    # User 1 prefers English
    user_en = User(id=881, telegram_user_id=881, preferred_language="en")
    # User 2 prefers Kyrgyz
    user_ky = User(id=882, telegram_user_id=882, preferred_language="ky")
    session.add_all([user_en, user_ky])
    await session.commit()

    # Verify build_messages incorporates language preference instructions
    messages_en = ai_service._build_messages([], lang="en")
    assert "You MUST write your response in English" in messages_en[0]["content"]

    messages_ky = ai_service._build_messages([], lang="ky")
    assert "You MUST write your response in Kyrgyz" in messages_ky[0]["content"]


@pytest.mark.anyio
async def test_language_endpoint_updates_preference(app_override_session, settings: Settings, session) -> None:
    now = datetime.now(UTC)
    customer = User(telegram_user_id=123, username="cust_lang", first_name="A", mode="AI_CHAT", last_seen_at=now)
    session.add(customer)
    await session.commit()
    await session.refresh(customer)

    token = create_signed_session_token(123, "customer", settings.miniapp_session_secret, 3600)
    async with AsyncClient(transport=ASGITransport(app=app_override_session), base_url="http://test") as ac:
        res = await ac.post(
            "/api/profile/language",
            json={"language": "ky"},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert res.status_code == 200
        assert res.json() == "ky"

    # Reload user
    stmt = select(User).where(User.telegram_user_id == 123)
    user = await session.scalar(stmt)
    assert user.preferred_language == "ky"


@pytest.mark.anyio
async def test_stats_endpoint_safe_defaults(app_override_session, settings: Settings, session) -> None:
    now = datetime.now(UTC)
    owner = User(telegram_user_id=999, username="owner_user", first_name="O", last_seen_at=now)
    session.add(owner)
    await session.commit()

    token = create_signed_session_token(999, "owner", settings.miniapp_session_secret, 3600)
    async with AsyncClient(transport=ASGITransport(app=app_override_session), base_url="http://test") as ac:
        res = await ac.get(
            "/api/owner/stats",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["total_customers"] >= 1
        assert data["new_customers_today"] >= 1
        assert data["total_ai_messages"] == 0
        assert data["total_tickets"] == 0
        assert data["open_tickets"] == 0
        assert data["claimed_tickets"] == 0
        assert data["closed_tickets"] == 0
        assert data["avg_first_claim_seconds"] is None
