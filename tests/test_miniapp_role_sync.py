from __future__ import annotations

import pytest
from datetime import datetime, UTC
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from fastapi import status

from app.api.dependencies import create_signed_session_token
from app.api.main import app
from app.config import get_settings, Settings
from app.db.models import User, StaffMember, Ticket
from app.db.session import get_session
from app.utils.enums import TicketStatus, StaffRole, StaffStatus
from app.services.settings_service import SettingsService
from app.services.authorization_service import AuthorizationService


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
async def test_dynamic_role_promotion_and_demotion(app_override_session, settings: Settings, session) -> None:
    # 1. Create a customer user in the database
    now = datetime.now(UTC)
    user_id = 98765
    user = User(
        telegram_user_id=user_id,
        username="dynamic_user",
        first_name="Dynamic",
        last_name="User",
        last_seen_at=now,
    )
    session.add(user)
    await session.commit()

    # 2. Create signed token (token does not contain role, but we pass "customer" to match signature)
    token = create_signed_session_token(user_id, "customer", settings.miniapp_session_secret, 3600)
    auth_headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(transport=ASGITransport(app=app_override_session), base_url="http://test") as ac:
        # A. Verify user is initially customer
        res = await ac.get("/api/me", headers=auth_headers)
        assert res.status_code == 200
        assert res.json()["role"] == "customer"

        # Manager endpoints should be blocked -> 403
        res = await ac.get("/api/manager/tickets/new", headers=auth_headers)
        assert res.status_code == 403

        # B. Promote user to manager (insert active StaffMember record)
        staff_member = StaffMember(
            telegram_user_id=user_id,
            role=StaffRole.MANAGER.value,
            status=StaffStatus.ACTIVE.value
        )
        session.add(staff_member)
        await session.commit()

        # Same token should now resolve to manager role
        res = await ac.get("/api/me", headers=auth_headers)
        assert res.status_code == 200
        assert res.json()["role"] == "manager"

        # Manager endpoints should now be accessible -> 200
        res = await ac.get("/api/manager/tickets/new", headers=auth_headers)
        assert res.status_code == 200

        # C. Disable manager (set status to disabled)
        stmt = select(StaffMember).where(StaffMember.telegram_user_id == user_id)
        staff_db = await session.scalar(stmt)
        staff_db.status = StaffStatus.DISABLED.value
        await session.commit()

        # Same token should now resolve back to customer
        res = await ac.get("/api/me", headers=auth_headers)
        assert res.status_code == 200
        assert res.json()["role"] == "customer"

        # Manager endpoints should be blocked again -> 403
        res = await ac.get("/api/manager/tickets/new", headers=auth_headers)
        assert res.status_code == 403


@pytest.mark.anyio
async def test_manager_ids_seeding_and_empty_allowed(session, settings: Settings) -> None:
    # 1. Test empty MANAGER_IDS is allowed and doesn't crash settings service
    settings.manager_ids = []
    
    auth_service = AuthorizationService(settings)
    settings_service = SettingsService(settings, auth_service)
    
    await settings_service.ensure_defaults(session)
    await session.commit()
    
    # 2. Test manager IDs seeding triggers successfully
    settings.manager_ids = [102, 103]
    
    await settings_service.ensure_defaults(session)
    await session.commit()
    
    for mid in [102, 103]:
        stmt = select(StaffMember).where(StaffMember.telegram_user_id == mid)
        staff = await session.scalar(stmt)
        assert staff is not None
        assert staff.status == StaffStatus.ACTIVE.value
        assert staff.role == StaffRole.MANAGER.value
        assert await auth_service.is_manager_db(mid, session) is True

    # 3. Test that a disabled staff member does not fallback to MANAGER_IDS
    stmt = select(StaffMember).where(StaffMember.telegram_user_id == 102)
    staff_102 = await session.scalar(stmt)
    staff_102.status = StaffStatus.DISABLED.value
    await session.commit()
    
    # Even though 102 is in settings.manager_ids, the db status is disabled,
    # so they should not resolve to manager.
    assert await auth_service.is_manager_db(102, session) is False


