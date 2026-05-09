"""add competition day dates

Revision ID: 20260509_0930
Revises: 20260509_0900
Create Date: 2026-05-09 09:30:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260509_0930"
down_revision = "20260509_0900"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("competitions", sa.Column("dia_1", sa.Date(), nullable=True))
    op.add_column("competitions", sa.Column("dia_2", sa.Date(), nullable=True))
    op.add_column("competitions", sa.Column("dia_3", sa.Date(), nullable=True))
    op.add_column("competitions", sa.Column("dia_4", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("competitions", "dia_4")
    op.drop_column("competitions", "dia_3")
    op.drop_column("competitions", "dia_2")
    op.drop_column("competitions", "dia_1")
