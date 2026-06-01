from __future__ import annotations

import pytest
from datetime import datetime, UTC, timedelta
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.api.dependencies import create_signed_session_token
from app.api.main import app
from app.config import get_settings, Settings
from app.db.models import AIMessage, Broadcast, StaffMember, Ticket, TicketMessage, User
from app.db.session import get_session
from app.utils.enums import AIMessageRole, StaffRole, StaffStatus, TicketStatus


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
async def test_customer_ticket_endpoints(app_override_session, settings: Settings, session) -> None:
    # 1. Create two customers and their tickets in the db
    now = datetime.now(UTC)
    customer_a = User(telegram_user_id=1001, username="cust_a", first_name="A", mode="AI_CHAT", last_seen_at=now)
    customer_b = User(telegram_user_id=1002, username="cust_b", first_name="B", mode="AI_CHAT", last_seen_at=now)
    session.add_all([customer_a, customer_b])
    await session.commit()
    
    # Reload to get db IDs
    stmt_a = select(User).where(User.telegram_user_id == 1001)
    customer_a = await session.scalar(stmt_a)
    stmt_b = select(User).where(User.telegram_user_id == 1002)
    customer_b = await session.scalar(stmt_b)
    
    ticket_a = Ticket(customer_id=customer_a.id, status=TicketStatus.OPEN.value, created_at=now)
    ticket_b = Ticket(customer_id=customer_b.id, status=TicketStatus.OPEN.value, created_at=now)
    session.add_all([ticket_a, ticket_b])
    await session.commit()
    
    # Generate tokens
    token_a = create_signed_session_token(1001, "customer", settings.miniapp_session_secret, 3600)
    token_b = create_signed_session_token(1002, "customer", settings.miniapp_session_secret, 3600)

    async with AsyncClient(transport=ASGITransport(app=app_override_session), base_url="http://test") as ac:
        # A accesses A's tickets -> 200
        res = await ac.get("/api/customer/tickets", headers={"Authorization": f"Bearer {token_a}"})
        assert res.status_code == 200
        assert len(res.json()) == 1
        assert res.json()[0]["id"] == ticket_a.id

        # A accesses A's single ticket details -> 200
        res = await ac.get(f"/api/customer/tickets/{ticket_a.id}", headers={"Authorization": f"Bearer {token_a}"})
        assert res.status_code == 200
        assert res.json()["id"] == ticket_a.id

        # A tries to access B's ticket -> 403
        res = await ac.get(f"/api/customer/tickets/{ticket_b.id}", headers={"Authorization": f"Bearer {token_a}"})
        assert res.status_code == 403


@pytest.mark.anyio
async def test_manager_ticket_endpoints(app_override_session, settings: Settings, session) -> None:
    # 1. Create three customers, a manager (101), and tickets
    now = datetime.now(UTC)
    customer_1 = User(telegram_user_id=1001, username="cust1", first_name="A", mode="AI_CHAT", last_seen_at=now)
    customer_2 = User(telegram_user_id=1002, username="cust2", first_name="B", mode="AI_CHAT", last_seen_at=now)
    customer_3 = User(telegram_user_id=1003, username="cust3", first_name="C", mode="AI_CHAT", last_seen_at=now)
    manager_user = User(telegram_user_id=101, username="mgr", first_name="M", mode="AI_CHAT", last_seen_at=now)
    session.add_all([customer_1, customer_2, customer_3, manager_user])
    await session.commit()
    
    # Tickets:
    # - Open (unclaimed)
    # - Claimed by Manager 101
    # - Claimed by another manager (202)
    ticket_open = Ticket(customer_id=customer_1.id, status=TicketStatus.OPEN.value, created_at=now)
    ticket_claimed_self = Ticket(
        customer_id=customer_2.id, 
        status=TicketStatus.CLAIMED.value, 
        assigned_manager_telegram_id=101, 
        claimed_at=now,
        created_at=now
    )
    ticket_claimed_other = Ticket(
        customer_id=customer_3.id, 
        status=TicketStatus.CLAIMED.value, 
        assigned_manager_telegram_id=202, 
        claimed_at=now,
        created_at=now
    )
    session.add_all([ticket_open, ticket_claimed_self, ticket_claimed_other])
    await session.commit()
    
    # Manager token (role='manager', tg_id=101)
    manager_token = create_signed_session_token(101, "manager", settings.miniapp_session_secret, 3600)
    # Customer token trying to access manager endpoint -> 403
    customer_token = create_signed_session_token(1001, "customer", settings.miniapp_session_secret, 3600)

    async with AsyncClient(transport=ASGITransport(app=app_override_session), base_url="http://test") as ac:
        # Verify customer blocked from manager endpoints
        res = await ac.get("/api/manager/tickets/new", headers={"Authorization": f"Bearer {customer_token}"})
        assert res.status_code == 403

        # Manager gets new tickets (unclaimed) -> returns ticket_open
        res = await ac.get("/api/manager/tickets/new", headers={"Authorization": f"Bearer {manager_token}"})
        assert res.status_code == 200
        new_tickets = res.json()
        assert len(new_tickets) == 1
        assert new_tickets[0]["id"] == ticket_open.id

        # Manager gets active tickets (claimed by self) -> returns ticket_claimed_self
        res = await ac.get("/api/manager/tickets/active", headers={"Authorization": f"Bearer {manager_token}"})
        assert res.status_code == 200
        active_tickets = res.json()
        assert len(active_tickets) == 1
        assert active_tickets[0]["id"] == ticket_claimed_self.id

        # Manager views unclaimed details -> 200
        res = await ac.get(f"/api/manager/tickets/{ticket_open.id}", headers={"Authorization": f"Bearer {manager_token}"})
        assert res.status_code == 200

        # Manager views own claimed details -> 200
        res = await ac.get(f"/api/manager/tickets/{ticket_claimed_self.id}", headers={"Authorization": f"Bearer {manager_token}"})
        assert res.status_code == 200

        # Manager views other manager's claimed details -> 403
        res = await ac.get(f"/api/manager/tickets/{ticket_claimed_other.id}", headers={"Authorization": f"Bearer {manager_token}"})
        assert res.status_code == 403


