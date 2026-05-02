from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dates import calculate_age
from app.core.validators import validate_and_normalize_cpf
from app.models.athlete import Athlete
from app.models.bracket import (
    Bracket,
    BracketEntry,
    Competition,
    CompetitionRegistration,
    Match,
    MatchStatus,
)
from app.models.category import Category
from app.models.common import Sex
from app.schemas.bracket import CompetitionCreate, CompetitionRegistrationCreate
from app.services.exceptions import ConflictError, NotFoundError, ValidationError
from app.tournament.brackets import (
    count_same_team_first_round_conflicts,
    generate_ibjjf_style_placements,
    next_power_of_two,
)


@dataclass(frozen=True)
class RegistrationPage:
    items: list[CompetitionRegistration]


@dataclass(frozen=True)
class RegistrationOptions:
    athlete: Athlete
    competition_id: int
    age: int
    age_group: str
    categories: list[Category]


class CompetitionService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, payload: CompetitionCreate) -> Competition:
        competition = Competition(**payload.model_dump())
        self.session.add(competition)
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError("Competition with the same name already exists.") from exc

        await self.session.refresh(competition)
        return competition

    async def list(self) -> list[Competition]:
        result = await self.session.execute(select(Competition).order_by(Competition.event_date))
        return list(result.scalars().all())

    async def get(self, competition_id: int) -> Competition:
        competition = await self.session.get(Competition, competition_id)
        if competition is None:
            raise NotFoundError("Competition not found.")
        return competition


class RegistrationService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        competition_id: int,
        payload: CompetitionRegistrationCreate,
    ) -> CompetitionRegistration:
        options = await self.get_options(
            competition_id=competition_id,
            cpf=payload.cpf,
            birth_date=payload.birth_date,
        )
        category = await self._ensure_category_exists(payload.category_id)
        if category.id not in {option.id for option in options.categories}:
            raise ValidationError("Selected category is not eligible for this athlete.")

        registration = CompetitionRegistration(
            competition_id=competition_id,
            athlete_id=options.athlete.id,
            category_id=payload.category_id,
        )
        self.session.add(registration)
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError("Athlete is already registered in this competition.") from exc

        return await self.get(registration.id)

    async def list(
        self,
        competition_id: int,
        category_id: int | None = None,
    ) -> RegistrationPage:
        await self._ensure_competition_exists(competition_id)
        stmt = (
            select(CompetitionRegistration)
            .where(CompetitionRegistration.competition_id == competition_id)
            .options(
                selectinload(CompetitionRegistration.athlete).selectinload(Athlete.team),
                selectinload(CompetitionRegistration.category),
            )
            .order_by(CompetitionRegistration.id)
        )
        if category_id is not None:
            stmt = stmt.where(CompetitionRegistration.category_id == category_id)

        result = await self.session.execute(stmt)
        return RegistrationPage(items=list(result.scalars().all()))

    async def get_options(
        self,
        *,
        competition_id: int,
        cpf: str,
        birth_date: date,
    ) -> RegistrationOptions:
        competition = await self._ensure_competition_exists(competition_id)
        athlete = await self._find_athlete_by_cpf_and_birth_date(cpf=cpf, birth_date=birth_date)
        age = calculate_age(athlete.birth_date, competition.event_date)
        age_group = ibjjf_age_group(age)
        categories = await self._eligible_categories(
            athlete=athlete,
            age_group=age_group,
        )
        return RegistrationOptions(
            athlete=athlete,
            competition_id=competition_id,
            age=age,
            age_group=age_group,
            categories=categories,
        )

    async def get(self, registration_id: int) -> CompetitionRegistration:
        result = await self.session.execute(
            select(CompetitionRegistration)
            .where(CompetitionRegistration.id == registration_id)
            .options(
                selectinload(CompetitionRegistration.athlete).selectinload(Athlete.team),
                selectinload(CompetitionRegistration.category),
            )
        )
        registration = result.scalar_one_or_none()
        if registration is None:
            raise NotFoundError("Registration not found.")
        return registration

    async def _ensure_competition_exists(self, competition_id: int) -> Competition:
        competition = await self.session.get(Competition, competition_id)
        if competition is None:
            raise NotFoundError("Competition not found.")
        return competition

    async def _ensure_athlete_exists(self, athlete_id: int) -> Athlete:
        athlete = await self.session.get(Athlete, athlete_id)
        if athlete is None:
            raise NotFoundError("Athlete not found.")
        return athlete

    async def _find_athlete_by_cpf_and_birth_date(self, *, cpf: str, birth_date: date) -> Athlete:
        normalized_cpf = validate_and_normalize_cpf(cpf)
        result = await self.session.execute(
            select(Athlete)
            .where(Athlete.cpf == normalized_cpf)
            .options(selectinload(Athlete.team))
        )
        athlete = result.scalar_one_or_none()
        if athlete is None or athlete.birth_date != birth_date:
            raise ValidationError("CPF and birth date do not match an athlete registration.")
        return athlete

    async def _ensure_category_exists(self, category_id: int) -> Category:
        category = await self.session.get(Category, category_id)
        if category is None:
            raise NotFoundError("Category not found.")
        return category

    async def _eligible_categories(self, *, athlete: Athlete, age_group: str) -> list[Category]:
        sex_prefix = "Male" if athlete.sex == Sex.male else "Female"
        result = await self.session.execute(
            select(Category)
            .where(
                Category.belt == athlete.belt,
                Category.age_group == age_group,
                Category.weight_class.ilike(f"{sex_prefix} -%"),
            )
            .order_by(Category.weight_class)
        )
        return list(result.scalars().all())


