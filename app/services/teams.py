from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Select, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete import Athlete
from app.models.team import Team
from app.schemas.team import TeamCreate, TeamUpdate
from app.services.exceptions import ConflictError, NotFoundError


@dataclass(frozen=True)
class TeamPage:
    items: list[Team]
    total: int
    limit: int
    offset: int


class TeamService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, payload: TeamCreate) -> Team:
        await self._ensure_name_is_available(payload.name)

        team = Team(**payload.model_dump())
        self.session.add(team)
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError("Team with the same name already exists.") from exc

        await self.session.refresh(team)
        await self._assign_responsible_athlete_to_team(team)
        return team

    async def create_many(self, payloads: list[TeamCreate]) -> list[Team]:
        for payload in payloads:
            await self._ensure_name_is_available(payload.name)

        teams = [Team(**payload.model_dump()) for payload in payloads]
        self.session.add_all(teams)
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError("One or more teams already exist.") from exc

        for team in teams:
            await self.session.refresh(team)
            await self._assign_responsible_athlete_to_team(team)
        return teams

    async def list(
        self,
        *,
        name: str | None = None,
        responsible: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> TeamPage:
        stmt = select(Team).order_by(Team.name)
        count_stmt = select(func.count(Team.id))

        stmt = self._apply_filters(stmt, name=name, responsible=responsible)
        count_stmt = self._apply_filters(count_stmt, name=name, responsible=responsible)

        total_result = await self.session.execute(count_stmt)
        total = int(total_result.scalar_one())

        result = await self.session.execute(stmt.limit(limit).offset(offset))
        return TeamPage(
            items=list(result.scalars().all()),
            total=total,
            limit=limit,
            offset=offset,
        )

    async def get(self, team_id: int) -> Team:
        team = await self.session.get(Team, team_id)
        if team is None:
            raise NotFoundError("Team not found.")
        return team

    async def update(self, team_id: int, payload: TeamUpdate) -> Team:
        team = await self.get(team_id)
        data = payload.model_dump(exclude_unset=True)

        if "name" in data:
            await self._ensure_name_is_available(data["name"], exclude_team_id=team_id)

        for field, value in data.items():
            setattr(team, field, value)

        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError("Team with the same name already exists.") from exc

        await self.session.refresh(team)
        await self._assign_responsible_athlete_to_team(team)
        return team

    async def delete(self, team_id: int) -> None:
        team = await self.get(team_id)
        await self.session.delete(team)
        await self.session.commit()

    def _apply_filters(
        self,
        stmt: Select,
        *,
        name: str | None,
        responsible: str | None,
    ) -> Select:
        if name is not None:
            stmt = stmt.where(Team.name.ilike(f"%{name.strip()}%"))
        if responsible is not None:
            stmt = stmt.where(Team.responsible.ilike(f"%{responsible.strip()}%"))
        return stmt

    async def _ensure_name_is_available(
        self,
        name: str,
        exclude_team_id: int | None = None,
    ) -> None:
        stmt = select(Team.id).where(func.lower(Team.name) == name.lower())
        if exclude_team_id is not None:
            stmt = stmt.where(Team.id != exclude_team_id)

        result = await self.session.execute(stmt)
        if result.scalar_one_or_none() is not None:
            raise ConflictError("Team with the same name already exists.")

    async def _assign_responsible_athlete_to_team(self, team: Team) -> None:
        if not team.responsible:
            return

        result = await self.session.execute(
            select(Athlete).where(func.lower(Athlete.name) == team.responsible.lower())
        )
        athletes = list(result.scalars().all())
        if not athletes:
            return

        for athlete in athletes:
            athlete.team_id = team.id

        await self.session.commit()
        await self.session.refresh(team)
