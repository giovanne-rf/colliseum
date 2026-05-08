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
