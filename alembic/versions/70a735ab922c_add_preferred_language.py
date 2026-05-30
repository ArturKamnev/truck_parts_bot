"""add_preferred_language

Revision ID: 70a735ab922c
Revises: 49f843f9c6b8
Create Date: 2026-05-30 18:52:58.048900
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = '70a735ab922c'
down_revision = '49f843f9c6b8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("preferred_language", sa.String(length=10), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "preferred_language")

