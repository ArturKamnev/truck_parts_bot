from __future__ import annotations

from types import SimpleNamespace

import pytest
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from sqlalchemy import select

from app.db.models import BroadcastDelivery, TicketMessage
from app.services.broadcast_service import BroadcastService
from app.services.ticket_service import TicketService
from app.utils.enums import (
    BroadcastButtonSelection,
    BroadcastDeliveryStatus,
    BroadcastStatus,
    OwnerWorkflowState,
    TicketMessageContentType,
)


async def _user(session, ticket_service: TicketService, telegram_user_id: int):
    return await ticket_service.upsert_user_from_telegram(
        session,
        telegram_user_id=telegram_user_id,
        username=f"user{telegram_user_id}",
        first_name=f"User{telegram_user_id}",
        last_name=None,
    )


def _message(*, user_id: int = 999, message_id: int = 10, text=None, caption=None, **content):
    payload = {
        "message_id": message_id,
        "chat": SimpleNamespace(id=user_id),
        "text": text,
        "caption": caption,
        "media_group_id": None,
        "photo": None,
        "video": None,
        "document": None,
        "animation": None,
        "audio": None,
        "voice": None,
        "video_note": None,
    }
    payload.update(content)
    return SimpleNamespace(**payload)


async def test_only_owner_can_start_broadcast(
    session, broadcast_service: BroadcastService
) -> None:
    with pytest.raises(Exception, match="Недостаточно прав"):
        await broadcast_service.start_draft(session, owner_telegram_id=101)

    draft = await broadcast_service.start_draft(session, owner_telegram_id=999)
    assert draft.status == BroadcastStatus.DRAFT.value


async def test_capture_text_broadcast_draft(session, broadcast_service: BroadcastService) -> None:
    await broadcast_service.start_draft(session, owner_telegram_id=999)

    draft = await broadcast_service.capture_content(
        session,
        owner_telegram_id=999,
        message=_message(text="Hello customers"),
    )

    assert draft.content_type == TicketMessageContentType.TEXT.value
    assert draft.content_preview == "Hello customers"
    assert (
        await broadcast_service.active_owner_state(session, owner_telegram_id=999)
        == OwnerWorkflowState.CHOOSING_BROADCAST_BUTTONS.value
    )


@pytest.mark.parametrize(
    ("attr", "content_type"),
    [
        ("photo", TicketMessageContentType.PHOTO.value),
        ("video", TicketMessageContentType.VIDEO.value),
        ("document", TicketMessageContentType.DOCUMENT.value),
    ],
)
async def test_capture_media_with_caption_draft(
    session,
    broadcast_service: BroadcastService,
    attr: str,
    content_type: str,
) -> None:
    await broadcast_service.start_draft(session, owner_telegram_id=999)

    draft = await broadcast_service.capture_content(
        session,
        owner_telegram_id=999,
        message=_message(message_id=33, caption="Caption", **{attr: object()}),
    )

    assert draft.content_type == content_type
    assert draft.content_preview == "Caption"
    assert draft.source_message_id == 33


def test_configured_button_selection_and_missing_url_behavior(
    settings, authorization, relay_service
):
    settings.instagram_url = "https://instagram.example/company"
    settings.official_site_url = None
    service = BroadcastService(settings, authorization, relay_service)

    assert service.is_button_selection_available(BroadcastButtonSelection.INSTAGRAM)
    assert not service.is_button_selection_available(BroadcastButtonSelection.SITE)
    assert not service.is_button_selection_available(BroadcastButtonSelection.BOTH)


async def test_preview_and_test_send_flow(session, broadcast_service: BroadcastService, fake_bot):
    await broadcast_service.start_draft(session, owner_telegram_id=999)
    draft = await broadcast_service.capture_content(
        session, owner_telegram_id=999, message=_message(text="Preview")
    )
    draft = await broadcast_service.set_buttons(
        session,
        owner_telegram_id=999,
        broadcast_id=draft.id,
        selection=BroadcastButtonSelection.NONE,
    )

    await broadcast_service.send_test(fake_bot, session, broadcast=draft)

    assert fake_bot.copied_messages[-1]["chat_id"] == 999
    assert draft.status == BroadcastStatus.READY.value


