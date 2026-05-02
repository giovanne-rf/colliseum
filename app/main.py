from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.database.session import create_db_and_tables
from app.routers import athletes, categories, health, teams


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.app_env == "development":
        await create_db_and_tables()
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Athlete registration backend for Brazilian Jiu-Jitsu competitions.",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(categories.router)
app.include_router(teams.router)
app.include_router(athletes.router)

static_dir = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", include_in_schema=False)
async def frontend() -> RedirectResponse:
    return RedirectResponse(url="/cadastros")


@app.get("/cadastros", include_in_schema=False)
async def athlete_frontend() -> FileResponse:
    return FileResponse(static_dir / "index.html")


@app.get("/equipes", include_in_schema=False)
async def team_frontend() -> FileResponse:
    return FileResponse(static_dir / "equipes.html")
