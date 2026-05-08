from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import Select, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dates import calculate_age
from app.models.athlete import Athlete
from app.models.bracket import Competition, CompetitionRegistration
from app.models.common import Belt
from app.models.ranking import RankingEntry
from app.schemas.ranking import (
    RankingAthleteOption,
    RankingEntryCreate,
    RankingOptionsRead,
    RankingStandingGroupRead,
    RankingStandingRead,
    RankingStandingsRead,
)
from app.services.brackets import ibjjf_age_group
from app.services.exceptions import ConflictError, NotFoundError, ValidationError


@dataclass(frozen=True)
class RankingPage:
    items: list[RankingEntry]
    total: int
    limit: int
    offset: int


class RankingService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, payload: RankingEntryCreate) -> RankingEntry:
        athlete = await self._ensure_athlete_exists(payload.athlete_id)
        age_group = self._athlete_age_group(athlete)

        if athlete.belt != payload.belt:
            raise ValidationError("Selected belt does not match the athlete belt.")
        if age_group != payload.age_group:
            raise ValidationError("Selected age category does not match the athlete age.")
        await self._ensure_athlete_is_registered_in_competition(
            athlete_id=athlete.id,
            competition_name=payload.competition_name,
        )

        entry = RankingEntry(**payload.model_dump())
        self.session.add(entry)
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError("Ranking entry could not be created.") from exc

        return await self.get(entry.id)

    async def list(
        self,
        *,
        belt: Belt | None = None,
        age_group: str | None = None,
        athlete_id: int | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> RankingPage:
        stmt = (
            select(RankingEntry)
            .options(selectinload(RankingEntry.athlete).selectinload(Athlete.team))
            .order_by(RankingEntry.created_at.desc(), RankingEntry.id.desc())
        )
        count_stmt = select(func.count(RankingEntry.id))

        stmt = self._apply_filters(stmt, belt=belt, age_group=age_group, athlete_id=athlete_id)
        count_stmt = self._apply_filters(
            count_stmt,
            belt=belt,
            age_group=age_group,
            athlete_id=athlete_id,
        )

        total_result = await self.session.execute(count_stmt)
        total = int(total_result.scalar_one())

        result = await self.session.execute(stmt.limit(limit).offset(offset))
        return RankingPage(
            items=list(result.scalars().all()),
            total=total,
            limit=limit,
            offset=offset,
        )

    async def get(self, entry_id: int) -> RankingEntry:
        result = await self.session.execute(
            select(RankingEntry)
            .where(RankingEntry.id == entry_id)
            .options(selectinload(RankingEntry.athlete).selectinload(Athlete.team))
        )
        entry = result.scalar_one_or_none()
        if entry is None:
            raise NotFoundError("Ranking entry not found.")
        return entry

    async def standings(self) -> RankingStandingsRead:
        result = await self.session.execute(
            select(RankingEntry)
            .options(selectinload(RankingEntry.athlete).selectinload(Athlete.team))
            .order_by(RankingEntry.belt, RankingEntry.age_group, RankingEntry.athlete_id)
        )
        entries = list(result.scalars().all())
        totals: dict[tuple[Belt, str, int], dict[str, object]] = {}

        for entry in entries:
            key = (entry.belt, entry.age_group, entry.athlete_id)
            if key not in totals:
                totals[key] = {
                    "athlete": entry.athlete,
                    "total_points": 0,
                    "entry_count": 0,
                }
            totals[key]["total_points"] = int(totals[key]["total_points"]) + entry.points
            totals[key]["entry_count"] = int(totals[key]["entry_count"]) + 1

        grouped: dict[tuple[Belt, str], list[RankingStandingRead]] = {}
        for (belt, age_group, athlete_id), data in totals.items():
            grouped.setdefault((belt, age_group), []).append(
                RankingStandingRead(
                    position=0,
                    athlete_id=athlete_id,
                    athlete=data["athlete"],
                    belt=belt,
                    age_group=age_group,
                    total_points=int(data["total_points"]),
                    entry_count=int(data["entry_count"]),
                )
            )

        groups: list[RankingStandingGroupRead] = []
        for belt, age_group in sorted(grouped, key=lambda item: (_belt_order(item[0]), item[1])):
            ranked_athletes = sorted(
                grouped[(belt, age_group)],
                key=lambda item: (-item.total_points, item.athlete.name, item.athlete_id),
            )
            positioned = _with_ranking_positions(ranked_athletes)
            groups.append(
                RankingStandingGroupRead(
                    belt=belt,
                    age_group=age_group,
                    athletes=positioned,
                )
            )

        return RankingStandingsRead(
            groups=groups,
            total_ranked=sum(len(group.athletes) for group in groups),
        )

    async def options(
        self,
        *,
        belt: Belt | None = None,
        age_group: str | None = None,
    ) -> RankingOptionsRead:
        result = await self.session.execute(
            select(Athlete).options(selectinload(Athlete.team)).order_by(Athlete.name)
        )
        athletes = list(result.scalars().all())

        athlete_options = []
        available_belts = set()
        available_age_groups = set()
        for athlete in athletes:
            try:
                athlete_age_group = self._athlete_age_group(athlete)
            except ValidationError:
                continue

            available_belts.add(athlete.belt)
            if belt is None or athlete.belt == belt:
                available_age_groups.add(athlete_age_group)

            if belt is not None and athlete.belt != belt:
                continue
            if age_group is not None and athlete_age_group != age_group:
                continue

            athlete_options.append(
                RankingAthleteOption(
                    id=athlete.id,
                    name=athlete.name,
                    team_name=athlete.team.name,
                    belt=athlete.belt,
                    age_group=athlete_age_group,
                )
            )

        return RankingOptionsRead(
            belts=sorted(available_belts, key=str),
            age_groups=sorted(available_age_groups),
            athletes=athlete_options,
        )

    def _apply_filters(
        self,
        stmt: Select,
        *,
        belt: Belt | None,
        age_group: str | None,
        athlete_id: int | None,
    ) -> Select:
        if belt is not None:
            stmt = stmt.where(RankingEntry.belt == belt)
        if age_group:
            stmt = stmt.where(RankingEntry.age_group == age_group)
        if athlete_id is not None:
            stmt = stmt.where(RankingEntry.athlete_id == athlete_id)
        return stmt

    async def _ensure_athlete_exists(self, athlete_id: int) -> Athlete:
        result = await self.session.execute(
            select(Athlete)
            .where(Athlete.id == athlete_id)
            .options(selectinload(Athlete.team))
        )
        athlete = result.scalar_one_or_none()
        if athlete is None:
            raise NotFoundError("Athlete not found.")
        return athlete

    async def _ensure_athlete_is_registered_in_competition(
        self,
        *,
        athlete_id: int,
        competition_name: str,
    ) -> None:
        competition_result = await self.session.execute(
            select(Competition).where(func.lower(Competition.name) == competition_name.lower())
        )
        competition = competition_result.scalar_one_or_none()
        if competition is None:
            raise NotFoundError("Competition not found.")

        registration_result = await self.session.execute(
            select(CompetitionRegistration.id).where(
                CompetitionRegistration.competition_id == competition.id,
                CompetitionRegistration.athlete_id == athlete_id,
            )
        )
        if registration_result.scalar_one_or_none() is None:
            raise ValidationError(
                "Athlete must be registered in the selected competition before receiving ranking points."
            )

    def _athlete_age_group(self, athlete: Athlete) -> str:
        age = calculate_age(athlete.birth_date, date.today())
        return ibjjf_age_group(age)


def _belt_order(belt: Belt) -> int:
    return {
        Belt.white: 1,
        Belt.blue: 2,
        Belt.purple: 3,
        Belt.brown: 4,
        Belt.black: 5,
    }[belt]


def _with_ranking_positions(
    athletes: list[RankingStandingRead],
) -> list[RankingStandingRead]:
    positioned = []
    previous_points: int | None = None
    previous_position = 0
    for index, athlete in enumerate(athletes, start=1):
        position = previous_position if athlete.total_points == previous_points else index
        positioned.append(athlete.model_copy(update={"position": position}))
        previous_points = athlete.total_points
        previous_position = position
    return positioned