async def test_final_confirmation_required_before_mass_sending(
    session, broadcast_service: BroadcastService
) -> None:
    await broadcast_service.start_draft(session, owner_telegram_id=999)
    draft = await broadcast_service.capture_content(
        session, owner_telegram_id=999, message=_message(text="Ready")
    )
    await broadcast_service.set_buttons(
        session,
        owner_telegram_id=999,
        broadcast_id=draft.id,
        selection=BroadcastButtonSelection.NONE,
    )

    broadcast, recipients = await broadcast_service.request_final_confirmation(
        session, owner_telegram_id=999, broadcast_id=draft.id
    )

    assert broadcast.status == BroadcastStatus.READY.value
    assert recipients == 0
    assert (
        await broadcast_service.active_owner_state(session, owner_telegram_id=999)
        == OwnerWorkflowState.CONFIRMING_BROADCAST.value
    )


async def test_opted_out_customers_and_staff_excluded_from_recipients(
    settings,
    session,
    ticket_service: TicketService,
    broadcast_service: BroadcastService,
) -> None:
    await _user(session, ticket_service, 500)
    opted_out = await _user(session, ticket_service, 501)
    opted_out.broadcasts_enabled = False
    await _user(session, ticket_service, settings.owner_id)
    await _user(session, ticket_service, settings.manager_ids[0])

    recipients = await broadcast_service.eligible_recipients(session)

    assert [user.telegram_user_id for user in recipients] == [500]


async def test_blocked_recipient_tracking(
    session, ticket_service: TicketService, broadcast_service: BroadcastService, fake_bot
) -> None:
    customer = await _user(session, ticket_service, 500)
    await broadcast_service.start_draft(session, owner_telegram_id=999)
    broadcast = await broadcast_service.capture_content(
        session, owner_telegram_id=999, message=_message(text="Blocked")
    )
    delivery = BroadcastDelivery(broadcast_id=broadcast.id, user_id=customer.id)
    session.add(delivery)
    await session.flush()
    fake_bot.copy_failures[500] = TelegramForbiddenError(method=None, message="blocked")

    await broadcast_service._attempt_delivery(fake_bot, session, broadcast, delivery)

    assert delivery.status == BroadcastDeliveryStatus.BLOCKED.value
    assert customer.is_unavailable


async def test_rate_limit_retry_behavior(session, ticket_service, broadcast_service):
    class RetryOnceBot:
        def __init__(self):
            self.calls = 0
            self.copied_messages = []

        async def copy_message(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise TelegramRetryAfter(method=None, message="retry", retry_after=0)
            self.copied_messages.append(kwargs)

    customer = await _user(session, ticket_service, 500)
    await broadcast_service.start_draft(session, owner_telegram_id=999)
    broadcast = await broadcast_service.capture_content(
        session, owner_telegram_id=999, message=_message(text="Retry")
    )
    delivery = BroadcastDelivery(broadcast_id=broadcast.id, user_id=customer.id)
    session.add(delivery)
    await session.flush()
    bot = RetryOnceBot()

    await broadcast_service._attempt_delivery(bot, session, broadcast, delivery)

    assert bot.calls == 2
    assert delivery.status == BroadcastDeliveryStatus.DELIVERED.value


async def test_broadcast_mode_does_not_create_ticket_message(
    session,
    broadcast_service: BroadcastService,
    ticket_service: TicketService,
    relay_service,
) -> None:
    customer = await _user(session, ticket_service, 500)
    ticket = await ticket_service.create_ticket(
        session, customer=customer, original_request="Need support"
    )
    await ticket_service.claim_ticket(session, ticket_id=ticket.id, manager_telegram_id=101)
    await broadcast_service.start_draft(session, owner_telegram_id=999)
    await broadcast_service.capture_content(
        session, owner_telegram_id=999, message=_message(text="Broadcast draft")
    )

    messages = list(await session.scalars(select(TicketMessage)))

    assert all(message.content != "Broadcast draft" for message in messages)
