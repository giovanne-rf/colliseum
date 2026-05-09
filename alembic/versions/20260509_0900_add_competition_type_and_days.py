"""add competition type and days

Revision ID: 20260509_0900
Revises: 20260508_1300
Create Date: 2026-05-09 09:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260509_0900"
down_revision = "20260508_1300"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "competitions",
        sa.Column("competition_type", sa.String(length=20), nullable=False, server_default="Oficial"),
    )
    op.add_column(
        "competitions",
        sa.Column("competition_days", sa.Integer(), nullable=False, server_default="2"),
    )


def downgrade() -> None:
    op.drop_column("competitions", "competition_days")
    op.drop_column("competitions", "competition_type")
