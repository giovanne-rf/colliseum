from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, status

from app.models.common import Belt
from app.routers.deps import DbSession, translate_service_error
from app.schemas.ranking import (
    RankingEntryCreate,
    RankingEntryList,
    RankingEntryRead,
    RankingOptionsRead,
    RankingStandingsRead,
)
from app.services.exceptions import ServiceError
from app.services.ranking import RankingService

router = APIRouter(prefix="/ranking", tags=["ranking"])


@router.post(
    "",
    response_model=RankingEntryRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add ranking points to an athlete",
)
async def create_ranking_entry(
    payload: RankingEntryCreate,
    session: DbSession,
) -> RankingEntryRead:
    try:
        return await RankingService(session).create(payload)
    except ServiceError as exc:
        raise translate_service_error(exc) from exc


@router.get("/entries", response_model=RankingEntryList, summary="List ranking entries")
async def list_ranking_entries(
    session: DbSession,
    belt: Belt | None = Query(default=None, description="Filter by belt."),
    age_group: str | None = Query(default=None, description="Filter by age category."),
    athlete_id: int | None = Query(default=None, gt=0, description="Filter by athlete."),
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> RankingEntryList:
    page = await RankingService(session).list(
        belt=belt,
        age_group=age_group,
        athlete_id=athlete_id,
        limit=limit,
        offset=offset,
    )
    return RankingEntryList(
        items=page.items,
        total=page.total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get("/standings", response_model=RankingStandingsRead, summary="List ranking standings")
async def ranking_standings(session: DbSession) -> RankingStandingsRead:
    return await RankingService(session).standings()


@router.get("/options", response_model=RankingOptionsRead, summary="List ranking form options")
async def ranking_options(
    session: DbSession,
    belt: Belt | None = Query(default=None, description="Filter athletes by belt."),
    age_group: str | None = Query(default=None, description="Filter athletes by age category."),
) -> RankingOptionsRead:
    return await RankingService(session).options(belt=belt, age_group=age_group)
