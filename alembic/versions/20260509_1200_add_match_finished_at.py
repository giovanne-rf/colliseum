"""add match finished at

Revision ID: 20260509_1200
Revises: 20260509_1100
Create Date: 2026-05-09 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260509_1200"
down_revision: str | None = "20260509_1100"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("match_results", sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("match_results", "finished_at")
