from __future__ import annotations

import pytest
from datetime import datetime, UTC
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.api.dependencies import create_signed_session_token, get_bot
from app.api.main import app
from app.config import get_settings, Settings
from app.db.models import Ticket, TicketMessage, User, StaffMember, AIMessage
from app.db.session import get_session
from app.utils.enums import TicketStatus, StaffRole, StaffStatus
from unittest.mock import AsyncMock

@pytest.fixture
def app_override_session(session, settings: Settings, fake_bot):
    """
    Overriding database session and settings dependencies.
    """
    async def override_get_session():
        yield session

    async def override_get_bot():
        yield fake_bot

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_bot] = override_get_bot
    yield app
    app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_customer_ticket_creation_and_rejection(app_override_session, settings: Settings, session) -> None:
    # 1. Create a customer in the db
    now = datetime.now(UTC)
    customer = User(telegram_user_id=1001, username="cust_a", first_name="A", mode="AI_CHAT", last_seen_at=now)
    session.add(customer)
    await session.commit()
    await session.refresh(customer)

    # Generate token
    token = create_signed_session_token(1001, "customer", settings.miniapp_session_secret, 3600)

    async with AsyncClient(transport=ASGITransport(app=app_override_session), base_url="http://test") as ac:
        # Create a ticket
        res = await ac.post(
            "/api/customer/tickets",
            headers={"Authorization": f"Bearer {token}"},
            json={"initialMessage": "Hello help me please"}
        )
        assert res.status_code == 200
        ticket_data = res.json()
        assert ticket_data["status"] == "OPEN"
        assert ticket_data["customer_first_name"] == "A"
        
        # Verify message was stored in DB
        ticket_id = ticket_data["id"]
        stmt = select(TicketMessage).where(TicketMessage.ticket_id == ticket_id)
        messages = (await session.scalars(stmt)).all()
        assert len(messages) == 1
        assert messages[0].content == "Hello help me please"

        # Attempt to create duplicate active ticket -> should fail
        res2 = await ac.post(
            "/api/customer/tickets",
            headers={"Authorization": f"Bearer {token}"},
            json={"initialMessage": "Another request"}
        )
        assert res2.status_code == 400

        # Close the ticket
        db_ticket = await session.get(Ticket, ticket_id)
        db_ticket.status = TicketStatus.CLOSED.value
        await session.commit()

        # Create ticket again after first is closed -> should succeed
        res3 = await ac.post(
            "/api/customer/tickets",
            headers={"Authorization": f"Bearer {token}"},
            json={"initialMessage": "Third request"}
        )
        assert res3.status_code == 200
        assert res3.json()["id"] != ticket_id


@pytest.mark.anyio
async def test_customer_send_message_permissions(app_override_session, settings: Settings, session) -> None:
    now = datetime.now(UTC)
    customer_a = User(telegram_user_id=1001, username="cust_a", first_name="A", mode="AI_CHAT", last_seen_at=now)
    customer_b = User(telegram_user_id=1002, username="cust_b", first_name="B", mode="AI_CHAT", last_seen_at=now)
    session.add_all([customer_a, customer_b])
    await session.commit()
    await session.refresh(customer_a)
    await session.refresh(customer_b)

    # Tickets: A owns ticket_a, B owns ticket_b
    ticket_a = Ticket(customer_id=customer_a.id, status=TicketStatus.OPEN.value, created_at=now)
    ticket_b = Ticket(customer_id=customer_b.id, status=TicketStatus.OPEN.value, created_at=now)
    session.add_all([ticket_a, ticket_b])
    await session.commit()

    token_a = create_signed_session_token(1001, "customer", settings.miniapp_session_secret, 3600)
    token_b = create_signed_session_token(1002, "customer", settings.miniapp_session_secret, 3600)

    async with AsyncClient(transport=ASGITransport(app=app_override_session), base_url="http://test") as ac:
        # A sends message to A's ticket -> succeeds
        res = await ac.post(
            f"/api/customer/tickets/{ticket_a.id}/messages",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"text": "Hello own ticket"}
        )
        assert res.status_code == 200
        assert res.json()["textPreview"] == "Hello own ticket"

        # A sends message to B's ticket -> 403 Forbidden
        res2 = await ac.post(
            f"/api/customer/tickets/{ticket_b.id}/messages",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"text": "Hello other ticket"}
        )
        assert res2.status_code == 403

        # Close ticket A
        db_ticket_a = await session.get(Ticket, ticket_a.id)
        db_ticket_a.status = TicketStatus.CLOSED.value
        await session.commit()

        # A sends message to closed ticket -> 400 Bad Request
        res3 = await ac.post(
            f"/api/customer/tickets/{ticket_a.id}/messages",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"text": "Message to closed ticket"}
        )
        assert res3.status_code == 400


