from __future__ import annotations

from types import SimpleNamespace
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db.models import User, OperatorSession, Ticket
from app.keyboards.constants import (
    CUSTOMER_ASK_AI,
    CUSTOMER_CONTACT_MANAGER,
    CUSTOMER_CANCEL,
    CUSTOMER_CANCEL_REQUEST,
    CUSTOMER_CLOSE_CHAT,
    MANAGER_NEW_TICKETS,
    MANAGER_ACTIVE_CHATS,
    MANAGER_STATS,
    MANAGER_CLOSE_TICKET,
    MANAGER_EXIT_REPLY,
    MANAGER_MY_DIALOGS,
    OWNER_CHOOSE_MODEL,
    OWNER_STATS,
    OWNER_TICKETS,
    OWNER_BROADCAST,
    OWNER_BROADCAST_HISTORY,
    OWNER_CANCEL,
    OWNER_BACK,
)
from app.services.authorization_service import AuthorizationService
from app.services.keyboard_service import KeyboardService
from app.services.ui_state_service import UIStateService
from app.services.ticket_service import TicketService
from app.services.settings_service import SettingsService
from app.services.broadcast_service import BroadcastService
from app.utils.enums import CustomerMode, OwnerWorkflowState, TicketStatus
from app.handlers import customer as customer_handlers
from app.handlers import manager as manager_handlers
from app.handlers import owner as owner_handlers
from app.handlers import callbacks as callback_handlers

# Compatibility wrapper for patching SessionLocal in test handlers
class SessionFactory:
    def __init__(self, session) -> None:
        self._session = session

    def __call__(self):
        return self

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, exc_type, exc, tb):
        return None


@pytest.fixture
def patch_handlers_session(monkeypatch, session):
    monkeypatch.setattr(customer_handlers, "SessionLocal", SessionFactory(session))
    monkeypatch.setattr(manager_handlers, "SessionLocal", SessionFactory(session))
    monkeypatch.setattr(owner_handlers, "SessionLocal", SessionFactory(session))
    monkeypatch.setattr(callback_handlers, "SessionLocal", SessionFactory(session))
    return session


class FakeMessage:
    def __init__(self, *, user_id: int, text: str = "") -> None:
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


class FakeCallbackQuery:
    def __init__(self, *, user_id: int, data: str, message: FakeMessage) -> None:
        self.from_user = SimpleNamespace(
            id=user_id,
            username=f"user{user_id}",
            first_name=f"User{user_id}",
            last_name=None,
        )
        self.data = data
        self.message = message
        self.answered = False
        self.answer_text = None

    async def answer(self, text: str | None = None, show_alert: bool = False, **kwargs):
        self.answered = True
        self.answer_text = text


async def test_owner_priority_over_manager(
    settings: Settings,
    session: AsyncSession,
    fake_bot,
) -> None:
    # Set owner ID to be inside manager IDs list as well
    settings.manager_ids.append(settings.owner_id)
    authorization = AuthorizationService(settings)
    
    assert authorization.detect_role(settings.owner_id) == "owner"
    
    keyboard_service = KeyboardService()
    ticket_service = TicketService(authorization)
    settings_service = SettingsService(settings, authorization)
    ui_state_service = UIStateService(settings, authorization, keyboard_service, ticket_service, settings_service)

    # Trigger show_current_menu
    await ui_state_service.show_current_menu(fake_bot, session, settings.owner_id)
    
    assert len(fake_bot.sent_messages) == 1
    # Verify it has normal owner panel options
    kb = fake_bot.sent_messages[0]["reply_markup"]
    assert OWNER_CHOOSE_MODEL in kb.keyboard[0][0].text


async def test_customer_start_and_menu_recovery(
    patch_handlers_session,
    ticket_service: TicketService,
    authorization: AuthorizationService,
    settings_service: SettingsService,
    fake_bot,
) -> None:
    keyboard_service = KeyboardService()
    ui_state_service = UIStateService(settings_service._settings, authorization, keyboard_service, ticket_service, settings_service)

    message = FakeMessage(user_id=500, text="/start")
    await customer_handlers.start(
        message, ticket_service, authorization, settings_service, fake_bot, ui_state_service
    )
    
    assert len(message.answers) == 1
    assert "AI-ассистент" in message.answers[0]["text"]
    kb = message.answers[0]["reply_markup"]
    assert kb.keyboard[0][0].text == CUSTOMER_ASK_AI

    # Recovery command /menu
    menu_message = FakeMessage(user_id=500, text="/menu")
    await customer_handlers.menu_command(menu_message, fake_bot, ui_state_service)
    assert len(menu_message.answers) == 1
    assert "AI-ассистент" in menu_message.answers[0]["text"]


