"""add checkin status

Revision ID: 20260508_1200
Revises: 20260508_1100
Create Date: 2026-05-08 12:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260508_1200"
down_revision: str | None = "20260508_1100"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "competition_checkins",
        sa.Column("status", sa.String(length=20), nullable=False, server_default="No checked"),
    )


def downgrade() -> None:
    op.drop_column("competition_checkins", "status")
