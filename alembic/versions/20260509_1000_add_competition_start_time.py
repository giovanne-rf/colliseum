"""add competition start time

Revision ID: 20260509_1000
Revises: 20260509_0930
Create Date: 2026-05-09 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260509_1000"
down_revision: str | None = "20260509_0930"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "competitions",
        sa.Column("start_time", sa.String(length=5), nullable=False, server_default="09:00"),
    )


def downgrade() -> None:
    op.drop_column("competitions", "start_time")
