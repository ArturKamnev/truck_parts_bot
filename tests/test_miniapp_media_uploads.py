from __future__ import annotations

from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import create_signed_session_token, get_bot
from app.api.main import app
from app.config import Settings, get_settings
from app.db.models import Ticket, User
from app.db.session import get_session
from app.utils.enums import TicketStatus


@pytest.fixture
def app_override_session(session, settings: Settings, fake_bot, tmp_path):
    settings.miniapp_media_storage_dir = str(tmp_path)

    async def override_get_session():
        yield session

    async def override_get_bot():
        yield fake_bot

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_bot] = override_get_bot
    yield app
    app.dependency_overrides.clear()


def auth_headers(settings: Settings, telegram_id: int) -> dict[str, str]:
    token = create_signed_session_token(
        telegram_id,
        "customer",
        settings.miniapp_session_secret,
        3600,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.anyio
async def test_customer_can_upload_and_download_own_ticket_file(
    app_override_session,
    settings: Settings,
    session,
) -> None:
    now = datetime.now(UTC)
    customer = User(
        telegram_user_id=777001,
        username="cust",
        first_name="Cust",
        last_seen_at=now,
    )
    session.add(customer)
    await session.flush()
    ticket = Ticket(customer_id=customer.id, status=TicketStatus.OPEN.value)
    session.add(ticket)
    await session.commit()

    async with AsyncClient(
        transport=ASGITransport(app=app_override_session),
        base_url="http://test",
    ) as ac:
        response = await ac.post(
            f"/api/customer/tickets/{ticket.id}/messages/upload",
            headers=auth_headers(settings, customer.telegram_user_id),
            files={"file": ("note.txt", b"hello file", "text/plain")},
            data={"caption": "caption"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["hasMedia"] is True
        assert payload["fileName"] == "note.txt"
        assert payload["mimeType"] == "text/plain"
        assert payload["downloadUrl"]

        download = await ac.get(
            payload["downloadUrl"],
            headers=auth_headers(settings, customer.telegram_user_id),
        )
        assert download.status_code == 200
        assert download.content == b"hello file"


@pytest.mark.anyio
async def test_owner_broadcast_accepts_single_attachment(
    app_override_session,
    settings: Settings,
    session,
) -> None:
    owner = User(
        telegram_user_id=settings.owner_id,
        username="owner",
        first_name="Owner",
        last_seen_at=datetime.now(UTC),
    )
    session.add(owner)
    await session.commit()

    async with AsyncClient(
        transport=ASGITransport(app=app_override_session),
        base_url="http://test",
    ) as ac:
        headers = auth_headers(settings, settings.owner_id)
        draft = await ac.post("/api/owner/broadcasts/drafts", headers=headers)
        assert draft.status_code == 200

        response = await ac.post(
            f"/api/owner/broadcasts/{draft.json()['id']}/attachment",
            headers=headers,
            files={"file": ("promo.txt", b"promo", "text/plain")},
            data={"caption": "June promo"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["content_type"] == "document"
        assert payload["content_preview"] == "June promo"
        assert payload["file_name"] == "promo.txt"
