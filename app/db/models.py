from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.utils.enums import BroadcastStatus, CustomerMode, TicketStatus


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, index=True, nullable=False
    )
    username: Mapped[str | None] = mapped_column(String(255))
    first_name: Mapped[str | None] = mapped_column(String(255))
    last_name: Mapped[str | None] = mapped_column(String(255))
    mode: Mapped[str] = mapped_column(
        String(32), default=CustomerMode.AI_CHAT.value, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    broadcasts_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("1")
    )
    is_unavailable: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("0")
    )

    tickets: Mapped[list[Ticket]] = relationship(back_populates="customer")
    ai_messages: Mapped[list[AIMessage]] = relationship(back_populates="customer")


class Ticket(Base):
    __tablename__ = "tickets"
    __table_args__ = (
        Index("ix_tickets_customer_id", "customer_id"),
        Index("ix_tickets_status", "status"),
        Index("ix_tickets_created_at", "created_at"),
        Index(
            "uq_tickets_one_active_per_customer",
            "customer_id",
            unique=True,
            postgresql_where=text("status IN ('OPEN', 'CLAIMED')"),
            sqlite_where=text("status IN ('OPEN', 'CLAIMED')"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), default=TicketStatus.OPEN.value, nullable=False)
    assigned_manager_telegram_id: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_by_telegram_id: Mapped[int | None] = mapped_column(BigInteger)

    customer: Mapped[User] = relationship(back_populates="tickets")
    messages: Mapped[list[TicketMessage]] = relationship(back_populates="ticket")


class AIMessage(Base):
    __tablename__ = "ai_messages"
    __table_args__ = (Index("ix_ai_messages_customer_created", "customer_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    model_id: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    customer: Mapped[User] = relationship(back_populates="ai_messages")


class TicketMessage(Base):
    __tablename__ = "ticket_messages"
    __table_args__ = (Index("ix_ticket_messages_ticket_created", "ticket_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False
    )
    sender_type: Mapped[str] = mapped_column(String(16), nullable=False)
    sender_telegram_id: Mapped[int | None] = mapped_column(BigInteger)
    content_type: Mapped[str] = mapped_column(String(32), nullable=False, default="text")
    source_chat_id: Mapped[int | None] = mapped_column(BigInteger)
    source_message_id: Mapped[int | None] = mapped_column(Integer)
    text_preview: Mapped[str | None] = mapped_column(Text)
    media_group_id: Mapped[str | None] = mapped_column(String(255))
    delivery_status: Mapped[str] = mapped_column(String(32), nullable=False, default="stored")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    ticket: Mapped[Ticket] = relationship(back_populates="messages")


class OperatorSession(Base):
    __tablename__ = "operator_sessions"

    operator_telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    selected_ticket_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("tickets.id", ondelete="SET NULL"), nullable=True
    )
    workflow_state: Mapped[str | None] = mapped_column(String(64))
    active_broadcast_id: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    selected_ticket: Mapped[Ticket | None] = relationship()


class Broadcast(Base):
    __tablename__ = "broadcasts"
    __table_args__ = (
        Index("ix_broadcasts_status", "status"),
        Index("ix_broadcasts_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_by_telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default=BroadcastStatus.DRAFT.value, nullable=False
    )
    source_chat_id: Mapped[int | None] = mapped_column(BigInteger)
    source_message_id: Mapped[int | None] = mapped_column(Integer)
    media_group_id: Mapped[str | None] = mapped_column(String(255))
    media_group_message_ids: Mapped[list[int] | None] = mapped_column(JSON)
    content_type: Mapped[str | None] = mapped_column(String(32))
    content_preview: Mapped[str | None] = mapped_column(Text)
    button_selection: Mapped[str] = mapped_column(String(32), nullable=False, default="none")
    recipient_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    delivered_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    blocked_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    deliveries: Mapped[list[BroadcastDelivery]] = relationship(back_populates="broadcast")


class BroadcastDelivery(Base):
    __tablename__ = "broadcast_deliveries"
    __table_args__ = (
        Index("ix_broadcast_deliveries_broadcast_status", "broadcast_id", "status"),
        Index("ix_broadcast_deliveries_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    broadcast_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("broadcasts.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    error_code: Mapped[str | None] = mapped_column(String(255))
    attempted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    broadcast: Mapped[Broadcast] = relationship(back_populates="deliveries")
    user: Mapped[User] = relationship()


class ManagerPreference(Base):
    __tablename__ = "manager_preferences"

    manager_telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    new_ticket_notifications_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("1")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True, unique=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    updated_by_telegram_id: Mapped[int | None] = mapped_column(BigInteger)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_event_type", "event_type"),
        Index("ix_audit_events_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    actor_telegram_id: Mapped[int | None] = mapped_column(BigInteger)
    customer_id: Mapped[int | None] = mapped_column(Integer)
    ticket_id: Mapped[int | None] = mapped_column(Integer)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict, server_default=text("'{}'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
