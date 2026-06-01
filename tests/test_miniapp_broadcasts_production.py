from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import create_signed_session_token, validate_telegram_init_data
from app.api.main import app
from app.config import DEFAULT_MODEL, Settings, get_settings
from app.db.models import StaffMember, User
from app.db.session import get_session
from app.services.broadcast_service import BroadcastService
from app.utils.enums import StaffRole, StaffStatus


@pytest.fixture
def app_override_session(session, settings: Settings):
    async def override_get_session():
        yield session

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_settings] = lambda: settings
    yield app
    app.dependency_overrides.clear()


async def _seed_user(session, telegram_user_id: int) -> User:
    user = User(
        telegram_user_id=telegram_user_id,
        username=f"user{telegram_user_id}",
        first_name=f"User{telegram_user_id}",
        mode="AI_CHAT",
        last_seen_at=datetime.now(UTC),
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@pytest.mark.anyio
async def test_owner_and_co_owner_can_create_preview_and_send_broadcast(
    app_override_session,
    settings: Settings,
    session,
    monkeypatch,
) -> None:
    async def no_active_job(*args, **kwargs):
        return False

    monkeypatch.setattr(BroadcastService, "launch_sending_job", lambda *args, **kwargs: None)
    monkeypatch.setattr(BroadcastService, "has_active_sending_job", no_active_job)

    await _seed_user(session, settings.owner_id)
    await _seed_user(session, 5001)
    await _seed_user(session, 5002)
    co_owner = await _seed_user(session, 777)
    session.add(
        StaffMember(
            telegram_user_id=co_owner.telegram_user_id,
            role=StaffRole.CO_OWNER.value,
            status=StaffStatus.ACTIVE.value,
        )
    )
    await session.commit()

    owner_token = create_signed_session_token(settings.owner_id, "owner", settings.miniapp_session_secret, 3600)
    co_owner_token = create_signed_session_token(777, "co_owner", settings.miniapp_session_secret, 3600)

    async with AsyncClient(transport=ASGITransport(app=app_override_session), base_url="http://test") as ac:
        for token in (owner_token, co_owner_token):
            res = await ac.post("/api/owner/broadcasts/drafts", headers={"Authorization": f"Bearer {token}"})
            assert res.status_code == 200
            draft_id = res.json()["id"]

            res = await ac.put(
                f"/api/owner/broadcasts/{draft_id}/content",
                json={"text": "Mini App broadcast"},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert res.status_code == 200
            assert res.json()["content_preview"] == "Mini App broadcast"

            res = await ac.put(
                f"/api/owner/broadcasts/{draft_id}/buttons",
                json={"selection": "none"},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert res.status_code == 200
            assert res.json()["status"] == "READY"

            res = await ac.get(
                f"/api/owner/broadcasts/{draft_id}/preview",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert res.status_code == 200
            assert res.json()["eligible_recipient_count"] == 2

            res = await ac.post(
                f"/api/owner/broadcasts/{draft_id}/send",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert res.status_code == 200
            assert res.json()["status"] == "SENDING"


@pytest.mark.anyio
async def test_manager_and_customer_cannot_create_broadcasts(
    app_override_session,
    settings: Settings,
    session,
) -> None:
    settings.manager_ids = [101]
    await _seed_user(session, 101)
    await _seed_user(session, 5001)

    manager_token = create_signed_session_token(101, "manager", settings.miniapp_session_secret, 3600)
    customer_token = create_signed_session_token(5001, "customer", settings.miniapp_session_secret, 3600)

    async with AsyncClient(transport=ASGITransport(app=app_override_session), base_url="http://test") as ac:
        for token in (manager_token, customer_token):
            res = await ac.post("/api/owner/broadcasts/drafts", headers={"Authorization": f"Bearer {token}"})
            assert res.status_code == 403


def test_production_rejects_mock_init_data(settings: Settings) -> None:
    init_data = (
        'user={"id":123,"first_name":"Mock"}&auth_date=1893456000&hash=mock_hash_role_owner'
    )

    assert validate_telegram_init_data(
        init_data=init_data,
        bot_token=settings.bot_token,
        max_age=3600,
        app_env="production",
    ) is None


def test_production_settings_require_strict_miniapp_secret_and_origin() -> None:
    with pytest.raises(ValueError, match="MINIAPP_SESSION_SECRET"):
        Settings(
            BOT_TOKEN="123:test",
            OPENROUTER_API_KEY="sk-test",
            APP_ENV="production",
            DATABASE_URL="sqlite+aiosqlite:///:memory:",
            OWNER_ID=999,
            MANAGER_IDS="101",
            DEFAULT_MODEL=DEFAULT_MODEL,
            MINIAPP_SESSION_SECRET="dev_secret_change_me_in_production",
            MINIAPP_ORIGIN="https://miniapp.example.com",
        )

    with pytest.raises(ValueError, match="MINIAPP_ORIGIN"):
        Settings(
            BOT_TOKEN="123:test",
            OPENROUTER_API_KEY="sk-test",
            APP_ENV="production",
            DATABASE_URL="sqlite+aiosqlite:///:memory:",
            OWNER_ID=999,
            MANAGER_IDS="101",
            DEFAULT_MODEL=DEFAULT_MODEL,
            MINIAPP_SESSION_SECRET="x" * 40,
            MINIAPP_ORIGIN="http://localhost:5173",
        )


def test_frontend_code_references_only_public_vite_environment_variables() -> None:
    frontend_root = Path(__file__).resolve().parents[1] / "miniapp" / "src"
    forbidden = {
        "BOT_TOKEN",
        "OPENROUTER_API_KEY",
        "DATABASE_URL",
        "OWNER_ID",
        "MANAGER_IDS",
        "MINIAPP_SESSION_SECRET",
    }

    offenders: list[str] = []
    for path in frontend_root.rglob("*"):
        if path.suffix not in {".ts", ".tsx"}:
            continue
        text = path.read_text(encoding="utf-8")
        for name in forbidden:
            if name in text:
                offenders.append(f"{path.relative_to(frontend_root)}:{name}")

    assert offenders == []
