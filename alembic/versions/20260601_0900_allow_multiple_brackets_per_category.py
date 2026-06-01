"""allow multiple brackets per category

Revision ID: 20260601_0900
Revises: 20260530_0100
Create Date: 2026-06-01 09:00:00.000000
"""

from collections.abc import Sequence

from alembic import op


revision: str = "20260601_0900"
down_revision: str | None = "20260530_0100"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.drop_constraint("uq_bracket_competition_category", "brackets", type_="unique")
        return

    if dialect == "sqlite":
        with op.batch_alter_table("brackets") as batch_op:
            batch_op.drop_constraint("uq_bracket_competition_category", type_="unique")
        return

    op.drop_constraint("uq_bracket_competition_category", "brackets", type_="unique")


def downgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.create_unique_constraint(
            "uq_bracket_competition_category",
            "brackets",
            ["competition_id", "category_id"],
        )
        return

    if dialect == "sqlite":
        with op.batch_alter_table("brackets") as batch_op:
            batch_op.create_unique_constraint(
                "uq_bracket_competition_category",
                ["competition_id", "category_id"],
            )
        return

    op.create_unique_constraint(
        "uq_bracket_competition_category",
        "brackets",
        ["competition_id", "category_id"],
    )
