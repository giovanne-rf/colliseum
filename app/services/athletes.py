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
        self._validate_minimum_age_for_belt(
            birth_date=payload.birth_date,
            belt=payload.belt,
            reference_date=date.today(),
        )
        self._validate_team_required_for_belt(team_id=payload.team_id, belt=payload.belt)
        if payload.team_id is not None:
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

    async def create_many(self, payloads: list[AthleteCreate]) -> list[Athlete]:
        self._validate_bulk_payload(payloads)

        for payload in payloads:
            self._validate_minimum_age_for_belt(
                birth_date=payload.birth_date,
                belt=payload.belt,
                reference_date=date.today(),
            )
            self._validate_graduation_date(
                birth_date=payload.birth_date,
                graduation_date=payload.graduation_date,
            )
            self._validate_team_required_for_belt(team_id=payload.team_id, belt=payload.belt)
            if payload.team_id is not None:
                await self._ensure_team_exists(payload.team_id)
            await self._ensure_no_duplicate(name=payload.name, team_id=payload.team_id)
            await self._ensure_cpf_is_available(cpf=payload.cpf)
            await self._ensure_email_is_available(email=payload.email)

        athletes = [Athlete(**payload.model_dump()) for payload in payloads]
        self.session.add_all(athletes)
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError(
                "One or more athletes have the same name/team, CPF, or email."
            ) from exc

        athlete_ids = [athlete.id for athlete in athletes]
        result = await self.session.execute(
            select(Athlete)
            .where(Athlete.id.in_(athlete_ids))
            .options(selectinload(Athlete.team))
        )
        athletes_by_id = {athlete.id: athlete for athlete in result.scalars().all()}
        return [athletes_by_id[athlete_id] for athlete_id in athlete_ids]

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

    async def find_id_by_cpf(self, cpf: str) -> int | None:
        result = await self.session.execute(select(Athlete.id).where(Athlete.cpf == cpf))
        athlete_id = result.scalar_one_or_none()
        return int(athlete_id) if athlete_id is not None else None

    async def update(self, athlete_id: int, payload: AthleteUpdate) -> Athlete:
        athlete = await self.get(athlete_id)
        data = payload.model_dump(exclude_unset=True)

        target_birth_date = data.get("birth_date", athlete.birth_date)
        target_graduation_date = data.get("graduation_date", athlete.graduation_date)
        target_belt = data.get("belt", athlete.belt)
        target_name = data.get("name", athlete.name)
        target_team_id = data.get("team_id", athlete.team_id)
        target_cpf = data.get("cpf", athlete.cpf)
        target_email = data.get("email", athlete.email)
        self._validate_minimum_age_for_belt(
            birth_date=target_birth_date,
            belt=target_belt,
            reference_date=date.today(),
        )
        self._validate_graduation_date(
            birth_date=target_birth_date,
            graduation_date=target_graduation_date,
        )
        self._validate_team_required_for_belt(team_id=target_team_id, belt=target_belt)

        if "team_id" in data and target_team_id is not None:
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

    def _validate_bulk_payload(self, payloads: list[AthleteCreate]) -> None:
        seen_name_team: set[tuple[str, int | None]] = set()
        seen_cpfs: set[str] = set()
        seen_emails: set[str] = set()

        for payload in payloads:
            # Only check name+team uniqueness when team is set; CPF is the primary key otherwise
            name_team_key = (payload.name.lower(), payload.team_id)
            email_key = payload.email.lower()
            if payload.team_id is not None and name_team_key in seen_name_team:
                raise ConflictError("Bulk payload contains duplicate athlete name/team.")
            if payload.cpf in seen_cpfs:
                raise ConflictError("Bulk payload contains duplicate CPF.")
            if email_key in seen_emails:
                raise ConflictError("Bulk payload contains duplicate email.")

            seen_name_team.add(name_team_key)
            seen_cpfs.add(payload.cpf)
            seen_emails.add(email_key)

    async def _ensure_team_exists(self, team_id: int) -> Team:
        team = await self.session.get(Team, team_id)
        if team is None:
            raise ValidationError("Athlete must belong to an existing team.")
        return team

    async def _ensure_no_duplicate(
        self,
        *,
        name: str,
        team_id: int | None,
        exclude_athlete_id: int | None = None,
    ) -> None:
        # Only enforce name+team uniqueness when team is defined
        if team_id is None:
            return
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

    def _validate_minimum_age_for_belt(
        self,
        *,
        birth_date: date,
        belt: Belt,
        reference_date: date,
    ) -> int:
        age = calculate_age(birth_date, reference_date)
        minimum_age = minimum_age_for_belt(belt)
        if age < minimum_age:
            raise ValidationError(
                f"Athlete must be at least {minimum_age} years old for belt {belt}."
            )
        return age

    def _validate_graduation_date(self, *, birth_date: date, graduation_date: date) -> None:
        if graduation_date < birth_date:
            raise ValidationError("Graduation date cannot be before birth date.")

    def _validate_team_required_for_belt(self, *, team_id: int | None, belt: Belt) -> None:
        if belt != Belt.black and team_id is None:
            raise ValidationError("Athlete must belong to an academy unless they are a black belt.")


def minimum_age_for_belt(belt: Belt) -> int:
    return {
        Belt.white: 0,
        Belt.gray: 4,
        Belt.gray_white: 4,
        Belt.gray_black: 4,
        Belt.yellow: 7,
        Belt.yellow_white: 7,
        Belt.yellow_black: 7,
        Belt.orange: 10,
        Belt.orange_white: 10,
        Belt.orange_black: 10,
        Belt.green: 13,
        Belt.green_white: 13,
        Belt.green_black: 13,
        Belt.blue: 16,
        Belt.purple: 16,
        Belt.brown: 18,
        Belt.black: 19,
        Belt.red_black: 50,
        Belt.red_white: 57,
        Belt.red: 67,
    }[belt]