async def test_customer_stable_keyboard_order() -> None:
    kb_service = KeyboardService()

    # AI_CHAT state
    kb = kb_service.get_customer_keyboard(CustomerMode.AI_CHAT.value, broadcasts_enabled=True)
    assert kb.keyboard[0][0].text == CUSTOMER_ASK_AI
    assert kb.keyboard[0][1].text == CUSTOMER_CONTACT_MANAGER
    assert kb.keyboard[1][0].text == "🔔 Рассылки: включены"

    kb = kb_service.get_customer_keyboard(CustomerMode.AI_CHAT.value, broadcasts_enabled=False)
    assert kb.keyboard[1][0].text == "🔕 Рассылки: выключены"

    # REQUESTING_MANAGER state
    kb = kb_service.get_customer_keyboard(CustomerMode.REQUESTING_MANAGER.value, broadcasts_enabled=True)
    assert len(kb.keyboard) == 1
    assert kb.keyboard[0][0].text == CUSTOMER_CANCEL

    # WAITING_MANAGER state
    kb = kb_service.get_customer_keyboard(CustomerMode.WAITING_MANAGER.value, broadcasts_enabled=True)
    assert len(kb.keyboard) == 1
    assert kb.keyboard[0][0].text == CUSTOMER_CANCEL_REQUEST

    # MANAGER_CHAT state
    kb = kb_service.get_customer_keyboard(CustomerMode.MANAGER_CHAT.value, broadcasts_enabled=True)
    assert len(kb.keyboard) == 1
    assert kb.keyboard[0][0].text == CUSTOMER_CLOSE_CHAT


async def test_manager_selected_ticket_mode_keyboard_order() -> None:
    kb_service = KeyboardService()

    # Main menu
    kb = kb_service.get_manager_keyboard(selected_ticket_id=None, notifications_enabled=True)
    assert kb.keyboard[0][0].text == MANAGER_NEW_TICKETS
    assert kb.keyboard[0][1].text == MANAGER_ACTIVE_CHATS
    assert kb.keyboard[1][0].text == MANAGER_STATS
    assert kb.keyboard[1][1].text == "🔔 Уведомления: включены"

    # Selected ticket Mode
    kb = kb_service.get_manager_keyboard(selected_ticket_id=123, notifications_enabled=True)
    assert kb.keyboard[0][0].text == MANAGER_CLOSE_TICKET
    assert kb.keyboard[1][0].text == MANAGER_EXIT_REPLY
    assert kb.keyboard[2][0].text == MANAGER_MY_DIALOGS


async def test_owner_temporary_modes_do_not_show_normal_controls() -> None:
    kb_service = KeyboardService()

    # Broadcast draft workflow mode
    kb = kb_service.get_owner_keyboard(workflow_state=OwnerWorkflowState.CREATING_BROADCAST_CONTENT.value, selected_ticket_id=None)
    assert len(kb.keyboard) == 1
    assert kb.keyboard[0][0].text == OWNER_CANCEL
    assert kb.keyboard[0][1].text == OWNER_BACK

    # Model selection workflow mode
    kb = kb_service.get_owner_keyboard(workflow_state="MODEL_SELECTION", selected_ticket_id=None)
    assert len(kb.keyboard) == 1
    assert kb.keyboard[0][0].text == OWNER_CANCEL
    assert kb.keyboard[0][1].text == OWNER_BACK

    # Supervisor active ticket reply mode
    kb = kb_service.get_owner_keyboard(workflow_state=None, selected_ticket_id=123)
    assert len(kb.keyboard) == 1
    assert kb.keyboard[0][0].text == OWNER_CANCEL
    assert kb.keyboard[0][1].text == OWNER_BACK


async def test_menu_buttons_are_never_routed_to_ai_or_relay(
    patch_handlers_session,
    ticket_service: TicketService,
    relay_service,
    authorization: AuthorizationService,
) -> None:
    class MockAIService:
        def __init__(self):
            self.called = False
        async def save_message(self, *args, **kwargs):
            pass
        async def answer(self, *args, **kwargs):
            self.called = True
            return "AI answer", "model"

    # Customer sends menu button
    ai = MockAIService()
    message = FakeMessage(user_id=500, text=CUSTOMER_CONTACT_MANAGER)
    await customer_handlers.private_text_message(
        message, None, ticket_service, relay_service, ai, None, None, None
    )
    assert not ai.called


async def test_stale_callback_refreshes_menu_instead_of_failing(
    patch_handlers_session,
    ticket_service: TicketService,
    authorization: AuthorizationService,
    settings_service: SettingsService,
    relay_service,
    fake_bot,
) -> None:
    keyboard_service = KeyboardService()
    ui_state_service = UIStateService(settings_service._settings, authorization, keyboard_service, ticket_service, settings_service)

    # Callback with non-existent ticket ID (stale callback)
    message = FakeMessage(user_id=101)
    callback = FakeCallbackQuery(user_id=101, data="ticket:claim:9999", message=message)

    await callback_handlers.ticket_callback(
        callback, fake_bot, ticket_service, authorization, relay_service, ui_state_service
    )
    
    assert callback.answered
    # Verify menu refresh is triggered for support
    assert len(message.answers) == 1
    assert "Панель менеджера" in message.answers[0]["text"]
