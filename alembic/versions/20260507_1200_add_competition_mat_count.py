from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260507_1200"
down_revision = "20260502_0835"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "competitions",
        sa.Column("mat_count", sa.Integer(), nullable=False, server_default="4"),
    )


def downgrade() -> None:
    op.drop_column("competitions", "mat_count")
