"""add ranking entries

Revision ID: 20260507_2100
Revises: 20260507_1200
Create Date: 2026-05-07 21:00:00.000000

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260507_2100"
down_revision = "20260507_1200"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ranking_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("athlete_id", sa.Integer(), nullable=False),
        sa.Column(
            "belt",
            sa.Enum("white", "blue", "purple", "brown", "black", name="belt_enum"),
            nullable=False,
        ),
        sa.Column("age_group", sa.String(length=80), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.Column("competition_name", sa.String(length=160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["athlete_id"], ["athletes.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ranking_entries_age_group"), "ranking_entries", ["age_group"], unique=False)
    op.create_index(op.f("ix_ranking_entries_athlete_id"), "ranking_entries", ["athlete_id"], unique=False)
    op.create_index(op.f("ix_ranking_entries_belt"), "ranking_entries", ["belt"], unique=False)
    op.create_index(
        op.f("ix_ranking_entries_competition_name"),
        "ranking_entries",
        ["competition_name"],
        unique=False,
    )
    op.create_index(op.f("ix_ranking_entries_id"), "ranking_entries", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_ranking_entries_id"), table_name="ranking_entries")
    op.drop_index(op.f("ix_ranking_entries_competition_name"), table_name="ranking_entries")
    op.drop_index(op.f("ix_ranking_entries_belt"), table_name="ranking_entries")
    op.drop_index(op.f("ix_ranking_entries_athlete_id"), table_name="ranking_entries")
    op.drop_index(op.f("ix_ranking_entries_age_group"), table_name="ranking_entries")
    op.drop_table("ranking_entries")
