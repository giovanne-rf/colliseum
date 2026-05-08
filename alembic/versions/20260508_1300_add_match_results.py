"""add match results

Revision ID: 20260508_1300
Revises: 20260508_1200
Create Date: 2026-05-08 13:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260508_1300"
down_revision: str | None = "20260508_1200"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "match_results",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("match_id", sa.Integer(), nullable=False),
        sa.Column("athlete_a_points", sa.Integer(), nullable=False),
        sa.Column("athlete_a_advantages", sa.Integer(), nullable=False),
        sa.Column("athlete_a_penalties", sa.Integer(), nullable=False),
        sa.Column("athlete_b_points", sa.Integer(), nullable=False),
        sa.Column("athlete_b_advantages", sa.Integer(), nullable=False),
        sa.Column("athlete_b_penalties", sa.Integer(), nullable=False),
        sa.Column("winner_id", sa.Integer(), nullable=True),
        sa.Column("finish_method", sa.String(length=30), nullable=True),
        sa.Column("finalized", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["match_id"], ["matches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["winner_id"], ["athletes.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("match_id", name="uq_match_result_match"),
    )
    op.create_index(op.f("ix_match_results_id"), "match_results", ["id"], unique=False)
    op.create_index(op.f("ix_match_results_match_id"), "match_results", ["match_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_match_results_match_id"), table_name="match_results")
    op.drop_index(op.f("ix_match_results_id"), table_name="match_results")
    op.drop_table("match_results")
