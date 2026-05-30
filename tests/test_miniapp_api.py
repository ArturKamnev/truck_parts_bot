from __future__ import annotations

import hmac
import hashlib
import json
import time
from urllib.parse import urlencode

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.api.dependencies import create_signed_session_token
from app.api.main import app
from app.config import get_settings, Settings
from app.db.models import User
from app.db.session import get_session


# Helper to generate a valid signed Telegram initData query string
def generate_init_data(user_dict: dict, bot_token: str, auth_date: int) -> str:
    params = {
        "auth_date": str(auth_date),
        "user": json.dumps(user_dict),
    }
    
    # Sort and join
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
    
    # Secret key = HMAC-SHA256(key=b"WebAppData", msg=bot_token)
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    
    # Signature = HMAC-SHA256(key=secret_key, msg=data_check_string)
    signature = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    
    params["hash"] = signature
    return urlencode(params)


@pytest.fixture
def app_override_session(session, settings: Settings):
    """
    Overriding the database session and settings dependencies.
    """
    async def override_get_session():
        yield session

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_settings] = lambda: settings
    yield app
    app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_health_endpoint(app_override_session) -> None:
    async with AsyncClient(transport=ASGITransport(app=app_override_session), base_url="http://test") as ac:
        response = await ac.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


@pytest.mark.anyio
async def test_telegram_auth_success_customer(app_override_session, settings: Settings, session) -> None:
    # 1. Prepare valid init data for a customer user
    user_dict = {
        "id": 55555,
        "first_name": "John",
        "last_name": "Doe",
        "username": "johndoe",
    }
    init_data = generate_init_data(user_dict, settings.bot_token, int(time.time()))

    async with AsyncClient(transport=ASGITransport(app=app_override_session), base_url="http://test") as ac:
        # 2. Call auth endpoint
        response = await ac.post("/api/auth/telegram", json={"initData": init_data})
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["profile"]["telegram_user_id"] == 55555
        assert data["profile"]["role"] == "customer"
        assert data["profile"]["username"] == "johndoe"
        assert data["profile"]["first_name"] == "John"
        assert data["profile"]["last_name"] == "Doe"

        # 3. Verify user was upserted in the database
        stmt = select(User).where(User.telegram_user_id == 55555)
        db_user = await session.scalar(stmt)
        assert db_user is not None
        assert db_user.username == "johndoe"


@pytest.mark.anyio
async def test_telegram_auth_roles_owner_and_manager(app_override_session, settings: Settings) -> None:
    async with AsyncClient(transport=ASGITransport(app=app_override_session), base_url="http://test") as ac:
        # 1. Owner role priority (user id: 999)
        owner_dict = {"id": 999, "first_name": "Owner"}
        init_data_owner = generate_init_data(owner_dict, settings.bot_token, int(time.time()))
        response_owner = await ac.post("/api/auth/telegram", json={"initData": init_data_owner})
        assert response_owner.status_code == 200
        assert response_owner.json()["profile"]["role"] == "owner"

        # 2. Manager role (user id: 101)
        manager_dict = {"id": 101, "first_name": "Manager"}
        init_data_manager = generate_init_data(manager_dict, settings.bot_token, int(time.time()))
        response_manager = await ac.post("/api/auth/telegram", json={"initData": init_data_manager})
        assert response_manager.status_code == 200
        assert response_manager.json()["profile"]["role"] == "manager"


@pytest.mark.anyio
async def test_telegram_auth_rejects_invalid_and_expired(app_override_session, settings: Settings) -> None:
    async with AsyncClient(transport=ASGITransport(app=app_override_session), base_url="http://test") as ac:
        # 1. Invalid signature
        user_dict = {"id": 12345}
        init_data = generate_init_data(user_dict, settings.bot_token, int(time.time()))
        tampered_init_data = init_data.replace("hash=", "hash=wrong_signature")
        response = await ac.post("/api/auth/telegram", json={"initData": tampered_init_data})
        assert response.status_code == 401
        assert "Invalid, expired, or malformed" in response.json()["detail"]

        # 2. Expired initData (older than max age, e.g. 2 days ago)
        expired_time = int(time.time()) - 2 * 86400
        expired_init_data = generate_init_data(user_dict, settings.bot_token, expired_time)
        response_expired = await ac.post("/api/auth/telegram", json={"initData": expired_init_data})
        assert response_expired.status_code == 401
        assert "Invalid, expired, or malformed" in response_expired.json()["detail"]


@pytest.mark.anyio
async def test_protected_endpoint_access(app_override_session, settings: Settings, session) -> None:
    # 1. Add user to the test database
    from datetime import datetime, UTC
    user = User(
        telegram_user_id=12345,
        username="testuser",
        first_name="Test",
        last_name="User",
        last_seen_at=datetime.now(UTC),
    )
    session.add(user)
    await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app_override_session), base_url="http://test") as ac:
        # 2. Access /api/me without Authorization header -> 401
        response = await ac.get("/api/me")
        assert response.status_code == 401

        # 3. Access with malformed token -> 401
        response = await ac.get("/api/me", headers={"Authorization": "Bearer malformed_token_string"})
        assert response.status_code == 401

        # 4. Access with expired token -> 401
        expired_token = create_signed_session_token(
            12345, "customer", settings.miniapp_session_secret, -10
        )
        response = await ac.get("/api/me", headers={"Authorization": f"Bearer {expired_token}"})
        assert response.status_code == 401

        # 5. Access with valid token -> 200
        valid_token = create_signed_session_token(
            12345, "customer", settings.miniapp_session_secret, 3600
        )
        response = await ac.get("/api/me", headers={"Authorization": f"Bearer {valid_token}"})
        assert response.status_code == 200
        profile = response.json()
        assert profile["telegram_user_id"] == 12345
        assert profile["username"] == "testuser"
        assert profile["role"] == "customer"
