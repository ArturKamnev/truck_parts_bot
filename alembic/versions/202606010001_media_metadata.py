"""add miniapp media metadata

Revision ID: 202606010001
Revises: 202605300001
Create Date: 2026-06-01 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "202606010001"
down_revision = "202605300001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ticket_messages", sa.Column("file_id", sa.String(length=255), nullable=True))
    op.add_column("ticket_messages", sa.Column("file_unique_id", sa.String(length=255), nullable=True))
    op.add_column("ticket_messages", sa.Column("file_name", sa.String(length=512), nullable=True))
    op.add_column("ticket_messages", sa.Column("mime_type", sa.String(length=255), nullable=True))
    op.add_column("ticket_messages", sa.Column("file_size", sa.Integer(), nullable=True))
    op.add_column("ticket_messages", sa.Column("file_path", sa.Text(), nullable=True))
    op.add_column("broadcasts", sa.Column("file_name", sa.String(length=512), nullable=True))
    op.add_column("broadcasts", sa.Column("mime_type", sa.String(length=255), nullable=True))
    op.add_column("broadcasts", sa.Column("file_size", sa.Integer(), nullable=True))
    op.add_column("broadcasts", sa.Column("file_path", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("broadcasts", "file_path")
    op.drop_column("broadcasts", "file_size")
    op.drop_column("broadcasts", "mime_type")
    op.drop_column("broadcasts", "file_name")
    op.drop_column("ticket_messages", "file_path")
    op.drop_column("ticket_messages", "file_size")
    op.drop_column("ticket_messages", "mime_type")
    op.drop_column("ticket_messages", "file_name")
    op.drop_column("ticket_messages", "file_unique_id")
    op.drop_column("ticket_messages", "file_id")
