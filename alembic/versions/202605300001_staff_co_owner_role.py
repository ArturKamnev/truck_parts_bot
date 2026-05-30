"""staff_co_owner_role

Revision ID: 202605300001
Revises: 70a735ab922c
Create Date: 2026-05-30 19:30:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "202605300001"
down_revision = "70a735ab922c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    staff_members = sa.table(
        "staff_members",
        sa.column("role", sa.String(length=32)),
        sa.column("status", sa.String(length=32)),
    )
    op.execute(
        staff_members.update()
        .where(staff_members.c.role.is_(None))
        .values(role="manager")
    )
    op.execute(
        staff_members.update()
        .where(staff_members.c.status.is_(None))
        .values(status="active")
    )


def downgrade() -> None:
    staff_members = sa.table(
        "staff_members",
        sa.column("role", sa.String(length=32)),
    )
    op.execute(
        staff_members.update()
        .where(staff_members.c.role == "co_owner")
        .values(role="manager")
    )