@pytest.mark.anyio
async def test_manager_and_owner_closed_tickets(app_override_session, settings: Settings, session) -> None:
    now = datetime.now(UTC)
    customer = User(telegram_user_id=1001, username="cust_a", first_name="A", mode="AI_CHAT", last_seen_at=now)
    manager_1 = User(telegram_user_id=101, username="mgr1", first_name="M1", mode="AI_CHAT", last_seen_at=now)
    manager_2 = User(telegram_user_id=102, username="mgr2", first_name="M2", mode="AI_CHAT", last_seen_at=now)
    owner = User(telegram_user_id=999, username="owner", first_name="O", mode="AI_CHAT", last_seen_at=now)
    session.add_all([customer, manager_1, manager_2, owner])
    
    # Register active managers in DB staff table
    staff_1 = StaffMember(telegram_user_id=101, role=StaffRole.MANAGER.value, status=StaffStatus.ACTIVE.value)
    staff_2 = StaffMember(telegram_user_id=102, role=StaffRole.MANAGER.value, status=StaffStatus.ACTIVE.value)
    session.add_all([staff_1, staff_2])
    await session.commit()

    await session.refresh(customer)
    await session.refresh(manager_1)
    await session.refresh(manager_2)

    # Tickets:
    # ticket_1: assigned to manager 101, closed
    # ticket_2: assigned to manager 102, closed
    # ticket_3: open (unassigned)
    ticket_1 = Ticket(customer_id=customer.id, status=TicketStatus.CLOSED.value, assigned_manager_telegram_id=101, created_at=now, closed_at=now)
    ticket_2 = Ticket(customer_id=customer.id, status=TicketStatus.CLOSED.value, assigned_manager_telegram_id=102, created_at=now, closed_at=now)
    ticket_3 = Ticket(customer_id=customer.id, status=TicketStatus.OPEN.value, created_at=now)
    session.add_all([ticket_1, ticket_2, ticket_3])
    await session.commit()

    token_m1 = create_signed_session_token(101, "manager", settings.miniapp_session_secret, 3600)
    token_m2 = create_signed_session_token(102, "manager", settings.miniapp_session_secret, 3600)
    token_owner = create_signed_session_token(999, "owner", settings.miniapp_session_secret, 3600)
    token_customer = create_signed_session_token(1001, "customer", settings.miniapp_session_secret, 3600)

    async with AsyncClient(transport=ASGITransport(app=app_override_session), base_url="http://test") as ac:
        # Manager 1 gets closed tickets -> sees only ticket_1
        res = await ac.get("/api/manager/tickets/closed", headers={"Authorization": f"Bearer {token_m1}"})
        if res.status_code != 200:
            print("STATUS:", res.status_code)
            print("BODY:", res.json())
        assert res.status_code == 200
        tickets = res.json()
        assert len(tickets) == 1
        assert tickets[0]["id"] == ticket_1.id

        # Manager 2 gets closed tickets -> sees only ticket_2
        res = await ac.get("/api/manager/tickets/closed", headers={"Authorization": f"Bearer {token_m2}"})
        assert res.status_code == 200
        tickets = res.json()
        assert len(tickets) == 1
        assert tickets[0]["id"] == ticket_2.id

        # Owner gets closed tickets -> sees ticket_1 and ticket_2
        res = await ac.get("/api/manager/tickets/closed", headers={"Authorization": f"Bearer {token_owner}"})
        assert res.status_code == 200
        tickets = res.json()
        assert len(tickets) == 2
        ids = [t["id"] for t in tickets]
        assert ticket_1.id in ids
        assert ticket_2.id in ids

        # Customer tries to access -> 403
        res = await ac.get("/api/manager/tickets/closed", headers={"Authorization": f"Bearer {token_customer}"})
        assert res.status_code == 403


