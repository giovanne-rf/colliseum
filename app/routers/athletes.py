from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, Query, Response, status

from app.core.validators import validate_and_normalize_cpf
from app.models.common import Belt
from app.routers.deps import DbSession, translate_service_error
from app.schemas.athlete import (
    AthleteCreate,
    AthleteList,
    AthleteRead,
    AthleteUpdate,
    CpfAvailabilityRead,
)
from app.services.athletes import AthleteService
from app.services.exceptions import ServiceError

router = APIRouter(prefix="/athletes", tags=["athletes"])


@router.post(
    "",
    response_model=AthleteRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create athlete",
    responses={
        201: {
            "description": "Athlete created.",
            "content": {
                "application/json": {
                    "example": {
                        "id": 1,
                        "name": "Maria Silva",
                        "cpf": "52998224725",
                        "email": "maria.silva@example.com",
                        "phone": "11-99999.1234",
                        "sex": "female",
                        "team_id": 1,
                        "belt": "blue",
                        "graduation_date": "2024-12-10",
                        "birth_date": "2002-05-14",
                        "age": 23,
                    }
                }
            },
        }
    },
)
async def create_athlete(payload: AthleteCreate, session: DbSession) -> AthleteRead:
    try:
        return await AthleteService(session).create(payload)
    except ServiceError as exc:
        raise translate_service_error(exc) from exc


@router.post(
    "/bulk",
    response_model=list[AthleteRead],
    status_code=status.HTTP_201_CREATED,
    summary="Create athletes in bulk",
)
async def create_athletes_bulk(
    payload: Annotated[list[AthleteCreate], Body(min_length=1, max_length=100)],
    session: DbSession,
) -> list[AthleteRead]:
    try:
        return await AthleteService(session).create_many(payload)
    except ServiceError as exc:
        raise translate_service_error(exc) from exc


@router.get("", response_model=AthleteList, summary="List athletes")
async def list_athletes(
    session: DbSession,
    belt: Belt | None = Query(default=None, description="Filter by belt."),
    team_id: int | None = Query(default=None, gt=0, description="Filter by team ID."),
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AthleteList:
    page = await AthleteService(session).list(
        belt=belt,
        team_id=team_id,
        limit=limit,
        offset=offset,
    )
    return AthleteList(items=page.items, total=page.total, limit=page.limit, offset=page.offset)


@router.get("/check-cpf", response_model=CpfAvailabilityRead, summary="Check CPF availability")
async def check_cpf(
    session: DbSession,
    cpf: str = Query(..., min_length=11, max_length=14),
) -> CpfAvailabilityRead:
    try:
        normalized_cpf = validate_and_normalize_cpf(cpf)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    athlete_id = await AthleteService(session).find_id_by_cpf(normalized_cpf)
    return CpfAvailabilityRead(
        cpf=normalized_cpf,
        exists=athlete_id is not None,
        athlete_id=athlete_id,
    )


@router.get("/{athlete_id}", response_model=AthleteRead, summary="Get athlete by ID")
async def get_athlete(athlete_id: int, session: DbSession) -> AthleteRead:
    try:
        return await AthleteService(session).get(athlete_id)
    except ServiceError as exc:
        raise translate_service_error(exc) from exc


@router.put("/{athlete_id}", response_model=AthleteRead, summary="Update athlete")
async def update_athlete(
    athlete_id: int,
    payload: AthleteUpdate,
    session: DbSession,
) -> AthleteRead:
    try:
        return await AthleteService(session).update(athlete_id, payload)
    except ServiceError as exc:
        raise translate_service_error(exc) from exc


@router.delete(
    "/{athlete_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete athlete",
)
async def delete_athlete(athlete_id: int, session: DbSession) -> Response:
    try:
        await AthleteService(session).delete(athlete_id)
    except ServiceError as exc:
        raise translate_service_error(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
