"""ticket media metadata and manager preferences

Revision ID: 202605290002
Revises: 202605290001
Create Date: 2026-05-29
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "202605290002"
down_revision = "202605290001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ticket_messages",
        sa.Column("content_type", sa.String(length=32), nullable=False, server_default="text"),
    )
    op.add_column("ticket_messages", sa.Column("source_chat_id", sa.BigInteger(), nullable=True))
    op.add_column("ticket_messages", sa.Column("source_message_id", sa.Integer(), nullable=True))
    op.add_column("ticket_messages", sa.Column("text_preview", sa.Text(), nullable=True))
    op.add_column(
        "ticket_messages", sa.Column("media_group_id", sa.String(length=255), nullable=True)
    )
    op.add_column(
        "ticket_messages",
        sa.Column(
            "delivery_status", sa.String(length=32), nullable=False, server_default="stored"
        ),
    )
    op.execute("UPDATE ticket_messages SET text_preview = content WHERE text_preview IS NULL")

    op.create_table(
        "manager_preferences",
        sa.Column("manager_telegram_id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "new_ticket_notifications_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )


def downgrade() -> None:
    op.drop_table("manager_preferences")
    op.drop_column("ticket_messages", "delivery_status")
    op.drop_column("ticket_messages", "media_group_id")
    op.drop_column("ticket_messages", "text_preview")
    op.drop_column("ticket_messages", "source_message_id")
    op.drop_column("ticket_messages", "source_chat_id")
    op.drop_column("ticket_messages", "content_type")