@pytest.mark.anyio
async def test_ai_chat_auth_and_history(app_override_session, settings: Settings, session, monkeypatch) -> None:
    now = datetime.now(UTC)
    customer_a = User(telegram_user_id=1001, username="cust_a", first_name="A", mode="AI_CHAT", last_seen_at=now)
    customer_b = User(telegram_user_id=1002, username="cust_b", first_name="B", mode="AI_CHAT", last_seen_at=now)
    session.add_all([customer_a, customer_b])
    await session.commit()
    await session.refresh(customer_a)
    await session.refresh(customer_b)

    token_a = create_signed_session_token(1001, "customer", settings.miniapp_session_secret, 3600)
    token_b = create_signed_session_token(1002, "customer", settings.miniapp_session_secret, 3600)

    # Mock AIService's answer method
    from app.services.ai_service import AIService
    async def mock_answer(self, session, *, customer_id: int):
        return f"Mock answer for customer_id {customer_id}", "mock-model"
    
    monkeypatch.setattr(AIService, "answer", mock_answer)

    async with AsyncClient(transport=ASGITransport(app=app_override_session), base_url="http://test") as ac:
        # 1. Access without auth -> 401
        res = await ac.post("/api/ai/chat", json={"message": "hello"})
        assert res.status_code == 401
        
        res = await ac.get("/api/ai/history")
        assert res.status_code == 401

        # 2. Chat with customer A -> 200
        res = await ac.post(
            "/api/ai/chat",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"message": "What is company stock?"}
        )
        assert res.status_code == 200
        data = res.json()
        assert "Mock answer for customer_id" in data["response"]
        assert data["model_id"] == "mock-model"

        # 3. Chat with customer B -> 200
        res = await ac.post(
            "/api/ai/chat",
            headers={"Authorization": f"Bearer {token_b}"},
            json={"message": "Tell me about shipping"}
        )
        assert res.status_code == 200

        # 4. Get history for A
        res = await ac.get("/api/ai/history", headers={"Authorization": f"Bearer {token_a}"})
        assert res.status_code == 200
        history_a = res.json()
        # History should contain User message and Assistant response
        assert len(history_a) == 2
        assert history_a[0]["role"] == "user"
        assert history_a[0]["content"] == "What is company stock?"
        assert history_a[1]["role"] == "assistant"
        assert history_a[1]["content"] == f"Mock answer for customer_id {customer_a.id}"

        # 5. Get history for B
        res = await ac.get("/api/ai/history", headers={"Authorization": f"Bearer {token_b}"})
        assert res.status_code == 200
        history_b = res.json()
        assert len(history_b) == 2
        assert history_b[0]["content"] == "Tell me about shipping"


@pytest.mark.anyio
async def test_customer_broadcast_toggle(app_override_session, settings: Settings, session) -> None:
    now = datetime.now(UTC)
    customer = User(telegram_user_id=1001, username="cust_a", first_name="A", mode="AI_CHAT", broadcasts_enabled=True, last_seen_at=now)
    session.add(customer)
    await session.commit()
    await session.refresh(customer)

    token = create_signed_session_token(1001, "customer", settings.miniapp_session_secret, 3600)

    async with AsyncClient(transport=ASGITransport(app=app_override_session), base_url="http://test") as ac:
        # Toggle off
        res = await ac.post(
            "/api/customer/profile/broadcast-toggle",
            headers={"Authorization": f"Bearer {token}"},
            json={"enabled": False}
        )
        assert res.status_code == 200
        assert res.json() is False

        # Verify in DB
        await session.refresh(customer)
        assert customer.broadcasts_enabled is False

        # Verify /api/me returns false
        res_me = await ac.get("/api/me", headers={"Authorization": f"Bearer {token}"})
        assert res_me.status_code == 200
        assert res_me.json()["broadcasts_enabled"] is False

        # Toggle on
        res = await ac.post(
            "/api/customer/profile/broadcast-toggle",
            headers={"Authorization": f"Bearer {token}"},
            json={"enabled": True}
        )
        assert res.status_code == 200
        assert res.json() is True