@pytest.mark.anyio
async def test_owner_ticket_endpoints(app_override_session, settings: Settings, session) -> None:
    now = datetime.now(UTC)
    customer_1 = User(telegram_user_id=1001, username="cust1", first_name="A", mode="AI_CHAT", last_seen_at=now)
    customer_2 = User(telegram_user_id=1002, username="cust2", first_name="B", mode="AI_CHAT", last_seen_at=now)
    session.add_all([customer_1, customer_2])
    await session.commit()
    
    ticket_a = Ticket(customer_id=customer_1.id, status=TicketStatus.OPEN.value, created_at=now)
    ticket_b = Ticket(customer_id=customer_2.id, status=TicketStatus.CLAIMED.value, assigned_manager_telegram_id=101, claimed_at=now, created_at=now)
    session.add_all([ticket_a, ticket_b])
    await session.commit()
    
    # Owner token (role='owner', tg_id=999)
    owner_token = create_signed_session_token(999, "owner", settings.miniapp_session_secret, 3600)

    async with AsyncClient(transport=ASGITransport(app=app_override_session), base_url="http://test") as ac:
        # Owner gets all tickets -> 200
        res = await ac.get("/api/owner/tickets", headers={"Authorization": f"Bearer {owner_token}"})
        assert res.status_code == 200
        assert len(res.json()) == 2

        # Owner gets statistics -> 200
        res = await ac.get("/api/owner/stats", headers={"Authorization": f"Bearer {owner_token}"})
        assert res.status_code == 200
        stats = res.json()
        assert stats["total_tickets"] == 2
        assert stats["open_tickets"] == 1
        assert stats["claimed_tickets"] == 1


