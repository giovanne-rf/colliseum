from __future__ import annotations

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Colliseum API"
    app_env: str = "development"
    database_url: str = "sqlite+aiosqlite:///./colliseum.db"
    sql_echo: bool = False

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @field_validator("database_url", mode="before")
    @classmethod
    def normalise_database_url(cls, v: str) -> str:
        # Railway (and some other hosts) provide postgres:// — SQLAlchemy needs
        # postgresql+asyncpg:// for async support.
        if v.startswith("postgres://"):
            v = v.replace("postgres://", "postgresql+asyncpg://", 1)
        elif v.startswith("postgresql://") and "+asyncpg" not in v:
            v = v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v


settings = Settings()
