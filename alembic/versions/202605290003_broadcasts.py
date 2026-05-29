"""broadcasts

Revision ID: 202605290003
Revises: 202605290002
Create Date: 2026-05-29
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "202605290003"
down_revision = "202605290002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("broadcasts_enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
    )
    op.add_column(
        "users",
        sa.Column("is_unavailable", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column("operator_sessions", sa.Column("workflow_state", sa.String(length=64)))
    op.add_column("operator_sessions", sa.Column("active_broadcast_id", sa.Integer()))

    op.create_table(
        "broadcasts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_by_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="DRAFT"),
        sa.Column("source_chat_id", sa.BigInteger(), nullable=True),
        sa.Column("source_message_id", sa.Integer(), nullable=True),
        sa.Column("media_group_id", sa.String(length=255), nullable=True),
        sa.Column("media_group_message_ids", sa.JSON(), nullable=True),
        sa.Column("content_type", sa.String(length=32), nullable=True),
        sa.Column("content_preview", sa.Text(), nullable=True),
        sa.Column("button_selection", sa.String(length=32), nullable=False, server_default="none"),
        sa.Column("recipient_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("delivered_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("blocked_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_broadcasts_status", "broadcasts", ["status"])
    op.create_index("ix_broadcasts_created_at", "broadcasts", ["created_at"])

    op.create_table(
        "broadcast_deliveries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "broadcast_id",
            sa.Integer(),
            sa.ForeignKey("broadcasts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="PENDING"),
        sa.Column("error_code", sa.String(length=255), nullable=True),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_broadcast_deliveries_broadcast_status",
        "broadcast_deliveries",
        ["broadcast_id", "status"],
    )
    op.create_index("ix_broadcast_deliveries_user_id", "broadcast_deliveries", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_broadcast_deliveries_user_id", table_name="broadcast_deliveries")
    op.drop_index(
        "ix_broadcast_deliveries_broadcast_status", table_name="broadcast_deliveries"
    )
    op.drop_table("broadcast_deliveries")
    op.drop_index("ix_broadcasts_created_at", table_name="broadcasts")
    op.drop_index("ix_broadcasts_status", table_name="broadcasts")
    op.drop_table("broadcasts")
    op.drop_column("operator_sessions", "active_broadcast_id")
    op.drop_column("operator_sessions", "workflow_state")
    op.drop_column("users", "is_unavailable")
    op.drop_column("users", "broadcasts_enabled")
