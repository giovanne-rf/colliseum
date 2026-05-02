from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import Select, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dates import calculate_age
from app.models.athlete import Athlete
from app.models.common import Belt
from app.models.team import Team
from app.schemas.athlete import AthleteCreate, AthleteUpdate
from app.services.exceptions import ConflictError, NotFoundError, ValidationError


@dataclass(frozen=True)
class AthletePage:
    items: list[Athlete]
    total: int
    limit: int
    offset: int


class AthleteService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, payload: AthleteCreate) -> Athlete:
        self._validate_minimum_age(payload.birth_date, date.today())
        await self._ensure_team_exists(payload.team_id)
        await self._ensure_no_duplicate(name=payload.name, team_id=payload.team_id)
        await self._ensure_cpf_is_available(cpf=payload.cpf)
        await self._ensure_email_is_available(email=payload.email)

        athlete = Athlete(**payload.model_dump())
        self.session.add(athlete)
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError("Athlete with the same name/team, CPF, or email already exists.") from exc

        return await self.get(athlete.id)

    async def list(
        self,
        *,
        belt: Belt | None = None,
        team_id: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> AthletePage:
        stmt = select(Athlete).options(selectinload(Athlete.team)).order_by(Athlete.id)
        count_stmt = select(func.count(Athlete.id))

        stmt = self._apply_filters(stmt, belt=belt, team_id=team_id)
        count_stmt = self._apply_filters(count_stmt, belt=belt, team_id=team_id)

        total_result = await self.session.execute(count_stmt)
        total = int(total_result.scalar_one())

        result = await self.session.execute(stmt.limit(limit).offset(offset))
        items = list(result.scalars().all())
        return AthletePage(items=items, total=total, limit=limit, offset=offset)

    async def get(self, athlete_id: int) -> Athlete:
        result = await self.session.execute(
            select(Athlete)
            .where(Athlete.id == athlete_id)
            .options(selectinload(Athlete.team))
        )
        athlete = result.scalar_one_or_none()
        if athlete is None:
            raise NotFoundError("Athlete not found.")
        return athlete

    async def update(self, athlete_id: int, payload: AthleteUpdate) -> Athlete:
        athlete = await self.get(athlete_id)
        data = payload.model_dump(exclude_unset=True)

        target_birth_date = data.get("birth_date", athlete.birth_date)
        target_graduation_date = data.get("graduation_date", athlete.graduation_date)
        target_name = data.get("name", athlete.name)
        target_team_id = data.get("team_id", athlete.team_id)
        target_cpf = data.get("cpf", athlete.cpf)
        target_email = data.get("email", athlete.email)
        self._validate_minimum_age(target_birth_date, date.today())
        self._validate_graduation_date(
            birth_date=target_birth_date,
            graduation_date=target_graduation_date,
        )

        if "team_id" in data:
            await self._ensure_team_exists(target_team_id)

        if {"name", "team_id"} & data.keys():
            await self._ensure_no_duplicate(
                name=target_name,
                team_id=target_team_id,
                exclude_athlete_id=athlete_id,
            )

        if "cpf" in data:
            await self._ensure_cpf_is_available(cpf=target_cpf, exclude_athlete_id=athlete_id)

        if "email" in data:
            await self._ensure_email_is_available(
                email=target_email,
                exclude_athlete_id=athlete_id,
            )

        for field, value in data.items():
            setattr(athlete, field, value)

        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError("Athlete with the same name/team, CPF, or email already exists.") from exc

        return await self.get(athlete_id)

    async def delete(self, athlete_id: int) -> None:
        athlete = await self.get(athlete_id)
        await self.session.delete(athlete)
        await self.session.commit()

    def _apply_filters(
        self,
        stmt: Select,
        *,
        belt: Belt | None,
        team_id: int | None,
    ) -> Select:
        if belt is not None:
            stmt = stmt.where(Athlete.belt == belt)
        if team_id is not None:
            stmt = stmt.where(Athlete.team_id == team_id)
        return stmt

    async def _ensure_team_exists(self, team_id: int) -> Team:
        team = await self.session.get(Team, team_id)
        if team is None:
            raise ValidationError("Athlete must belong to an existing team.")
        return team

    async def _ensure_no_duplicate(
        self,
        *,
        name: str,
        team_id: int,
        exclude_athlete_id: int | None = None,
    ) -> None:
        stmt = select(Athlete.id).where(
            func.lower(Athlete.name) == name.lower(),
            Athlete.team_id == team_id,
        )
        if exclude_athlete_id is not None:
            stmt = stmt.where(Athlete.id != exclude_athlete_id)

        result = await self.session.execute(stmt)
        if result.scalar_one_or_none() is not None:
            raise ConflictError("Athlete with the same name and team already exists.")

    async def _ensure_cpf_is_available(
        self,
        *,
        cpf: str,
        exclude_athlete_id: int | None = None,
    ) -> None:
        stmt = select(Athlete.id).where(Athlete.cpf == cpf)
        if exclude_athlete_id is not None:
            stmt = stmt.where(Athlete.id != exclude_athlete_id)

        result = await self.session.execute(stmt)
        if result.scalar_one_or_none() is not None:
            raise ConflictError("Athlete with the same CPF already exists.")

    async def _ensure_email_is_available(
        self,
        *,
        email: str,
        exclude_athlete_id: int | None = None,
    ) -> None:
        stmt = select(Athlete.id).where(func.lower(Athlete.email) == email.lower())
        if exclude_athlete_id is not None:
            stmt = stmt.where(Athlete.id != exclude_athlete_id)

        result = await self.session.execute(stmt)
        if result.scalar_one_or_none() is not None:
            raise ConflictError("Athlete with the same email already exists.")

    def _validate_minimum_age(self, birth_date: date, reference_date: date) -> int:
        age = calculate_age(birth_date, reference_date)
        if age < 4:
            raise ValidationError("Athlete must be at least 4 years old on the reference date.")
        return age

    def _validate_graduation_date(self, *, birth_date: date, graduation_date: date) -> None:
        if graduation_date < birth_date:
            raise ValidationError("Graduation date cannot be before birth date.")
