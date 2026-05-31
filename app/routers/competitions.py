from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Body, Query, status

from app.routers.deps import DbSession, translate_service_error
from app.schemas.bracket import (
    BracketGenerateRequest,
    BracketBatchGenerateRead,
    BracketGenerateAllRequest,
    BracketRead,
    CompetitionCheckinCreate,
    CompetitionCheckinClosureRead,
    CompetitionFinalCheckRead,
    CompetitionCheckinLookupRead,
    CompetitionCheckinRead,
    CompetitionCreate,
    CompetitionRead,
    CompetitionRegistrationCreate,
    CompetitionRegistrationRead,
    CompetitionScheduleRead,
    MatchResultRead,
    MatchResultUpdate,
    RegistrationOptionsRead,
)
from app.services.brackets import (
    BracketService,
    CheckinService,
    CompetitionService,
    RegistrationService,
    ScheduleService,
)
from app.services.exceptions import ServiceError

router = APIRouter(prefix="/competitions", tags=["competitions"])


@router.post(
    "",
    response_model=CompetitionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create competition",
)
async def create_competition(payload: CompetitionCreate, session: DbSession) -> CompetitionRead:
    try:
        return await CompetitionService(session).create(payload)
    except ServiceError as exc:
        raise translate_service_error(exc) from exc


@router.get("", response_model=list[CompetitionRead], summary="List competitions")
async def list_competitions(session: DbSession) -> list[CompetitionRead]:
    return await CompetitionService(session).list()


@router.get(
    "/{competition_id}/schedule",
    response_model=CompetitionScheduleRead,
    summary="List competition schedule",
)
async def list_schedule(competition_id: int, session: DbSession) -> CompetitionScheduleRead:
    try:
        return await ScheduleService(session).list_for_competition(competition_id)
    except ServiceError as exc:
        raise translate_service_error(exc) from exc


@router.post(
    "/{competition_id}/registrations",
    response_model=CompetitionRegistrationRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register athlete in competition category",
)
async def create_registration(
    competition_id: int,
    payload: CompetitionRegistrationCreate,
    session: DbSession,
) -> CompetitionRegistrationRead:
    try:
        return await RegistrationService(session).create(competition_id, payload)
    except ServiceError as exc:
        raise translate_service_error(exc) from exc


@router.post(
    "/{competition_id}/registrations/bulk",
    response_model=list[CompetitionRegistrationRead],
    status_code=status.HTTP_201_CREATED,
    summary="Register athletes in competition categories in bulk",
)
async def create_registrations_bulk(
    competition_id: int,
    payload: Annotated[list[CompetitionRegistrationCreate], Body(min_length=1, max_length=100)],
    session: DbSession,
) -> list[CompetitionRegistrationRead]:
    try:
        return await RegistrationService(session).create_many(competition_id, payload)
    except ServiceError as exc:
        raise translate_service_error(exc) from exc


@router.get(
    "/{competition_id}/registrations",
    response_model=list[CompetitionRegistrationRead],
    summary="List competition registrations",
)
async def list_registrations(
    competition_id: int,
    session: DbSession,
    category_id: int | None = Query(default=None, gt=0),
) -> list[CompetitionRegistrationRead]:
    try:
        page = await RegistrationService(session).list(
            competition_id=competition_id,
            category_id=category_id,
        )
    except ServiceError as exc:
        raise translate_service_error(exc) from exc
    return page.items


@router.get(
    "/{competition_id}/registration-options",
    response_model=RegistrationOptionsRead,
    summary="Validate athlete and list eligible IBJJF categories",
)
async def get_registration_options(
    competition_id: int,
    session: DbSession,
    cpf: str = Query(..., min_length=11, max_length=14),
    birth_date: date = Query(...),
) -> RegistrationOptionsRead:
    try:
        return await RegistrationService(session).get_options(
            competition_id=competition_id,
            cpf=cpf,
            birth_date=birth_date,
        )
    except ServiceError as exc:
        raise translate_service_error(exc) from exc


@router.get(
    "/{competition_id}/checkin-options",
    response_model=CompetitionCheckinLookupRead,
    summary="Find athlete registration for competition check-in",
)
async def get_checkin_options(
    competition_id: int,
    session: DbSession,
    cpf: str = Query(..., min_length=11, max_length=14),
) -> CompetitionCheckinLookupRead:
    try:
        return await CheckinService(session).lookup(competition_id=competition_id, cpf=cpf)
    except ServiceError as exc:
        raise translate_service_error(exc) from exc


@router.get(
    "/{competition_id}/final-checks",
    response_model=list[CompetitionFinalCheckRead],
    summary="List final athlete check statuses by competition",
)
async def list_final_checks(
    competition_id: int,
    session: DbSession,
) -> list[CompetitionFinalCheckRead]:
    try:
        return await CheckinService(session).list_final_checks(competition_id)
    except ServiceError as exc:
        raise translate_service_error(exc) from exc