@pytest.mark.anyio
async def test_owner_priority_and_demote_protection(session, settings: Settings, app_override_session) -> None:
    auth_service = AuthorizationService(settings)
    
    # Owner (999) has highest priority, even if they are marked as disabled in staff_members
    assert auth_service.is_owner(settings.owner_id) is True
    assert await auth_service.detect_role_db(settings.owner_id, session) == "owner"
    
    owner_staff = StaffMember(
        telegram_user_id=settings.owner_id,
        role=StaffRole.MANAGER.value,
        status=StaffStatus.DISABLED.value
    )
    session.add(owner_staff)
    await session.commit()
    
    # Role should still be owner
    assert await auth_service.detect_role_db(settings.owner_id, session) == "owner"
    assert await auth_service.is_manager_db(settings.owner_id, session) is False
    
    # API endpoints: trying to promote or disable the root owner must return 400 Bad Request
    owner_token = create_signed_session_token(settings.owner_id, "owner", settings.miniapp_session_secret, 3600)
    auth_headers = {"Authorization": f"Bearer {owner_token}"}
    
    async with AsyncClient(transport=ASGITransport(app=app_override_session), base_url="http://test") as ac:
        # Promote owner ID -> 400
        res = await ac.post(f"/api/owner/managers/{settings.owner_id}/promote", json={}, headers=auth_headers)
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "owner cannot be promoted" in res.json()["detail"].lower()
        
        # Disable owner ID -> 400
        res = await ac.post(f"/api/owner/managers/{settings.owner_id}/disable", headers=auth_headers)
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "owner cannot be disabled" in res.json()["detail"].lower()


@pytest.mark.anyio
async def test_owner_endpoints_access_control(session, settings: Settings, app_override_session) -> None:
    # 1. Create owner, manager, customer tokens
    owner_token = create_signed_session_token(settings.owner_id, "owner", settings.miniapp_session_secret, 3600)
    manager_token = create_signed_session_token(101, "manager", settings.miniapp_session_secret, 3600)
    customer_token = create_signed_session_token(8888, "customer", settings.miniapp_session_secret, 3600)
    
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    manager_headers = {"Authorization": f"Bearer {manager_token}"}
    customer_headers = {"Authorization": f"Bearer {customer_token}"}
    
    # Seed manager in database
    manager_staff = StaffMember(telegram_user_id=101, role=StaffRole.MANAGER.value, status=StaffStatus.ACTIVE.value)
    session.add(manager_staff)
    
    # Create customer user
    cust_user = User(telegram_user_id=8888, username="cust", first_name="Cust", last_seen_at=datetime.now(UTC))
    session.add(cust_user)
    await session.commit()
    
    async with AsyncClient(transport=ASGITransport(app=app_override_session), base_url="http://test") as ac:
        # A. Manager / Customer receive 403 on owner endpoints
        for headers in [manager_headers, customer_headers]:
            res = await ac.get("/api/owner/managers", headers=headers)
            assert res.status_code == status.HTTP_403_FORBIDDEN
            
            res = await ac.get("/api/owner/users", headers=headers)
            assert res.status_code == status.HTTP_403_FORBIDDEN
            
            res = await ac.post("/api/owner/managers/8888/promote", json={}, headers=headers)
            assert res.status_code == status.HTTP_403_FORBIDDEN
            
            res = await ac.post("/api/owner/managers/101/disable", headers=headers)
            assert res.status_code == status.HTTP_403_FORBIDDEN
            
            res = await ac.get("/api/owner/managers/101/stats", headers=headers)
            assert res.status_code == status.HTTP_403_FORBIDDEN
            
        # B. Owner can successfully use endpoints
        # List managers
        res = await ac.get("/api/owner/managers", headers=owner_headers)
        assert res.status_code == 200
        assert len(res.json()) >= 1
        
        # List users
        res = await ac.get("/api/owner/users", headers=owner_headers)
        assert res.status_code == 200
        assert len(res.json()) >= 1
        
        # Promote customer
        res = await ac.post("/api/owner/managers/8888/promote", json={"notes": "Excellent new manager"}, headers=owner_headers)
        assert res.status_code == 200
        assert res.json()["status"] == "active"
        assert res.json()["notes"] == "Excellent new manager"
        
        # Check customer's role is updated to manager instantly
        res = await ac.get("/api/me", headers=customer_headers)
        assert res.status_code == 200
        assert res.json()["role"] == "manager"
        
        # Get manager stats
        res = await ac.get("/api/owner/managers/8888/stats", headers=owner_headers)
        assert res.status_code == 200
        assert res.json()["tickets_claimed"] == 0
        
        # Disable manager
        res = await ac.post("/api/owner/managers/8888/disable", headers=owner_headers)
        assert res.status_code == 200
        assert res.json()["status"] == "disabled"
        
        # Customer's role is back to customer
        res = await ac.get("/api/me", headers=customer_headers)
        assert res.status_code == 200
        assert res.json()["role"] == "customer"