def ibjjf_age_group(age: int) -> str:
    if age == 16:
        return "Juvenile 1"
    if age == 17:
        return "Juvenile 2"
    if 18 <= age <= 29:
        return "Adult"
    if 30 <= age <= 35:
        return "Master 1"
    if 36 <= age <= 40:
        return "Master 2"
    if 41 <= age <= 45:
        return "Master 3"
    if 46 <= age <= 50:
        return "Master 4"
    if 51 <= age <= 55:
        return "Master 5"
    if 56 <= age <= 60:
        return "Master 6"
    if age >= 61:
        return "Master 7"
    raise ValidationError("Athlete is too young for IBJJF competition categories.")


class BracketService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def generate(
        self,
        *,
        competition_id: int,
        category_id: int,
        replace_existing: bool = True,
    ) -> Bracket:
        await CompetitionService(self.session).get(competition_id)
        category = await self.session.get(Category, category_id)
        if category is None:
            raise NotFoundError("Category not found.")

        existing = await self._get_existing_bracket(competition_id, category_id)
        if existing is not None:
            if not replace_existing:
                raise ConflictError("Bracket already exists for this competition and category.")
            await self._delete_bracket(existing.id)

        athletes = await self._get_registered_athletes(competition_id, category_id)
        if len(athletes) < 2:
            raise ValidationError("At least two registered athletes are required to generate a bracket.")

        placements = generate_ibjjf_style_placements(athletes)
        bracket_size = next_power_of_two(len(athletes))
        rounds = bracket_size.bit_length() - 1
        bracket = Bracket(
            competition_id=competition_id,
            category_id=category_id,
            bracket_size=bracket_size,
            bye_count=bracket_size - len(athletes),
            rounds=rounds,
            same_team_conflicts=count_same_team_first_round_conflicts(placements),
        )
        self.session.add(bracket)
        await self.session.flush()

        self.session.add_all(
            [
                BracketEntry(
                    bracket_id=bracket.id,
                    position=placement.position,
                    athlete_id=placement.athlete.id if placement.athlete is not None else None,
                    team_id=placement.athlete.team_id if placement.athlete is not None else None,
                    is_bye=placement.is_bye,
                )
                for placement in placements
            ]
        )
        self.session.add_all(self._build_matches(bracket.id, placements, bracket_size))

        await self.session.commit()
        return await self.get(bracket.id)

    async def generate_all(
        self,
        *,
        competition_id: int,
        replace_existing: bool = True,
    ) -> tuple[list[Bracket], int]:
        await CompetitionService(self.session).get(competition_id)
        category_ids = await self._get_registered_category_ids(competition_id)
        brackets: list[Bracket] = []
        skipped_count = 0

        for category_id, athlete_count in category_ids:
            if athlete_count < 2:
                skipped_count += 1
                continue
            brackets.append(
                await self.generate(
                    competition_id=competition_id,
                    category_id=category_id,
                    replace_existing=replace_existing,
                )
            )

        if not brackets:
            raise ValidationError(
                "At least one category with two or more registered athletes is required."
            )

        return brackets, skipped_count

    async def get(self, bracket_id: int) -> Bracket:
        result = await self.session.execute(
            select(Bracket)
            .where(Bracket.id == bracket_id)
            .options(
                selectinload(Bracket.category),
                selectinload(Bracket.entries).selectinload(BracketEntry.athlete).selectinload(Athlete.team),
                selectinload(Bracket.matches).selectinload(Match.athlete_a).selectinload(Athlete.team),
                selectinload(Bracket.matches).selectinload(Match.athlete_b).selectinload(Athlete.team),
                selectinload(Bracket.matches).selectinload(Match.winner).selectinload(Athlete.team),
            )
        )
        bracket = result.scalar_one_or_none()
        if bracket is None:
            raise NotFoundError("Bracket not found.")
        return bracket

    async def _get_existing_bracket(self, competition_id: int, category_id: int) -> Bracket | None:
        result = await self.session.execute(
            select(Bracket).where(
                Bracket.competition_id == competition_id,
                Bracket.category_id == category_id,
            )
        )
        return result.scalar_one_or_none()

    async def _get_registered_category_ids(self, competition_id: int) -> list[tuple[int, int]]:
        result = await self.session.execute(
            select(
                CompetitionRegistration.category_id,
                func.count(CompetitionRegistration.athlete_id),
            )
            .where(CompetitionRegistration.competition_id == competition_id)
            .group_by(CompetitionRegistration.category_id)
            .order_by(CompetitionRegistration.category_id)
        )
        return [(int(category_id), int(athlete_count)) for category_id, athlete_count in result.all()]

    async def _delete_bracket(self, bracket_id: int) -> None:
        await self.session.execute(delete(Match).where(Match.bracket_id == bracket_id))
        await self.session.execute(delete(BracketEntry).where(BracketEntry.bracket_id == bracket_id))
        await self.session.execute(delete(Bracket).where(Bracket.id == bracket_id))
        await self.session.flush()

    async def _get_registered_athletes(self, competition_id: int, category_id: int) -> list[Athlete]:
        result = await self.session.execute(
            select(Athlete)
            .join(CompetitionRegistration, CompetitionRegistration.athlete_id == Athlete.id)
            .where(
                CompetitionRegistration.competition_id == competition_id,
                CompetitionRegistration.category_id == category_id,
            )
            .options(selectinload(Athlete.team))
            .order_by(Athlete.id)
        )
        return list(result.scalars().all())

    def _build_matches(
        self,
        bracket_id: int,
        placements,
        bracket_size: int,
    ) -> list[Match]:
        matches: list[Match] = []
        first_round = 1
        for index in range(0, bracket_size, 2):
            left = placements[index]
            right = placements[index + 1]
            winner_id = None
            status = MatchStatus.pending
            if left.athlete is not None and right.athlete is None:
                winner_id = left.athlete.id
                status = MatchStatus.bye
            elif right.athlete is not None and left.athlete is None:
                winner_id = right.athlete.id
                status = MatchStatus.bye

            matches.append(
                Match(
                    bracket_id=bracket_id,
                    round_number=first_round,
                    match_number=(index // 2) + 1,
                    position_start=left.position,
                    position_end=right.position,
                    athlete_a_id=left.athlete.id if left.athlete is not None else None,
                    athlete_b_id=right.athlete.id if right.athlete is not None else None,
                    winner_id=winner_id,
                    status=status,
                )
            )

        round_number = 2
        match_count = bracket_size // 4
        span = 4
        while match_count >= 1:
            for match_index in range(match_count):
                matches.append(
                    Match(
                        bracket_id=bracket_id,
                        round_number=round_number,
                        match_number=match_index + 1,
                        position_start=(match_index * span) + 1,
                        position_end=(match_index + 1) * span,
                        status=MatchStatus.pending,
                    )
                )
            round_number += 1
            match_count //= 2
            span *= 2

        return matches
