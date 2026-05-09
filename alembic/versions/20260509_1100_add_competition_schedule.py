"""add competition schedule

Revision ID: 20260509_1100
Revises: 20260509_1000
Create Date: 2026-05-09 11:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260509_1100"
down_revision: str | None = "20260509_1000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "competition_schedule",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("competition_id", sa.Integer(), nullable=False),
        sa.Column("bracket_id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("match_id", sa.Integer(), nullable=False),
        sa.Column("mat_number", sa.Integer(), nullable=False),
        sa.Column("day_number", sa.Integer(), nullable=False),
        sa.Column("scheduled_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("estimated_minutes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["bracket_id"], ["brackets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["competition_id"], ["competitions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["match_id"], ["matches.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("match_id", name="uq_competition_schedule_match"),
    )
    op.create_index(op.f("ix_competition_schedule_id"), "competition_schedule", ["id"])
    op.create_index(op.f("ix_competition_schedule_competition_id"), "competition_schedule", ["competition_id"])
    op.create_index(op.f("ix_competition_schedule_bracket_id"), "competition_schedule", ["bracket_id"])
    op.create_index(op.f("ix_competition_schedule_category_id"), "competition_schedule", ["category_id"])
    op.create_index(op.f("ix_competition_schedule_match_id"), "competition_schedule", ["match_id"])
    op.create_index(op.f("ix_competition_schedule_mat_number"), "competition_schedule", ["mat_number"])
    op.create_index(op.f("ix_competition_schedule_day_number"), "competition_schedule", ["day_number"])
    op.create_index(op.f("ix_competition_schedule_scheduled_start"), "competition_schedule", ["scheduled_start"])


def downgrade() -> None:
    op.drop_index(op.f("ix_competition_schedule_scheduled_start"), table_name="competition_schedule")
    op.drop_index(op.f("ix_competition_schedule_day_number"), table_name="competition_schedule")
    op.drop_index(op.f("ix_competition_schedule_mat_number"), table_name="competition_schedule")
    op.drop_index(op.f("ix_competition_schedule_match_id"), table_name="competition_schedule")
    op.drop_index(op.f("ix_competition_schedule_category_id"), table_name="competition_schedule")
    op.drop_index(op.f("ix_competition_schedule_bracket_id"), table_name="competition_schedule")
    op.drop_index(op.f("ix_competition_schedule_competition_id"), table_name="competition_schedule")
    op.drop_index(op.f("ix_competition_schedule_id"), table_name="competition_schedule")
    op.drop_table("competition_schedule")
