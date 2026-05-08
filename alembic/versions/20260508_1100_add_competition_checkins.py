"""add competition checkins

Revision ID: 20260508_1100
Revises: 20260508_0900
Create Date: 2026-05-08 11:00:00.000000

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260508_1100"
down_revision = "20260508_0900"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "competition_checkins",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("competition_id", sa.Integer(), nullable=False),
        sa.Column("registration_id", sa.Integer(), nullable=False),
        sa.Column("athlete_id", sa.Integer(), nullable=False),
        sa.Column("checked_weight", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("gi", sa.Boolean(), nullable=False),
        sa.Column("overweight_confirmed", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["athlete_id"], ["athletes.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["competition_id"], ["competitions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["registration_id"],
            ["competition_registrations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("registration_id", name="uq_checkin_registration"),
    )
    op.create_index(op.f("ix_competition_checkins_athlete_id"), "competition_checkins", ["athlete_id"], unique=False)
    op.create_index(
        op.f("ix_competition_checkins_competition_id"),
        "competition_checkins",
        ["competition_id"],
        unique=False,
    )
    op.create_index(op.f("ix_competition_checkins_id"), "competition_checkins", ["id"], unique=False)
    op.create_index(
        op.f("ix_competition_checkins_registration_id"),
        "competition_checkins",
        ["registration_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_competition_checkins_registration_id"), table_name="competition_checkins")
    op.drop_index(op.f("ix_competition_checkins_id"), table_name="competition_checkins")
    op.drop_index(op.f("ix_competition_checkins_competition_id"), table_name="competition_checkins")
    op.drop_index(op.f("ix_competition_checkins_athlete_id"), table_name="competition_checkins")
    op.drop_table("competition_checkins")
