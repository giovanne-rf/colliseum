from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.database.session import create_db_and_tables
from app.routers import athletes, categories, competitions, health, ranking, teams


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
app.include_router(competitions.router)
app.include_router(ranking.router)

static_dir = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", include_in_schema=False)
async def frontend() -> RedirectResponse:
    return RedirectResponse(url="/cadastros")


@app.get("/cadastros", include_in_schema=False)
async def athlete_frontend() -> FileResponse:
    return FileResponse(static_dir / "react.html")


@app.get("/equipes", include_in_schema=False)
async def team_frontend() -> FileResponse:
    return FileResponse(static_dir / "react.html")


@app.get("/competicoes", include_in_schema=False)
async def competition_frontend() -> FileResponse:
    return FileResponse(static_dir / "react.html")


@app.get("/inscricoes", include_in_schema=False)
async def registration_frontend() -> FileResponse:
    return FileResponse(static_dir / "react.html")


@app.get("/chaves", include_in_schema=False)
async def bracket_frontend() -> FileResponse:
    return FileResponse(static_dir / "react.html")


@app.get("/checagem", include_in_schema=False)
async def checkin_frontend() -> FileResponse:
    return FileResponse(static_dir / "react.html")


@app.get("/checkin/pesagem", include_in_schema=False)
async def weighin_frontend() -> FileResponse:
    return FileResponse(static_dir / "react.html")


@app.get("/checkin", include_in_schema=False)
async def ready_checkin_frontend() -> FileResponse:
    return FileResponse(static_dir / "react.html")


@app.get("/checagem-final", include_in_schema=False)
async def final_check_frontend() -> FileResponse:
    return FileResponse(static_dir / "react.html")


@app.get("/ranking", include_in_schema=False)
async def ranking_frontend() -> FileResponse:
    return FileResponse(static_dir / "react.html")
