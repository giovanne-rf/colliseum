from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.database.base import Base

engine = create_async_engine(settings.database_url, echo=settings.sql_echo, future=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def create_db_and_tables() -> None:
    from app.models import athlete, bracket, category, ranking, team  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        competition_columns = await conn.run_sync(
            lambda sync_conn: {
                column["name"] for column in inspect(sync_conn).get_columns("competitions")
            }
        )
        if "mat_count" not in competition_columns:
            await conn.execute(
                text("ALTER TABLE competitions ADD COLUMN mat_count INTEGER NOT NULL DEFAULT 4")
            )
        if "start_time" not in competition_columns:
            await conn.execute(
                text("ALTER TABLE competitions ADD COLUMN start_time VARCHAR(5) NOT NULL DEFAULT '09:00'")
            )
        if "competition_type" not in competition_columns:
            await conn.execute(
                text("ALTER TABLE competitions ADD COLUMN competition_type VARCHAR(20) NOT NULL DEFAULT 'Oficial'")
            )
        if "competition_days" not in competition_columns:
            await conn.execute(
                text("ALTER TABLE competitions ADD COLUMN competition_days INTEGER NOT NULL DEFAULT 2")
            )
        for day_column in ("dia_1", "dia_2", "dia_3", "dia_4"):
            if day_column not in competition_columns:
                await conn.execute(
                    text(f"ALTER TABLE competitions ADD COLUMN {day_column} DATE")
                )
        table_names = await conn.run_sync(lambda sync_conn: set(inspect(sync_conn).get_table_names()))
        if "competition_checkins" not in table_names:
            await conn.execute(
                text(
                    """
                    CREATE TABLE competition_checkins (
                        id INTEGER NOT NULL,
                        competition_id INTEGER NOT NULL,
                        registration_id INTEGER NOT NULL,
                        athlete_id INTEGER NOT NULL,
                        checked_weight NUMERIC(5, 2) NOT NULL,
                        gi BOOLEAN NOT NULL,
                        overweight_confirmed BOOLEAN NOT NULL,
                        status VARCHAR(20) NOT NULL DEFAULT 'No checked',
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                        PRIMARY KEY (id),
                        UNIQUE (registration_id),
                        FOREIGN KEY(competition_id) REFERENCES competitions (id) ON DELETE CASCADE,
                        FOREIGN KEY(registration_id) REFERENCES competition_registrations (id) ON DELETE CASCADE,
                        FOREIGN KEY(athlete_id) REFERENCES athletes (id) ON DELETE RESTRICT
                    )
                    """
                )
            )
            await conn.execute(text("CREATE INDEX ix_competition_checkins_id ON competition_checkins (id)"))
            await conn.execute(
                text(
                    "CREATE INDEX ix_competition_checkins_competition_id "
                    "ON competition_checkins (competition_id)"
                )
            )
            await conn.execute(
                text(
                    "CREATE INDEX ix_competition_checkins_registration_id "
                    "ON competition_checkins (registration_id)"
                )
            )
            await conn.execute(
                text(
                    "CREATE INDEX ix_competition_checkins_athlete_id "
                    "ON competition_checkins (athlete_id)"
                )
            )
        else:
            checkin_columns = await conn.run_sync(
                lambda sync_conn: {
                    column["name"] for column in inspect(sync_conn).get_columns("competition_checkins")
                }
            )
            if "status" not in checkin_columns:
                await conn.execute(
                    text(
                        "ALTER TABLE competition_checkins "
                        "ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'No checked'"
                    )
                )
        table_names = await conn.run_sync(lambda sync_conn: set(inspect(sync_conn).get_table_names()))
        if "competition_checkin_closures" not in table_names:
            await conn.execute(
                text(
                    """
                    CREATE TABLE competition_checkin_closures (
                        id INTEGER NOT NULL,
                        competition_id INTEGER NOT NULL,
                        category_id INTEGER NOT NULL,
                        closed_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                        PRIMARY KEY (id),
                        UNIQUE (competition_id, category_id),
                        FOREIGN KEY(competition_id) REFERENCES competitions (id) ON DELETE CASCADE,
                        FOREIGN KEY(category_id) REFERENCES categories (id) ON DELETE RESTRICT
                    )
                    """
                )
            )
            await conn.execute(text("CREATE INDEX ix_competition_checkin_closures_id ON competition_checkin_closures (id)"))
            await conn.execute(
                text(
                    "CREATE INDEX ix_competition_checkin_closures_competition_id "
                    "ON competition_checkin_closures (competition_id)"
                )
            )
            await conn.execute(
                text(
                    "CREATE INDEX ix_competition_checkin_closures_category_id "
                    "ON competition_checkin_closures (category_id)"
                )
            )
        table_names = await conn.run_sync(lambda sync_conn: set(inspect(sync_conn).get_table_names()))
        if "competition_checkin_controls" not in table_names:
            await conn.execute(
                text(
                    """
                    CREATE TABLE competition_checkin_controls (
                        id INTEGER NOT NULL,
                        competition_id INTEGER NOT NULL,
                        category_id INTEGER NOT NULL,
                        started_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                        closed_at DATETIME,
                        PRIMARY KEY (id),
                        UNIQUE (competition_id, category_id),
                        FOREIGN KEY(competition_id) REFERENCES competitions (id) ON DELETE CASCADE,
                        FOREIGN KEY(category_id) REFERENCES categories (id) ON DELETE RESTRICT
                    )
                    """
                )
            )
            await conn.execute(text("CREATE INDEX ix_competition_checkin_controls_id ON competition_checkin_controls (id)"))
            await conn.execute(
                text(
                    "CREATE INDEX ix_competition_checkin_controls_competition_id "
                    "ON competition_checkin_controls (competition_id)"
                )
            )
            await conn.execute(
                text(
                    "CREATE INDEX ix_competition_checkin_controls_category_id "
                    "ON competition_checkin_controls (category_id)"
                )
            )
        table_names = await conn.run_sync(lambda sync_conn: set(inspect(sync_conn).get_table_names()))
        if "match_results" not in table_names:
            await conn.execute(
                text(
                    """
                    CREATE TABLE match_results (
                        id INTEGER NOT NULL,
                        match_id INTEGER NOT NULL,
                        athlete_a_points INTEGER NOT NULL DEFAULT 0,
                        athlete_a_advantages INTEGER NOT NULL DEFAULT 0,
                        athlete_a_penalties INTEGER NOT NULL DEFAULT 0,
                        athlete_b_points INTEGER NOT NULL DEFAULT 0,
                        athlete_b_advantages INTEGER NOT NULL DEFAULT 0,
                        athlete_b_penalties INTEGER NOT NULL DEFAULT 0,
                        winner_id INTEGER,
                        finish_method VARCHAR(30),
                        finalized BOOLEAN NOT NULL DEFAULT 0,
                        started_at DATETIME,
                        finished_at DATETIME,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                        PRIMARY KEY (id),
                        UNIQUE (match_id),
                        FOREIGN KEY(match_id) REFERENCES matches (id) ON DELETE CASCADE,
                        FOREIGN KEY(winner_id) REFERENCES athletes (id) ON DELETE RESTRICT
                    )
                    """
                )
            )
            await conn.execute(text("CREATE INDEX ix_match_results_id ON match_results (id)"))
            await conn.execute(text("CREATE INDEX ix_match_results_match_id ON match_results (match_id)"))
        else:
            match_result_columns = await conn.run_sync(
                lambda sync_conn: {
                    column["name"]
                    for column in inspect(sync_conn).get_columns("match_results")
                }
            )
            if "started_at" not in match_result_columns:
                await conn.execute(text("ALTER TABLE match_results ADD COLUMN started_at DATETIME"))
            if "finished_at" not in match_result_columns:
                await conn.execute(text("ALTER TABLE match_results ADD COLUMN finished_at DATETIME"))
        # Make athletes.team_id nullable (required for belts above black)
        athlete_columns = await conn.run_sync(
            lambda sync_conn: {
                col["name"]: col
                for col in inspect(sync_conn).get_columns("athletes")
            }
        )
        team_col = athlete_columns.get("team_id", {})
        if team_col.get("nullable") is False:
            dialect = conn.dialect.name
            if dialect == "postgresql":
                await conn.execute(text("ALTER TABLE athletes ALTER COLUMN team_id DROP NOT NULL"))
            # SQLite does not support ALTER COLUMN — the ORM create_all already handles new DBs correctly.

        team_columns = await conn.run_sync(
            lambda sync_conn: {
                col["name"]: col
                for col in inspect(sync_conn).get_columns("teams")
            }
        )
        responsible_col = team_columns.get("responsible", {})
        if responsible_col.get("nullable") is False:
            dialect = conn.dialect.name
            if dialect == "postgresql":
                await conn.execute(text("ALTER TABLE teams ALTER COLUMN responsible DROP NOT NULL"))

        table_names = await conn.run_sync(lambda sync_conn: set(inspect(sync_conn).get_table_names()))
        if conn.dialect.name == "postgresql" and "brackets" in table_names:
            await conn.execute(
                text("ALTER TABLE brackets DROP CONSTRAINT IF EXISTS uq_bracket_competition_category")
            )
        if "competition_schedule" not in table_names:
            await conn.execute(
                text(
                    """
                    CREATE TABLE competition_schedule (
                        id INTEGER NOT NULL,
                        competition_id INTEGER NOT NULL,
                        bracket_id INTEGER NOT NULL,
                        category_id INTEGER NOT NULL,
                        match_id INTEGER NOT NULL,
                        mat_number INTEGER NOT NULL,
                        day_number INTEGER NOT NULL,
                        scheduled_start DATETIME NOT NULL,
                        estimated_minutes INTEGER NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                        PRIMARY KEY (id),
                        UNIQUE (match_id),
                        FOREIGN KEY(competition_id) REFERENCES competitions (id) ON DELETE CASCADE,
                        FOREIGN KEY(bracket_id) REFERENCES brackets (id) ON DELETE CASCADE,
                        FOREIGN KEY(category_id) REFERENCES categories (id) ON DELETE RESTRICT,
                        FOREIGN KEY(match_id) REFERENCES matches (id) ON DELETE CASCADE
                    )
                    """
                )
            )
            await conn.execute(text("CREATE INDEX ix_competition_schedule_id ON competition_schedule (id)"))
            await conn.execute(text("CREATE INDEX ix_competition_schedule_competition_id ON competition_schedule (competition_id)"))
            await conn.execute(text("CREATE INDEX ix_competition_schedule_bracket_id ON competition_schedule (bracket_id)"))
            await conn.execute(text("CREATE INDEX ix_competition_schedule_category_id ON competition_schedule (category_id)"))
            await conn.execute(text("CREATE INDEX ix_competition_schedule_match_id ON competition_schedule (match_id)"))
            await conn.execute(text("CREATE INDEX ix_competition_schedule_mat_number ON competition_schedule (mat_number)"))
            await conn.execute(text("CREATE INDEX ix_competition_schedule_day_number ON competition_schedule (day_number)"))
            await conn.execute(text("CREATE INDEX ix_competition_schedule_scheduled_start ON competition_schedule (scheduled_start)"))

