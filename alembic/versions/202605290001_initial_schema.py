"""initial schema

Revision ID: 202605290001
Revises:
Create Date: 2026-05-29
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "202605290001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("first_name", sa.String(length=255), nullable=True),
        sa.Column("last_name", sa.String(length=255), nullable=True),
        sa.Column("mode", sa.String(length=32), nullable=False, server_default="AI_CHAT"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_users_telegram_user_id", "users", ["telegram_user_id"], unique=True)
    op.create_index("ix_users_last_seen_at", "users", ["last_seen_at"])

    op.create_table(
        "tickets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "customer_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="OPEN"),
        sa.Column("assigned_manager_telegram_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_by_telegram_id", sa.BigInteger(), nullable=True),
    )
    op.create_index("ix_tickets_customer_id", "tickets", ["customer_id"])
    op.create_index("ix_tickets_status", "tickets", ["status"])
    op.create_index("ix_tickets_created_at", "tickets", ["created_at"])
    op.create_index(
        "uq_tickets_one_active_per_customer",
        "tickets",
        ["customer_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('OPEN', 'CLAIMED')"),
        sqlite_where=sa.text("status IN ('OPEN', 'CLAIMED')"),
    )

    op.create_table(
        "ai_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "customer_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("model_id", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_ai_messages_customer_created", "ai_messages", ["customer_id", "created_at"])

    op.create_table(
        "ticket_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "ticket_id",
            sa.Integer(),
            sa.ForeignKey("tickets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sender_type", sa.String(length=16), nullable=False),
        sa.Column("sender_telegram_id", sa.BigInteger(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_ticket_messages_ticket_created", "ticket_messages", ["ticket_id", "created_at"]
    )

    op.create_table(
        "operator_sessions",
        sa.Column("operator_telegram_id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "selected_ticket_id",
            sa.Integer(),
            sa.ForeignKey("tickets.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )

    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(length=128), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("updated_by_telegram_id", sa.BigInteger(), nullable=True),
    )
    op.create_index("ix_app_settings_key", "app_settings", ["key"], unique=True)

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("actor_telegram_id", sa.BigInteger(), nullable=True),
        sa.Column("customer_id", sa.Integer(), nullable=True),
        sa.Column("ticket_id", sa.Integer(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_audit_events_event_type", "audit_events", ["event_type"])
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"])


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("app_settings")
    op.drop_table("operator_sessions")
    op.drop_table("ticket_messages")
    op.drop_table("ai_messages")
    op.drop_index("uq_tickets_one_active_per_customer", table_name="tickets")
    op.drop_table("tickets")
    op.drop_table("users")