@pytest.mark.anyio
async def test_manager_stats_roles(app_override_session, settings: Settings, session) -> None:
    now = datetime.now(UTC)
    # Register customer, manager and owner
    customer = User(telegram_user_id=1001, username="cust", first_name="C", last_seen_at=now)
    manager_user = User(telegram_user_id=1002, username="mgr", first_name="M", last_seen_at=now)
    owner_user = User(telegram_user_id=settings.owner_id, username="owner", first_name="O", last_seen_at=now)
    
    session.add_all([customer, manager_user, owner_user])
    await session.commit()

    # Add staff member entry
    manager_staff = StaffMember(
        telegram_user_id=1002,
        role=StaffRole.MANAGER.value,
        status=StaffStatus.ACTIVE.value,
        notes="Active manager"
    )
    session.add(manager_staff)
    await session.commit()

    token_customer = create_signed_session_token(1001, "customer", settings.miniapp_session_secret, 3600)
    token_manager = create_signed_session_token(1002, "manager", settings.miniapp_session_secret, 3600)
    token_owner = create_signed_session_token(settings.owner_id, "owner", settings.miniapp_session_secret, 3600)

    async with AsyncClient(transport=ASGITransport(app=app_override_session), base_url="http://test") as ac:
        # 1. Customer blocked from manager stats -> 403
        res = await ac.get("/api/manager/stats", headers={"Authorization": f"Bearer {token_customer}"})
        assert res.status_code == 403

        # 2. Manager accesses stats -> 200
        res = await ac.get("/api/manager/stats", headers={"Authorization": f"Bearer {token_manager}"})
        assert res.status_code == 200
        data = res.json()
        assert "tickets_claimed" in data
        assert "tickets_closed" in data

        # 3. Disable manager and test access -> should be blocked
        manager_staff.status = StaffStatus.DISABLED.value
        await session.commit()

        # The role detection in get_current_user_session will evaluate role="customer" dynamically, which is blocked from verify_manager_or_owner_role
        res = await ac.get("/api/manager/stats", headers={"Authorization": f"Bearer {token_manager}"})
        assert res.status_code == 403


@pytest.mark.anyio
async def test_owner_settings_and_broadcasts_access(app_override_session, settings: Settings, session) -> None:
    now = datetime.now(UTC)
    # Register owner, manager, customer
    owner = User(telegram_user_id=settings.owner_id, username="owner", first_name="O", last_seen_at=now)
    manager = User(telegram_user_id=1002, username="mgr", first_name="M", last_seen_at=now)
    session.add_all([owner, manager])
    await session.commit()

    manager_staff = StaffMember(telegram_user_id=1002, role=StaffRole.MANAGER.value, status=StaffStatus.ACTIVE.value)
    session.add(manager_staff)
    await session.commit()

    token_owner = create_signed_session_token(settings.owner_id, "owner", settings.miniapp_session_secret, 3600)
    token_manager = create_signed_session_token(1002, "manager", settings.miniapp_session_secret, 3600)

    async with AsyncClient(transport=ASGITransport(app=app_override_session), base_url="http://test") as ac:
        # 1. Get settings active-model (Owner -> 200)
        res = await ac.get("/api/owner/settings/active-model", headers={"Authorization": f"Bearer {token_owner}"})
        assert res.status_code == 200
        data = res.json()
        assert "active_model" in data
        assert "available_models" in data

        # 2. Get settings active-model (Manager -> 403)
        res = await ac.get("/api/owner/settings/active-model", headers={"Authorization": f"Bearer {token_manager}"})
        assert res.status_code == 403

        # 3. Post settings active-model switch to allowed model
        allowed_model = list(data["available_models"].keys())[0]
        res = await ac.post(
            "/api/owner/settings/active-model",
            headers={"Authorization": f"Bearer {token_owner}"},
            json={"model_id": allowed_model}
        )
        assert res.status_code == 200
        assert res.json() == allowed_model

        # 4. Post settings active-model switch to disallowed model -> should fail
        res = await ac.post(
            "/api/owner/settings/active-model",
            headers={"Authorization": f"Bearer {token_owner}"},
            json={"model_id": "invalid_model_id"}
        )
        assert res.status_code == 400

        # 5. Customer/Manager switch model -> 403
        res = await ac.post(
            "/api/owner/settings/active-model",
            headers={"Authorization": f"Bearer {token_manager}"},
            json={"model_id": allowed_model}
        )
        assert res.status_code == 403

        # 6. Fetch broadcasts history (Owner -> 200)
        res = await ac.get("/api/owner/broadcasts", headers={"Authorization": f"Bearer {token_owner}"})
        assert res.status_code == 200
        assert isinstance(res.json(), list)

        # 7. Fetch broadcasts history (Manager -> 403)
        res = await ac.get("/api/owner/broadcasts", headers={"Authorization": f"Bearer {token_manager}"})
        assert res.status_code == 403

