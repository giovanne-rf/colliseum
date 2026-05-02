from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.routers.deps import DbSession, translate_service_error
from app.schemas.team import TeamCreate, TeamList, TeamRead, TeamUpdate
from app.services.exceptions import ServiceError
from app.services.teams import TeamService

router = APIRouter(prefix="/teams", tags=["teams"])


@router.post(
    "",
    response_model=TeamRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create team",
)
async def create_team(payload: TeamCreate, session: DbSession) -> TeamRead:
    try:
        return await TeamService(session).create(payload)
    except ServiceError as exc:
        raise translate_service_error(exc) from exc


@router.get("", response_model=TeamList, summary="List teams")
async def list_teams(
    session: DbSession,
    name: str | None = Query(default=None, min_length=1, description="Filter by team name."),
    responsible: str | None = Query(
        default=None,
        min_length=1,
        description="Filter by responsible person.",
    ),
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> TeamList:
    page = await TeamService(session).list(
        name=name,
        responsible=responsible,
        limit=limit,
        offset=offset,
    )
    return TeamList(items=page.items, total=page.total, limit=page.limit, offset=page.offset)


@router.post(
    "/bulk",
    response_model=list[TeamRead],
    status_code=status.HTTP_201_CREATED,
    summary="Create teams in bulk",
)
async def create_teams_bulk(payload: list[TeamCreate], session: DbSession) -> list[TeamRead]:
    try:
        return await TeamService(session).create_many(payload)
    except ServiceError as exc:
        raise translate_service_error(exc) from exc


@router.get("/{team_id}", response_model=TeamRead, summary="Get team by ID")
async def get_team(team_id: int, session: DbSession) -> TeamRead:
    try:
        return await TeamService(session).get(team_id)
    except ServiceError as exc:
        raise translate_service_error(exc) from exc


@router.put("/{team_id}", response_model=TeamRead, summary="Update team")
async def update_team(team_id: int, payload: TeamUpdate, session: DbSession) -> TeamRead:
    try:
        return await TeamService(session).update(team_id, payload)
    except ServiceError as exc:
        raise translate_service_error(exc) from exc


@router.delete(
    "/{team_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete team",
)
async def delete_team(team_id: int, session: DbSession) -> Response:
    try:
        await TeamService(session).delete(team_id)
    except ServiceError as exc:
        raise translate_service_error(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
