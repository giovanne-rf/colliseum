"""relax team and athlete team requirements

Revision ID: 20260530_0100
Revises: 20260509_1200
Create Date: 2026-05-30 01:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260530_0100"
down_revision: str | None = "20260509_1200"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.alter_column(
            "athletes",
            "team_id",
            existing_type=sa.Integer(),
            nullable=True,
        )
        op.alter_column(
            "teams",
            "responsible",
            existing_type=sa.String(length=160),
            nullable=True,
        )
        return

    if dialect == "sqlite":
        return

    op.alter_column("athletes", "team_id", existing_type=sa.Integer(), nullable=True)
    op.alter_column("teams", "responsible", existing_type=sa.String(length=160), nullable=True)


def downgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.alter_column(
            "teams",
            "responsible",
            existing_type=sa.String(length=160),
            nullable=False,
        )
        op.alter_column(
            "athletes",
            "team_id",
            existing_type=sa.Integer(),
            nullable=False,
        )
        return

    if dialect == "sqlite":
        return

    op.alter_column("teams", "responsible", existing_type=sa.String(length=160), nullable=False)
    op.alter_column("athletes", "team_id", existing_type=sa.Integer(), nullable=False)
