from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.filters.roles import IsCustomer, IsSupport
from app.handlers import customer as customer_handlers
from app.keyboards.customer import customer_keyboard
from app.keyboards.manager import manager_keyboard
from app.keyboards.owner import owner_panel_keyboard
from app.services.authorization_service import AuthorizationService
from app.services.settings_service import SettingsService
from app.services.ticket_service import TicketService


class SessionFactory:
    def __init__(self, session) -> None:
        self._session = session

    def __call__(self):
        return self

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, exc_type, exc, tb):
        return None


class FakeMessage:
    def __init__(self, *, user_id: int, text: str = "/start") -> None:
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

    async def answer(self, text: str, reply_markup=None, **kwargs):
        self.answers.append({"text": text, "reply_markup": reply_markup, **kwargs})


class FakeAIService:
    def __init__(self) -> None:
        self.answer_called = False
        self.saved: list[dict] = []

    async def save_message(self, session, *, customer_id, role, content, model_id=None):
        self.saved.append(
            {
                "customer_id": customer_id,
                "role": role,
                "content": content,
                "model_id": model_id,
            }
        )

    async def answer(self, session, *, customer_id):
        self.answer_called = True
        return "AI reply", "deepseek/deepseek-v4-flash:free"

    async def get_recent_history(self, session, *, customer_id):
        return []


@pytest.fixture
def patched_session(monkeypatch, session):
    monkeypatch.setattr(customer_handlers, "SessionLocal", SessionFactory(session))
    return session


async def test_customer_start_gets_customer_menu(
    patched_session,
    ticket_service: TicketService,
    authorization: AuthorizationService,
    settings_service: SettingsService,
) -> None:
    message = FakeMessage(user_id=500)

    await customer_handlers.start(message, ticket_service, authorization, settings_service)

    assert message.answers
    assert "AI-ассистент" in message.answers[-1]["text"]
    assert type(message.answers[-1]["reply_markup"]) is type(customer_keyboard())


async def test_customer_text_reaches_ai_routing(
    patched_session,
    ticket_service: TicketService,
    relay_service,
    authorization: AuthorizationService,
) -> None:
    message = FakeMessage(user_id=500, text="Hello")
    fake_ai = FakeAIService()

    await customer_handlers.private_text_message(
        message,
        SimpleNamespace(),
        ticket_service,
        relay_service,
        fake_ai,
    )

    assert fake_ai.answer_called
    assert message.answers[-1]["text"] == "AI reply"


async def test_requesting_manager_text_creates_ticket_and_skips_ai(
    patched_session,
    ticket_service: TicketService,
    relay_service,
) -> None:
    async with patched_session.begin():
        customer = await ticket_service.upsert_customer_from_telegram(
            patched_session,
            telegram_user_id=500,
            username="customer",
            first_name="Customer",
            last_name=None,
        )
        await ticket_service.begin_manager_request(patched_session, customer=customer)

    message = FakeMessage(user_id=500, text="Need a person")
    fake_ai = FakeAIService()

    await customer_handlers.private_text_message(
        message,
        SimpleNamespace(send_message=lambda **kwargs: None),
        ticket_service,
        relay_service,
        fake_ai,
    )

    assert not fake_ai.answer_called
    assert "Ваше обращение принято" in message.answers[-1]["text"]


async def test_manager_filters_do_not_match_customer_messages(
    authorization: AuthorizationService,
) -> None:
    event = SimpleNamespace(from_user=SimpleNamespace(id=500))

    assert not await IsSupport()(event, authorization)
    assert await IsCustomer()(event, authorization)


async def test_owner_start_gets_owner_panel_with_priority(
    patched_session,
    settings,
    settings_service: SettingsService,
    ticket_service: TicketService,
) -> None:
    settings.manager_ids.append(settings.owner_id)
    authorization = AuthorizationService(settings)
    message = FakeMessage(user_id=settings.owner_id)

    await customer_handlers.start(message, ticket_service, authorization, settings_service)

    assert message.answers
    assert "Панель владельца" in message.answers[-1]["text"]
    assert type(message.answers[-1]["reply_markup"]) is type(owner_panel_keyboard())


async def test_manager_start_gets_manager_panel(
    patched_session,
    ticket_service: TicketService,
    authorization: AuthorizationService,
    settings_service: SettingsService,
) -> None:
    message = FakeMessage(user_id=101)

    await customer_handlers.start(message, ticket_service, authorization, settings_service)

    assert message.answers
    assert "Панель менеджера" in message.answers[-1]["text"]
    assert type(message.answers[-1]["reply_markup"]) is type(manager_keyboard())


def test_only_owner_panel_contains_broadcast_actions() -> None:
    owner_markup = owner_panel_keyboard()
    manager_markup = manager_keyboard()
    owner_text = str(owner_markup)
    manager_text = str(manager_markup)

    assert "📨 Разослать" in owner_text
    assert "📋 История рассылок" in owner_text
    assert "📨 Разослать" not in manager_text
    assert "📋 История рассылок" not in manager_text
