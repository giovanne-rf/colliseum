from __future__ import annotations

from fastapi import APIRouter, status

from app.routers.deps import DbSession, translate_service_error
from app.schemas.category import CategoryCreate, CategoryRead
from app.services.categories import CategoryService
from app.services.exceptions import ServiceError

router = APIRouter(prefix="/categories", tags=["categories"])


@router.post(
    "",
    response_model=CategoryRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create category",
)
async def create_category(payload: CategoryCreate, session: DbSession) -> CategoryRead:
    try:
        return await CategoryService(session).create(payload)
    except ServiceError as exc:
        raise translate_service_error(exc) from exc


@router.get("", response_model=list[CategoryRead], summary="List categories")
async def list_categories(session: DbSession) -> list[CategoryRead]:
    return await CategoryService(session).list()


@router.post(
    "/bulk",
    response_model=list[CategoryRead],
    status_code=status.HTTP_201_CREATED,
    summary="Create categories in bulk",
)
async def create_categories_bulk(
    payload: list[CategoryCreate],
    session: DbSession,
) -> list[CategoryRead]:
    try:
        return await CategoryService(session).create_many(payload)
    except ServiceError as exc:
        raise translate_service_error(exc) from exc


@router.get("/{category_id}", response_model=CategoryRead, summary="Get category by ID")
async def get_category(category_id: int, session: DbSession) -> CategoryRead:
    try:
        return await CategoryService(session).get(category_id)
    except ServiceError as exc:
        raise translate_service_error(exc) from exc
