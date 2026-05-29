from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy import inspect, select

from app.db.models import OperatorSession, Ticket, TicketMessage
from app.services.authorization_service import AuthorizationService
from app.services.relay_service import RelayService
from app.services.ticket_service import TicketService
from app.utils.enums import (
    CustomerMode,
    TicketMessageContentType,
    TicketMessageSenderType,
    TicketStatus,
)
from app.utils.exceptions import AuthorizationError, DuplicateActiveTicketError, TicketStateError


async def _customer(session, ticket_service: TicketService, telegram_user_id: int = 500):
    return await ticket_service.upsert_customer_from_telegram(
        session,
        telegram_user_id=telegram_user_id,
        username="customer",
        first_name="Test",
        last_name="Customer",
    )


def _fake_message(*, message_id: int = 10, text=None, caption=None, **content):
    payload = {
        "message_id": message_id,
        "chat": SimpleNamespace(id=500),
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


async def test_sqlite_database_initialization(session) -> None:
    table_names = await session.run_sync(
        lambda sync_session: inspect(sync_session.bind).get_table_names(),
    )

    assert "users" in table_names
    assert "tickets" in table_names
    assert "operator_sessions" in table_names


async def test_customer_begins_manager_request_without_empty_ticket(
    session, ticket_service: TicketService
) -> None:
    customer = await _customer(session, ticket_service)
    await ticket_service.begin_manager_request(session, customer=customer)

    assert customer.mode == CustomerMode.REQUESTING_MANAGER.value
    assert list(await session.scalars(select(Ticket))) == []


async def test_first_customer_text_creates_manager_ticket(
    session, ticket_service: TicketService
) -> None:
    customer = await _customer(session, ticket_service)
    await ticket_service.begin_manager_request(session, customer=customer)
    ticket = await ticket_service.create_ticket(
        session,
        customer=customer,
        original_request="Need a manager",
    )

    assert ticket.status == TicketStatus.OPEN.value
    assert customer.mode == CustomerMode.WAITING_MANAGER.value
    messages = await ticket_service.get_recent_ticket_messages(session, ticket_id=ticket.id)
    assert messages[-1].content == "Need a manager"


@pytest.mark.parametrize(
    ("attr", "content_type"),
    [
        ("photo", TicketMessageContentType.PHOTO.value),
        ("video", TicketMessageContentType.VIDEO.value),
        ("document", TicketMessageContentType.DOCUMENT.value),
    ],
)
async def test_first_customer_media_creates_ticket_with_metadata(
    session,
    ticket_service: TicketService,
    relay_service: RelayService,
    attr: str,
    content_type: str,
) -> None:
    customer = await _customer(session, ticket_service)
    await ticket_service.begin_manager_request(session, customer=customer)
    message = _fake_message(caption="media question", **{attr: object()})
    metadata = relay_service.metadata_from_message(message)

    ticket = await ticket_service.create_ticket(
        session,
        customer=customer,
        original_request=metadata.text_preview,
        content_type=metadata.content_type,
        source_chat_id=metadata.source_chat_id,
        source_message_id=metadata.source_message_id,
    )

    messages = await ticket_service.get_recent_ticket_messages(session, ticket_id=ticket.id)
    assert messages[-1].content_type == content_type
    assert messages[-1].source_message_id == 10


async def test_duplicate_active_ticket_prevention(session, ticket_service: TicketService) -> None:
    customer = await _customer(session, ticket_service)
    await ticket_service.create_ticket(
        session,
        customer=customer,
        original_request="Need a manager",
    )

    with pytest.raises(DuplicateActiveTicketError):
        await ticket_service.create_ticket(
            session,
            customer=customer,
            original_request="Second active ticket",
        )


def test_manager_queue_access_only_for_approved_managers(
    authorization: AuthorizationService,
) -> None:
    assert authorization.can_use_support_tools(101)
    assert authorization.can_use_support_tools(999)
    assert not authorization.can_use_support_tools(555)


async def test_one_manager_claims_open_ticket(session, ticket_service: TicketService) -> None:
    customer = await _customer(session, ticket_service)
    ticket = await ticket_service.create_ticket(
        session,
        customer=customer,
        original_request="Need a manager",
    )
    claimed = await ticket_service.claim_ticket(
        session,
        ticket_id=ticket.id,
        manager_telegram_id=101,
    )

    assert claimed.status == TicketStatus.CLAIMED.value
    assert claimed.assigned_manager_telegram_id == 101
    assert claimed.claimed_at is not None
    assert claimed.customer.mode == CustomerMode.MANAGER_CHAT.value
    operator_session = await session.get(OperatorSession, 101)
    assert operator_session.selected_ticket_id == ticket.id


async def test_another_manager_cannot_claim_already_claimed_ticket(settings, session) -> None:
    settings.manager_ids.append(102)
    authorization = AuthorizationService(settings)
    ticket_service = TicketService(authorization)
    customer = await _customer(session, ticket_service)
    ticket = await ticket_service.create_ticket(
        session,
        customer=customer,
        original_request="Need a manager",
    )
    await ticket_service.claim_ticket(session, ticket_id=ticket.id, manager_telegram_id=101)

    with pytest.raises(TicketStateError, match="другой менеджер"):
        await ticket_service.claim_ticket(session, ticket_id=ticket.id, manager_telegram_id=102)


async def test_only_assigned_manager_or_owner_can_reply(
    session, ticket_service: TicketService
) -> None:
    customer = await _customer(session, ticket_service)
    ticket = await ticket_service.create_ticket(
        session,
        customer=customer,
        original_request="Need a manager",
    )
    assert not ticket_service.can_send_manager_reply(ticket, 101)

    await ticket_service.claim_ticket(session, ticket_id=ticket.id, manager_telegram_id=101)
    assert ticket_service.can_send_manager_reply(ticket, 101)
    assert ticket_service.can_send_manager_reply(ticket, 999)
    assert not ticket_service.can_send_manager_reply(ticket, 555)


async def test_customer_messages_route_to_assigned_manager_not_ai(
    session, ticket_service: TicketService, relay_service: RelayService, fake_bot
) -> None:
    customer = await _customer(session, ticket_service)
    ticket = await ticket_service.create_ticket(
        session,
        customer=customer,
        original_request="Need a manager",
    )
    await ticket_service.claim_ticket(session, ticket_id=ticket.id, manager_telegram_id=101)

    delivered = await relay_service.relay_customer_message(
        fake_bot,
        session,
        ticket=ticket,
        customer=customer,
        text="Customer follow-up",
    )

    assert delivered
    assert fake_bot.sent_messages[-1]["chat_id"] == 101
    assert "Customer follow-up" in fake_bot.sent_messages[-1]["text"]


async def test_waiting_customer_messages_are_stored_but_not_sent(
    session, ticket_service: TicketService, relay_service: RelayService, fake_bot
) -> None:
    customer = await _customer(session, ticket_service)
    ticket = await ticket_service.create_ticket(
        session,
        customer=customer,
        original_request="Need a manager",
    )

    delivered = await relay_service.relay_customer_message(
        fake_bot,
        session,
        ticket=ticket,
        customer=customer,
        text="More detail while waiting",
    )

    assert not delivered
    assert fake_bot.sent_messages == []
    messages = await ticket_service.get_recent_ticket_messages(session, ticket_id=ticket.id)
    assert messages[-1].content == "More detail while waiting"


async def test_waiting_customer_additional_media_is_stored(
    session, ticket_service: TicketService, relay_service: RelayService, fake_bot
) -> None:
    customer = await _customer(session, ticket_service)
    ticket = await ticket_service.create_ticket(
        session,
        customer=customer,
        original_request="Need a manager",
    )
    message = _fake_message(message_id=22, caption="extra file", document=object())

    delivered = await relay_service.relay_customer_message(
        fake_bot,
        session,
        ticket=ticket,
        customer=customer,
        message=message,
    )

    assert not delivered
    messages = await ticket_service.get_recent_ticket_messages(session, ticket_id=ticket.id)
    assert messages[-1].content_type == TicketMessageContentType.DOCUMENT.value
    assert messages[-1].source_message_id == 22


async def test_manager_replies_route_to_customer(
    session, ticket_service: TicketService, relay_service: RelayService, fake_bot
) -> None:
    customer = await _customer(session, ticket_service)
    ticket = await ticket_service.create_ticket(
        session,
        customer=customer,
        original_request="Need a manager",
    )
    await ticket_service.claim_ticket(session, ticket_id=ticket.id, manager_telegram_id=101)

    await relay_service.relay_manager_message_to_customer(
        fake_bot,
        session,
        ticket=ticket,
        actor_telegram_id=101,
        text="Manager answer",
    )

    assert fake_bot.sent_messages[-1]["chat_id"] == customer.telegram_user_id
    assert fake_bot.sent_messages[-1]["text"] == "Manager answer"


async def test_manager_media_routes_to_correct_customer(
    session, ticket_service: TicketService, relay_service: RelayService, fake_bot
) -> None:
    customer = await _customer(session, ticket_service)
    ticket = await ticket_service.create_ticket(
        session,
        customer=customer,
        original_request="Need a manager",
    )
    await ticket_service.claim_ticket(session, ticket_id=ticket.id, manager_telegram_id=101)
    message = _fake_message(message_id=33, caption="signed doc", document=object())

    await relay_service.relay_manager_message_to_customer(
        fake_bot,
        session,
        ticket=ticket,
        actor_telegram_id=101,
        message=message,
    )

    assert fake_bot.copied_messages[-1]["chat_id"] == customer.telegram_user_id
    assert fake_bot.copied_messages[-1]["message_id"] == 33


async def test_manager_selected_ticket_reply_mode_is_persistent_and_safe(
    session, ticket_service: TicketService
) -> None:
    customer = await _customer(session, ticket_service)
    ticket = await ticket_service.create_ticket(
        session,
        customer=customer,
        original_request="Need a manager",
    )
    await ticket_service.claim_ticket(session, ticket_id=ticket.id, manager_telegram_id=101)

    selected = await ticket_service.get_selected_ticket(session, operator_telegram_id=101)
    assert selected.id == ticket.id
    await ticket_service.clear_selected_ticket(session, operator_telegram_id=101)
    assert await ticket_service.get_selected_ticket(session, operator_telegram_id=101) is None


async def test_manager_notification_preference_defaults_enabled_and_persists(
    session, ticket_service: TicketService
) -> None:
    assert await ticket_service.get_manager_notifications_enabled(
        session, manager_telegram_id=101
    )

    await ticket_service.set_manager_notifications_enabled(
        session, manager_telegram_id=101, enabled=False
    )

    assert not await ticket_service.get_manager_notifications_enabled(
        session, manager_telegram_id=101
    )


async def test_customer_cancel_flow(session, ticket_service: TicketService) -> None:
    customer = await _customer(session, ticket_service)
    ticket = await ticket_service.create_ticket(
        session,
        customer=customer,
        original_request="Need a manager",
    )
    await ticket_service.claim_ticket(session, ticket_id=ticket.id, manager_telegram_id=101)

    cancelled = await ticket_service.cancel_by_customer(
        session, customer=customer, actor_telegram_id=customer.telegram_user_id
    )

    assert cancelled.status == TicketStatus.CANCELLED_BY_CUSTOMER.value
    assert customer.mode == CustomerMode.AI_CHAT.value
    assert (await session.get(OperatorSession, 101)).selected_ticket_id is None


async def test_manager_close_flow(session, ticket_service: TicketService) -> None:
    customer = await _customer(session, ticket_service)
    ticket = await ticket_service.create_ticket(
        session,
        customer=customer,
        original_request="Need a manager",
    )
    await ticket_service.claim_ticket(session, ticket_id=ticket.id, manager_telegram_id=101)
    closed = await ticket_service.close_ticket(
        session,
        ticket_id=ticket.id,
        actor_telegram_id=101,
    )

    assert closed.status == TicketStatus.CLOSED.value
    assert closed.closed_by_telegram_id == 101
    assert closed.customer.mode == CustomerMode.AI_CHAT.value
    assert (await session.get(OperatorSession, 101)).selected_ticket_id is None


async def test_unassigned_manager_cannot_close_claimed_ticket(settings, session) -> None:
    settings.manager_ids.append(102)
    authorization = AuthorizationService(settings)
    ticket_service = TicketService(authorization)
    customer = await _customer(session, ticket_service)
    ticket = await ticket_service.create_ticket(
        session,
        customer=customer,
        original_request="Need a manager",
    )
    await ticket_service.claim_ticket(session, ticket_id=ticket.id, manager_telegram_id=101)

    with pytest.raises(AuthorizationError):
        await ticket_service.close_ticket(session, ticket_id=ticket.id, actor_telegram_id=102)


async def test_owner_supervisor_can_select_open_ticket_and_reply(
    session, ticket_service: TicketService, relay_service: RelayService, fake_bot
) -> None:
    customer = await _customer(session, ticket_service)
    ticket = await ticket_service.create_ticket(
        session,
        customer=customer,
        original_request="Need a manager",
    )
    await ticket_service.select_ticket(session, operator_telegram_id=999, ticket=ticket)

    await relay_service.relay_manager_message_to_customer(
        fake_bot,
        session,
        ticket=ticket,
        actor_telegram_id=999,
        text="Supervisor answer",
    )

    assert fake_bot.sent_messages[-1]["chat_id"] == customer.telegram_user_id
    assert fake_bot.sent_messages[-1]["text"] == "Supervisor answer"


async def test_ticket_messages_store_customer_and_manager_messages(
    session, ticket_service: TicketService
) -> None:
    customer = await _customer(session, ticket_service)
    ticket = await ticket_service.create_ticket(
        session,
        customer=customer,
        original_request="Need a manager",
    )
    ticket_service.add_ticket_message(
        session,
        ticket=ticket,
        sender_type=TicketMessageSenderType.MANAGER,
        sender_telegram_id=101,
        content="Manual message",
    )
    await session.flush()

    messages = list(await session.scalars(select(TicketMessage)))
    assert len(messages) == 2