@pytest.mark.anyio
async def test_role_overview_endpoints_and_owner_bulk_permissions(
    app_override_session,
    settings: Settings,
    session,
) -> None:
    now = datetime.now(UTC)
    old = now - timedelta(days=21)
    owner = User(telegram_user_id=999, username="owner", first_name="Owner", mode="AI_CHAT", last_seen_at=now)
    manager = User(telegram_user_id=101, username="mgr", first_name="Manager", mode="AI_CHAT", last_seen_at=now)
    customer = User(
        telegram_user_id=1001,
        username="cust",
        first_name="Customer",
        mode="MANAGER_CHAT",
        last_seen_at=now,
        preferred_language="en",
        broadcasts_enabled=True,
    )
    stale_customer = User(
        telegram_user_id=1002,
        username="stale",
        first_name="Stale",
        mode="WAITING_MANAGER",
        last_seen_at=old,
    )
    session.add_all([owner, manager, customer, stale_customer])
    await session.commit()
    await session.refresh(customer)
    await session.refresh(stale_customer)

    staff = StaffMember(
        telegram_user_id=101,
        role=StaffRole.MANAGER.value,
        status=StaffStatus.ACTIVE.value,
        added_by_telegram_id=999,
    )
    active_ticket = Ticket(
        customer_id=customer.id,
        status=TicketStatus.CLAIMED.value,
        assigned_manager_telegram_id=101,
        created_at=old,
        claimed_at=now,
    )
    closed_ticket = Ticket(
        customer_id=customer.id,
        status=TicketStatus.CLOSED.value,
        assigned_manager_telegram_id=101,
        closed_by_telegram_id=101,
        created_at=old,
        claimed_at=old,
        closed_at=now,
    )
    stale_ticket = Ticket(customer_id=stale_customer.id, status=TicketStatus.OPEN.value, created_at=old)
    session.add_all([staff, active_ticket, closed_ticket, stale_ticket])
    await session.flush()
    session.add_all(
        [
            TicketMessage(
                ticket_id=active_ticket.id,
                sender_type="customer",
                content_type="text",
                content="Need help",
                text_preview="Need help",
                created_at=now,
            ),
            AIMessage(
                customer_id=customer.id,
                role=AIMessageRole.USER.value,
                content="AI question",
                created_at=now,
            ),
            Broadcast(
                created_by_telegram_id=999,
                status="COMPLETED",
                recipient_count=3,
                delivered_count=2,
                failed_count=1,
                blocked_count=0,
                content_preview="hello",
            ),
        ]
    )
    await session.commit()

    owner_token = create_signed_session_token(999, "owner", settings.miniapp_session_secret, 3600)
    manager_token = create_signed_session_token(101, "manager", settings.miniapp_session_secret, 3600)
    customer_token = create_signed_session_token(1001, "customer", settings.miniapp_session_secret, 3600)

    async with AsyncClient(transport=ASGITransport(app=app_override_session), base_url="http://test") as ac:
        owner_res = await ac.get(
            "/api/owner/overview",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert owner_res.status_code == 200
        owner_data = owner_res.json()
        assert owner_data["total_users"] == 4
        assert owner_data["active_chats"] == 1
        assert owner_data["pending_chats"] == 1
        assert owner_data["ai_requests_count"] == 1
        assert owner_data["broadcast_summary"]["delivered"] == 2
        assert owner_data["manager_performance"][0]["telegram_user_id"] == 101

        manager_res = await ac.get(
            "/api/manager/overview",
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        assert manager_res.status_code == 200
        manager_data = manager_res.json()
        assert manager_data["my_active_chats"] == 1
        assert manager_data["my_closed_chats"] == 1
        assert manager_data["pending_replies"] == 1

        customer_res = await ac.get(
            "/api/customer/overview",
            headers={"Authorization": f"Bearer {customer_token}"},
        )
        assert customer_res.status_code == 200
        customer_data = customer_res.json()
        assert customer_data["active_ticket"]["id"] == active_ticket.id
        assert customer_data["broadcasts_enabled"] is True
        assert customer_data["closed_chats"] == 1

        denied_res = await ac.get(
            "/api/owner/overview",
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        assert denied_res.status_code == 403

        denied_bulk = await ac.post(
            "/api/owner/tickets/close-stale",
            json={"confirm": True, "days": 14},
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        assert denied_bulk.status_code == 403

        missing_confirm = await ac.post(
            "/api/owner/tickets/close-stale",
            json={"confirm": False, "days": 14},
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert missing_confirm.status_code == 400

        close_res = await ac.post(
            "/api/owner/tickets/close-stale",
            json={"confirm": True, "days": 14},
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert close_res.status_code == 200
        assert close_res.json()["affected_count"] == 1

    await session.refresh(stale_ticket)
    assert stale_ticket.status == TicketStatus.CLOSED.value


@pytest.mark.anyio
async def test_message_cursor_pagination(app_override_session, settings: Settings, session) -> None:
    now = datetime.now(UTC)
    customer = User(telegram_user_id=1001, username="cust", first_name="A", mode="AI_CHAT", last_seen_at=now)
    session.add(customer)
    await session.commit()
    
    stmt = select(User).where(User.telegram_user_id == 1001)
    customer = await session.scalar(stmt)
    
    ticket = Ticket(customer_id=customer.id, status=TicketStatus.OPEN.value, created_at=now)
    session.add(ticket)
    await session.commit()
    
    # Add messages with consecutive IDs/timestamps
    messages = [
        TicketMessage(
            ticket_id=ticket.id, 
            sender_type="customer", 
            content_type="text", 
            content=f"Msg {i}", 
            text_preview=f"Msg {i}",
            created_at=now
        )
        for i in range(1, 6)
    ]
    session.add_all(messages)
    await session.commit()
    
    token = create_signed_session_token(1001, "customer", settings.miniapp_session_secret, 3600)

    async with AsyncClient(transport=ASGITransport(app=app_override_session), base_url="http://test") as ac:
        # Limit 2
        res = await ac.get(
            f"/api/customer/tickets/{ticket.id}/messages?limit=2",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert res.status_code == 200
        msgs = res.json()
        assert len(msgs) == 2
        assert msgs[0]["textPreview"] == "Msg 1"
        assert msgs[1]["textPreview"] == "Msg 2"
        
        last_id = msgs[-1]["id"]
        
        # Next page: after_id = last_id, limit=2
        res = await ac.get(
            f"/api/customer/tickets/{ticket.id}/messages?limit=2&after_id={last_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert res.status_code == 200
        next_msgs = res.json()
        assert len(next_msgs) == 2
        assert next_msgs[0]["textPreview"] == "Msg 3"
        assert next_msgs[1]["textPreview"] == "Msg 4"


@pytest.mark.anyio
async def test_manager_chat_actions(app_override_session, settings: Settings, session, fake_bot) -> None:
    async def override_get_bot():
        yield fake_bot
        
    from app.api.dependencies import get_bot
    app_override_session.dependency_overrides[get_bot] = override_get_bot

    # Set up manager IDs in settings
    settings.manager_ids = [101, 102]
    
    now = datetime.now(UTC)
    cust = User(telegram_user_id=1001, username="cust", first_name="C", mode="AI_CHAT", last_seen_at=now)
    mgr_a = User(telegram_user_id=101, username="mgra", first_name="MA", mode="AI_CHAT", last_seen_at=now)
    mgr_b = User(telegram_user_id=102, username="mgrb", first_name="MB", mode="AI_CHAT", last_seen_at=now)
    owner_user = User(telegram_user_id=999, username="owner", first_name="O", mode="AI_CHAT", last_seen_at=now)
    session.add_all([cust, mgr_a, mgr_b, owner_user])
    await session.commit()
    
    await session.refresh(cust)
    await session.refresh(mgr_a)
    await session.refresh(mgr_b)
    await session.refresh(owner_user)

    ticket_open = Ticket(customer_id=cust.id, status=TicketStatus.OPEN.value, created_at=now)
    session.add(ticket_open)
    await session.commit()
    await session.refresh(ticket_open)

    # Generate Bearer tokens
    cust_token = create_signed_session_token(1001, "customer", settings.miniapp_session_secret, 3600)
    mgra_token = create_signed_session_token(101, "manager", settings.miniapp_session_secret, 3600)
    mgrb_token = create_signed_session_token(102, "manager", settings.miniapp_session_secret, 3600)
    owner_token = create_signed_session_token(999, "owner", settings.miniapp_session_secret, 3600)

    async with AsyncClient(transport=ASGITransport(app=app_override_session), base_url="http://test") as ac:
        # 1. Customer cannot claim/close/send (403)
        res = await ac.post(f"/api/manager/tickets/{ticket_open.id}/claim", headers={"Authorization": f"Bearer {cust_token}"})
        assert res.status_code == 403

        res = await ac.post(f"/api/manager/tickets/{ticket_open.id}/close", json={"asSupervisor": False}, headers={"Authorization": f"Bearer {cust_token}"})
        assert res.status_code == 403

        res = await ac.post(f"/api/manager/tickets/{ticket_open.id}/messages", json={"text": "hello"}, headers={"Authorization": f"Bearer {cust_token}"})
        assert res.status_code == 403

        # 2. Unauthorized user gets 401
        res = await ac.post(f"/api/manager/tickets/{ticket_open.id}/claim")
        assert res.status_code == 401

        # 3. Manager B cannot send to OPEN unclaimed ticket
        res = await ac.post(
            f"/api/manager/tickets/{ticket_open.id}/messages",
            json={"text": "manager try send to open"},
            headers={"Authorization": f"Bearer {mgrb_token}"}
        )
        assert res.status_code == 403

        # 4. Manager A claims OPEN ticket -> 200
        res = await ac.post(f"/api/manager/tickets/{ticket_open.id}/claim", headers={"Authorization": f"Bearer {mgra_token}"})
        assert res.status_code == 200
        assert res.json()["status"] == "CLAIMED"
        assert res.json()["assigned_manager_telegram_id"] == 101
        
        # Verify Telegram send message to customer was called
        assert any(
            m["chat_id"] == 1001 and "подключился менеджер" in m["text"]
            for m in fake_bot.sent_messages
        )
        
        # 5. Double claim returns 409
        res = await ac.post(f"/api/manager/tickets/{ticket_open.id}/claim", headers={"Authorization": f"Bearer {mgrb_token}"})
        assert res.status_code == 409

        # 6. Assigned manager A can send message -> 200
        msg_count_before = len(fake_bot.sent_messages)
        res = await ac.post(
            f"/api/manager/tickets/{ticket_open.id}/messages",
            json={"text": "hello customer from mgr a"},
            headers={"Authorization": f"Bearer {mgra_token}"}
        )
        assert res.status_code == 200
        assert res.json()["textPreview"] == "hello customer from mgr a"
        assert res.json()["deliveryStatus"] == "delivered"
        # Bot called exactly once for this message send
        assert len(fake_bot.sent_messages) == msg_count_before + 1
        assert fake_bot.sent_messages[-1]["chat_id"] == 1001
        assert fake_bot.sent_messages[-1]["text"] == "hello customer from mgr a"

        # Verify message stored exactly once in DB
        stmt = select(TicketMessage).where(TicketMessage.ticket_id == ticket_open.id, TicketMessage.sender_type == "manager")
        db_messages = (await session.scalars(stmt)).all()
        assert len(db_messages) == 1

        # 7. Another manager cannot send -> 403
        res = await ac.post(
            f"/api/manager/tickets/{ticket_open.id}/messages",
            json={"text": "hello from mgr b"},
            headers={"Authorization": f"Bearer {mgrb_token}"}
        )
        assert res.status_code == 403

        # 8. Owner without supervisor intent remains read-only -> 403
        res = await ac.post(
            f"/api/manager/tickets/{ticket_open.id}/messages",
            json={"text": "owner send", "asSupervisor": False},
            headers={"Authorization": f"Bearer {owner_token}"}
        )
        assert res.status_code == 403

        # 9. Owner can send only with explicit supervisor intent -> 200
        res = await ac.post(
            f"/api/manager/tickets/{ticket_open.id}/messages",
            json={"text": "hello from supervisor owner", "asSupervisor": True},
            headers={"Authorization": f"Bearer {owner_token}"}
        )
        assert res.status_code == 200
        assert res.json()["deliveryStatus"] == "delivered"

        # 10. Failed Telegram delivery stores FAILED status exactly once
        original_send_message = fake_bot.send_message
        
        async def failing_send_message(chat_id, text, **kwargs):
            if chat_id == 1001:
                raise Exception("Telegram rate limit / chat blocked")
            await original_send_message(chat_id=chat_id, text=text, **kwargs)
            
        fake_bot.send_message = failing_send_message
        
        res = await ac.post(
            f"/api/manager/tickets/{ticket_open.id}/messages",
            json={"text": "hello failing message", "asSupervisor": True},
            headers={"Authorization": f"Bearer {owner_token}"}
        )
        assert res.status_code == 200
        assert res.json()["deliveryStatus"] == "FAILED"
        
        stmt = select(TicketMessage).where(TicketMessage.text_preview == "hello failing message")
        db_msgs = (await session.scalars(stmt)).all()
        assert len(db_msgs) == 1
        assert db_msgs[0].delivery_status == "FAILED"
        
        fake_bot.send_message = original_send_message
        
        # 11. Manager cannot close another manager's ticket -> 403
        res = await ac.post(
            f"/api/manager/tickets/{ticket_open.id}/close",
            json={"asSupervisor": False},
            headers={"Authorization": f"Bearer {mgrb_token}"}
        )
        assert res.status_code == 403

        # 12. Owner without supervisor intent cannot close -> 403
        res = await ac.post(
            f"/api/manager/tickets/{ticket_open.id}/close",
            json={"asSupervisor": False},
            headers={"Authorization": f"Bearer {owner_token}"}
        )
        assert res.status_code == 403

        # 13. Assigned manager A can close -> 200
        res = await ac.post(
            f"/api/manager/tickets/{ticket_open.id}/close",
            json={"asSupervisor": False},
            headers={"Authorization": f"Bearer {mgra_token}"}
        )
        assert res.status_code == 200
        assert res.json()["status"] == "CLOSED"

        # 14. Closed tickets reject send -> 400
        res = await ac.post(
            f"/api/manager/tickets/{ticket_open.id}/messages",
            json={"text": "try send to closed"},
            headers={"Authorization": f"Bearer {mgra_token}"}
        )
        assert res.status_code == 400
