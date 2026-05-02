from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260502_0835"
down_revision = None
branch_labels = None
depends_on = None


belt_enum = sa.Enum("white", "blue", "purple", "brown", "black", name="belt_enum")


def upgrade() -> None:
    belt_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("weight_class", sa.String(length=80), nullable=False),
        sa.Column("belt", belt_enum, nullable=False),
        sa.Column("age_group", sa.String(length=80), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("weight_class", "belt", "age_group", name="uq_category_identity"),
    )
    op.create_index("ix_categories_id", "categories", ["id"])
    op.create_index("ix_categories_weight_class", "categories", ["weight_class"])
    op.create_index("ix_categories_belt", "categories", ["belt"])
    op.create_index("ix_categories_age_group", "categories", ["age_group"])

    op.create_table(
        "teams",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("created_date", sa.Date(), nullable=False),
        sa.Column("responsible", sa.String(length=160), nullable=False),
        sa.Column("phone", sa.String(length=13), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_teams_id", "teams", ["id"])
    op.create_index("ix_teams_name", "teams", ["name"])
    op.create_index("ix_teams_created_date", "teams", ["created_date"])
    op.create_index("ix_teams_responsible", "teams", ["responsible"])

    op.create_table(
        "athletes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("cpf", sa.String(length=11), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("phone", sa.String(length=13), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("belt", belt_enum, nullable=False),
        sa.Column("graduation_date", sa.Date(), nullable=False),
        sa.Column("birth_date", sa.Date(), nullable=False),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cpf"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("name", "team_id", name="uq_athlete_name_team"),
    )
    op.create_index("ix_athletes_id", "athletes", ["id"])
    op.create_index("ix_athletes_name", "athletes", ["name"])
    op.create_index("ix_athletes_cpf", "athletes", ["cpf"])
    op.create_index("ix_athletes_email", "athletes", ["email"])
    op.create_index("ix_athletes_team_id", "athletes", ["team_id"])
    op.create_index("ix_athletes_belt", "athletes", ["belt"])
    op.create_index("ix_athletes_graduation_date", "athletes", ["graduation_date"])
    op.create_index("ix_athletes_birth_date", "athletes", ["birth_date"])


def downgrade() -> None:
    op.drop_index("ix_athletes_birth_date", table_name="athletes")
    op.drop_index("ix_athletes_graduation_date", table_name="athletes")
    op.drop_index("ix_athletes_belt", table_name="athletes")
    op.drop_index("ix_athletes_team_id", table_name="athletes")
    op.drop_index("ix_athletes_email", table_name="athletes")
    op.drop_index("ix_athletes_cpf", table_name="athletes")
    op.drop_index("ix_athletes_name", table_name="athletes")
    op.drop_index("ix_athletes_id", table_name="athletes")
    op.drop_table("athletes")

    op.drop_index("ix_teams_responsible", table_name="teams")
    op.drop_index("ix_teams_created_date", table_name="teams")
    op.drop_index("ix_teams_name", table_name="teams")
    op.drop_index("ix_teams_id", table_name="teams")
    op.drop_table("teams")

    op.drop_index("ix_categories_age_group", table_name="categories")
    op.drop_index("ix_categories_belt", table_name="categories")
    op.drop_index("ix_categories_weight_class", table_name="categories")
    op.drop_index("ix_categories_id", table_name="categories")
    op.drop_table("categories")

    belt_enum.drop(op.get_bind(), checkfirst=True)
