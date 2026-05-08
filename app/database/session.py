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
