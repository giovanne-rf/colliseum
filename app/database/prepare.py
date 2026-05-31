from __future__ import annotations

import asyncio
import subprocess
import sys

from sqlalchemy import inspect, text

from app.database.session import create_db_and_tables, engine


def run_alembic(*args: str) -> None:
    subprocess.run([sys.executable, "-m", "alembic", *args], check=True)


async def has_legacy_schema_without_alembic() -> bool:
    async with engine.begin() as conn:
        table_names = await conn.run_sync(lambda sync_conn: set(inspect(sync_conn).get_table_names()))
        has_version = "alembic_version" in table_names
        version_count = 0
        if has_version:
            result = await conn.execute(text("SELECT COUNT(*) FROM alembic_version"))
            version_count = int(result.scalar_one())
    user_tables = table_names - {"alembic_version"}
    return bool(user_tables) and (not has_version or version_count == 0)


async def main() -> None:
    if await has_legacy_schema_without_alembic():
        await create_db_and_tables()
        run_alembic("stamp", "head")
        return
    run_alembic("upgrade", "head")


if __name__ == "__main__":
    asyncio.run(main())