@pytest.mark.anyio
async def test_co_owner_role_boundaries_and_manager_demotion(
    session, settings: Settings, app_override_session
) -> None:
    now = datetime.now(UTC)
    co_owner_id = 2020
    manager_id = 3030
    customer_id = 4040
    user_to_manage_id = 5050
    session.add_all(
        [
            User(telegram_user_id=co_owner_id, username="co", first_name="Co", last_seen_at=now),
            User(telegram_user_id=manager_id, username="mgr", first_name="Mgr", last_seen_at=now),
            User(telegram_user_id=customer_id, username="cust", first_name="Cust", last_seen_at=now),
            User(telegram_user_id=user_to_manage_id, username="future", first_name="Future", last_seen_at=now),
        ]
    )
    await session.commit()
    customer = await session.scalar(select(User).where(User.telegram_user_id == customer_id))
    session.add_all(
        [
            StaffMember(
                telegram_user_id=co_owner_id,
                role=StaffRole.CO_OWNER.value,
                status=StaffStatus.ACTIVE.value,
            ),
            StaffMember(
                telegram_user_id=manager_id,
                role=StaffRole.MANAGER.value,
                status=StaffStatus.ACTIVE.value,
            ),
        ]
    )
    ticket = Ticket(
        customer_id=customer.id,
        status=TicketStatus.CLAIMED.value,
        assigned_manager_telegram_id=manager_id,
        claimed_at=now,
        created_at=now,
    )
    session.add(ticket)
    await session.commit()

    owner_token = create_signed_session_token(settings.owner_id, "owner", settings.miniapp_session_secret, 3600)
    co_token = create_signed_session_token(co_owner_id, "co_owner", settings.miniapp_session_secret, 3600)
    manager_token = create_signed_session_token(manager_id, "manager", settings.miniapp_session_secret, 3600)
    customer_token = create_signed_session_token(customer_id, "customer", settings.miniapp_session_secret, 3600)
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    co_headers = {"Authorization": f"Bearer {co_token}"}
    manager_headers = {"Authorization": f"Bearer {manager_token}"}
    customer_headers = {"Authorization": f"Bearer {customer_token}"}

    async with AsyncClient(transport=ASGITransport(app=app_override_session), base_url="http://test") as ac:
        res = await ac.get("/api/me", headers=co_headers)
        assert res.status_code == 200
        assert res.json()["role"] == "co_owner"

        res = await ac.get("/api/owner/stats", headers=co_headers)
        assert res.status_code == 200
        res = await ac.get("/api/owner/managers", headers=co_headers)
        assert res.status_code == 200
        res = await ac.get("/api/manager/tickets/active", headers=co_headers)
        assert res.status_code == 200

        res = await ac.post(
            f"/api/owner/managers/{user_to_manage_id}/promote",
            json={"notes": "co-owner promoted"},
            headers=co_headers,
        )
        assert res.status_code == 200
        assert res.json()["role"] == "manager"

        res = await ac.post(
            f"/api/owner/managers/{user_to_manage_id}/disable",
            headers=co_headers,
        )
        assert res.status_code == 200
        assert res.json()["status"] == "disabled"

        res = await ac.post(
            f"/api/owner/co-owners/{manager_id}/promote",
            json={},
            headers=co_headers,
        )
        assert res.status_code == status.HTTP_403_FORBIDDEN

        res = await ac.post(
            f"/api/owner/co-owners/{manager_id}/promote",
            json={"notes": "trusted"},
            headers=owner_headers,
        )
        assert res.status_code == 200
        assert res.json()["role"] == "co_owner"

        res = await ac.post(
            f"/api/owner/managers/{manager_id}/disable",
            headers=co_headers,
        )
        assert res.status_code == status.HTTP_403_FORBIDDEN

        res = await ac.post(
            f"/api/owner/co-owners/{manager_id}/disable",
            headers=owner_headers,
        )
        assert res.status_code == 200
        assert res.json()["status"] == "disabled"

        res = await ac.get("/api/me", headers=manager_headers)
        assert res.status_code == 200
        assert res.json()["role"] == "customer"

        await session.refresh(ticket)
        assert ticket.status == TicketStatus.OPEN.value
        assert ticket.assigned_manager_telegram_id is None

        for headers in [manager_headers, customer_headers]:
            res = await ac.post(
                f"/api/owner/co-owners/{customer_id}/promote",
                json={},
                headers=headers,
            )
            assert res.status_code == status.HTTP_403_FORBIDDEN
