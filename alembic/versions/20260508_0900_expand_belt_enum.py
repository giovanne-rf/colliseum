"""expand belt enum

Revision ID: 20260508_0900
Revises: 20260507_2100
Create Date: 2026-05-08 09:00:00.000000

"""

from __future__ import annotations

from alembic import op


revision = "20260508_0900"
down_revision = "20260507_2100"
branch_labels = None
depends_on = None


NEW_BELTS = (
    "gray",
    "gray_white",
    "gray_black",
    "yellow",
    "yellow_white",
    "yellow_black",
    "orange",
    "orange_white",
    "orange_black",
    "green",
    "green_white",
    "green_black",
    "red_black",
    "red_white",
    "red",
)


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return

    for belt in NEW_BELTS:
        op.execute(f"ALTER TYPE belt_enum ADD VALUE IF NOT EXISTS '{belt}'")


def downgrade() -> None:
    pass