@router.post(
    "/{competition_id}/categories/{category_id}/checkin/close",
    response_model=CompetitionCheckinClosureRead,
    summary="Close check-in for a competition category",
)
async def close_category_checkin(
    competition_id: int,
    category_id: int,
    session: DbSession,
) -> CompetitionCheckinClosureRead:
    try:
        return await CheckinService(session).close_category_checkin(
            competition_id=competition_id,
            category_id=category_id,
        )
    except ServiceError as exc:
        raise translate_service_error(exc) from exc


@router.post(
    "/{competition_id}/checkins",
    response_model=CompetitionCheckinRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create or update athlete competition check-in",
)
async def create_checkin(
    competition_id: int,
    payload: CompetitionCheckinCreate,
    session: DbSession,
) -> CompetitionCheckinRead:
    try:
        return await CheckinService(session).create_or_update(
            competition_id=competition_id,
            payload=payload,
        )
    except ServiceError as exc:
        raise translate_service_error(exc) from exc


@router.post(
    "/{competition_id}/checkins/{registration_id}/ready",
    response_model=CompetitionCheckinRead,
    summary="Mark weighed athlete as ready to fight",
)
async def ready_to_fight(
    competition_id: int,
    registration_id: int,
    session: DbSession,
) -> CompetitionCheckinRead:
    try:
        return await CheckinService(session).ready_to_fight(
            competition_id=competition_id,
            registration_id=registration_id,
        )
    except ServiceError as exc:
        raise translate_service_error(exc) from exc


@router.post(
    "/{competition_id}/checkins/{registration_id}/not-ready",
    response_model=CompetitionCheckinRead,
    summary="Mark weighed athlete as not ready to fight",
)
async def not_ready_to_fight(
    competition_id: int,
    registration_id: int,
    session: DbSession,
) -> CompetitionCheckinRead:
    try:
        return await CheckinService(session).not_ready_to_fight(
            competition_id=competition_id,
            registration_id=registration_id,
        )
    except ServiceError as exc:
        raise translate_service_error(exc) from exc


@router.post(
    "/{competition_id}/brackets/generate-all",
    response_model=BracketBatchGenerateRead,
    status_code=status.HTTP_201_CREATED,
    summary="Generate all IBJJF-style brackets for a competition",
)
async def generate_all_brackets(
    competition_id: int,
    payload: BracketGenerateAllRequest,
    session: DbSession,
) -> BracketBatchGenerateRead:
    try:
        brackets, skipped_count = await BracketService(session).generate_all(
            competition_id=competition_id,
            replace_existing=payload.replace_existing,
        )
    except ServiceError as exc:
        raise translate_service_error(exc) from exc
    return BracketBatchGenerateRead(
        competition_id=competition_id,
        generated_count=len(brackets),
        skipped_count=skipped_count,
        brackets=brackets,
    )


@router.get(
    "/{competition_id}/brackets",
    response_model=list[BracketRead],
    summary="List saved brackets for a competition",
)
async def list_brackets(competition_id: int, session: DbSession) -> list[BracketRead]:
    try:
        return await BracketService(session).list_for_competition(competition_id)
    except ServiceError as exc:
        raise translate_service_error(exc) from exc


@router.put(
    "/{competition_id}/matches/{match_id}/result",
    response_model=MatchResultRead,
    summary="Persist match score and result",
)
async def update_match_result(
    competition_id: int,
    match_id: int,
    payload: MatchResultUpdate,
    session: DbSession,
) -> MatchResultRead:
    try:
        return await BracketService(session).update_match_result(
            competition_id=competition_id,
            match_id=match_id,
            payload=payload,
        )
    except ServiceError as exc:
        raise translate_service_error(exc) from exc


@router.post(
    "/{competition_id}/brackets",
    response_model=BracketRead,
    status_code=status.HTTP_201_CREATED,
    summary="Generate IBJJF-style bracket",
)
async def generate_bracket(
    competition_id: int,
    payload: BracketGenerateRequest,
    session: DbSession,
) -> BracketRead:
    try:
        return await BracketService(session).generate(
            competition_id=competition_id,
            category_id=payload.category_id,
            replace_existing=payload.replace_existing,
        )
    except ServiceError as exc:
        raise translate_service_error(exc) from exc


@router.get("/brackets/{bracket_id}", response_model=BracketRead, summary="Get bracket by ID")
async def get_bracket(bracket_id: int, session: DbSession) -> BracketRead:
    try:
        return await BracketService(session).get(bracket_id)
    except ServiceError as exc:
        raise translate_service_error(exc) from exc
