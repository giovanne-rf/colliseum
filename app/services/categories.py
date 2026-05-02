from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category
from app.schemas.category import CategoryCreate
from app.services.exceptions import ConflictError, NotFoundError


class CategoryService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, payload: CategoryCreate) -> Category:
        category = Category(**payload.model_dump())
        self.session.add(category)
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError("Category already exists.") from exc
        await self.session.refresh(category)
        return category

    async def create_many(self, payloads: list[CategoryCreate]) -> list[Category]:
        categories = [Category(**payload.model_dump()) for payload in payloads]
        self.session.add_all(categories)
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError("One or more categories already exist.") from exc

        for category in categories:
            await self.session.refresh(category)
        return categories

    async def list(self) -> list[Category]:
        result = await self.session.execute(select(Category).order_by(Category.id))
        return list(result.scalars().all())

    async def get(self, category_id: int) -> Category:
        category = await self.session.get(Category, category_id)
        if category is None:
            raise NotFoundError("Category not found.")
        return category
