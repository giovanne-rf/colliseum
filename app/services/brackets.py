from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import re

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
    CompetitionCheckin,
    Competition,
    CompetitionRegistration,
    Match,
    MatchResult,
    MatchStatus,
)
from app.models.category import Category
from app.models.common import Sex
from app.models.ranking import RankingEntry
from app.schemas.bracket import (
    CompetitionCheckinCreate,
    CompetitionFinalCheckRead,
    CompetitionCheckinLookupRead,
    CompetitionCheckinRead,
    CompetitionCreate,
    CompetitionRegistrationCreate,
    MatchResultRead,
    MatchResultUpdate,
)
from app.services.exceptions import ConflictError, NotFoundError, ValidationError
from app.tournament.brackets import (
    count_same_team_first_round_conflicts,
    generate_ibjjf_style_placements,
    next_power_of_two,
)

CHECKIN_STATUS_CHECKED = "Checked"
CHECKIN_STATUS_NO_CHECKED = "No checked"
CHECKIN_STATUS_NO_SHOW = "No Show"
CHECKIN_STATUS_OUT_OF_WEIGHT = "Out of weight"


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

    async def create_many(
        self,
        competition_id: int,
        payloads: list[CompetitionRegistrationCreate],
    ) -> list[CompetitionRegistration]:
        resolved: list[tuple[CompetitionRegistrationCreate, RegistrationOptions]] = []
        seen_athlete_ids: set[int] = set()

        for payload in payloads:
            options = await self.get_options(
                competition_id=competition_id,
                cpf=payload.cpf,
                birth_date=payload.birth_date,
            )
            if options.athlete.id in seen_athlete_ids:
                raise ConflictError("Bulk payload contains duplicate athlete registration.")

            category = await self._ensure_category_exists(payload.category_id)
            if category.id not in {option.id for option in options.categories}:
                raise ValidationError("Selected category is not eligible for this athlete.")

            seen_athlete_ids.add(options.athlete.id)
            resolved.append((payload, options))

        await self._ensure_athletes_are_not_registered(
            competition_id=competition_id,
            athlete_ids=seen_athlete_ids,
        )

        registrations = [
            CompetitionRegistration(
                competition_id=competition_id,
                athlete_id=options.athlete.id,
                category_id=payload.category_id,
            )
            for payload, options in resolved
        ]
        self.session.add_all(registrations)
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError(
                "One or more athletes are already registered in this competition."
            ) from exc

        registration_ids = [registration.id for registration in registrations]
        result = await self.session.execute(
            select(CompetitionRegistration)
            .where(CompetitionRegistration.id.in_(registration_ids))
            .options(
                selectinload(CompetitionRegistration.athlete).selectinload(Athlete.team),
                selectinload(CompetitionRegistration.category),
            )
        )
        registrations_by_id = {
            registration.id: registration for registration in result.scalars().all()
        }
        return [registrations_by_id[registration_id] for registration_id in registration_ids]

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

    async def _ensure_athletes_are_not_registered(
        self,
        *,
        competition_id: int,
        athlete_ids: set[int],
    ) -> None:
        if not athlete_ids:
            return

        result = await self.session.execute(
            select(CompetitionRegistration.athlete_id).where(
                CompetitionRegistration.competition_id == competition_id,
                CompetitionRegistration.athlete_id.in_(athlete_ids),
            )
        )
        if result.scalars().first() is not None:
            raise ConflictError("One or more athletes are already registered in this competition.")

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


class CheckinService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def lookup(self, *, competition_id: int, cpf: str) -> CompetitionCheckinLookupRead:
        registration = await self._find_registration_by_cpf(
            competition_id=competition_id,
            cpf=cpf,
        )
        checkin = await self._get_checkin_by_registration(registration.id)
        return CompetitionCheckinLookupRead(
            registration_id=registration.id,
            competition_id=registration.competition_id,
            athlete=registration.athlete,
            category=registration.category,
            max_weight_kg=max_weight_kg(registration.category.weight_class),
            status=checkin.status if checkin is not None else CHECKIN_STATUS_NO_SHOW,
            checkin=self._to_read(checkin, registration) if checkin is not None else None,
        )

    async def list_final_checks(self, competition_id: int) -> list[CompetitionFinalCheckRead]:
        await self._ensure_competition_exists(competition_id)
        registrations_result = await self.session.execute(
            select(CompetitionRegistration)
            .where(CompetitionRegistration.competition_id == competition_id)
            .options(
                selectinload(CompetitionRegistration.athlete).selectinload(Athlete.team),
                selectinload(CompetitionRegistration.category),
            )
            .order_by(CompetitionRegistration.id)
        )
        registrations = list(registrations_result.scalars().all())
        if not registrations:
            return []

        checkins_result = await self.session.execute(
            select(CompetitionCheckin).where(
                CompetitionCheckin.registration_id.in_([registration.id for registration in registrations])
            )
        )
        checkins_by_registration = {
            checkin.registration_id: checkin for checkin in checkins_result.scalars().all()
        }

        rows: list[CompetitionFinalCheckRead] = []
        for registration in registrations:
            checkin = checkins_by_registration.get(registration.id)
            checked_weight = Decimal(str(checkin.checked_weight)) if checkin is not None else None
            max_weight = max_weight_kg(registration.category.weight_class)
            rows.append(
                CompetitionFinalCheckRead(
                    registration_id=registration.id,
                    competition_id=registration.competition_id,
                    athlete=registration.athlete,
                    category=registration.category,
                    checked_weight=checked_weight,
                    status=checkin.status if checkin is not None else CHECKIN_STATUS_NO_SHOW,
                    is_overweight=(
                        checked_weight is not None
                        and max_weight is not None
                        and checked_weight > max_weight
                    ),
                )
            )
        return rows

    async def create_or_update(
        self,
        *,
        competition_id: int,
        payload: CompetitionCheckinCreate,
    ) -> CompetitionCheckinRead:
        registration = await self._get_registration(
            competition_id=competition_id,
            registration_id=payload.registration_id,
        )
        max_weight = max_weight_kg(registration.category.weight_class)
        is_overweight = max_weight is not None and payload.checked_weight > max_weight
        if is_overweight and not payload.overweight_confirmed:
            raise ValidationError("Overweight check-in requires explicit confirmation.")

        checkin = await self._get_checkin_by_registration(registration.id)
        if checkin is not None:
            raise ConflictError("Athlete has already been weighed in this competition.")

        checkin = CompetitionCheckin(
            competition_id=competition_id,
            registration_id=registration.id,
            athlete_id=registration.athlete_id,
            checked_weight=payload.checked_weight,
            gi=payload.gi,
            overweight_confirmed=payload.overweight_confirmed,
            status=CHECKIN_STATUS_OUT_OF_WEIGHT if is_overweight else CHECKIN_STATUS_NO_CHECKED,
        )
        self.session.add(checkin)

        await self.session.commit()
        await self.session.refresh(checkin)
        return self._to_read(checkin, registration)

    async def ready_to_fight(
        self,
        *,
        competition_id: int,
        registration_id: int,
    ) -> CompetitionCheckinRead:
        registration = await self._get_registration(
            competition_id=competition_id,
            registration_id=registration_id,
        )
        checkin = await self._get_checkin_by_registration(registration.id)
        if checkin is None:
            raise ValidationError("Athlete must be weighed before ready to fight.")

        max_weight = max_weight_kg(registration.category.weight_class)
        checked_weight = Decimal(str(checkin.checked_weight))
        if max_weight is not None and checked_weight > max_weight:
            checkin.status = CHECKIN_STATUS_OUT_OF_WEIGHT
            await self.session.commit()
            raise ValidationError("Athlete is not available for ready to fight because weight is over category limit.")

        checkin.status = CHECKIN_STATUS_CHECKED
        await self.session.commit()
        await self.session.refresh(checkin)
        return self._to_read(checkin, registration)

    async def not_ready_to_fight(
        self,
        *,
        competition_id: int,
        registration_id: int,
    ) -> CompetitionCheckinRead:
        registration = await self._get_registration(
            competition_id=competition_id,
            registration_id=registration_id,
        )
        checkin = await self._get_checkin_by_registration(registration.id)
        if checkin is None:
            raise ValidationError("Athlete must be weighed before not ready to fight.")

        max_weight = max_weight_kg(registration.category.weight_class)
        checked_weight = Decimal(str(checkin.checked_weight))
        checkin.status = (
            CHECKIN_STATUS_OUT_OF_WEIGHT
            if max_weight is not None and checked_weight > max_weight
            else CHECKIN_STATUS_NO_CHECKED
        )
        await self.session.commit()
        await self.session.refresh(checkin)
        return self._to_read(checkin, registration)

    async def _find_registration_by_cpf(
        self,
        *,
        competition_id: int,
        cpf: str,
    ) -> CompetitionRegistration:
        normalized_cpf = validate_and_normalize_cpf(cpf)
        result = await self.session.execute(
            select(CompetitionRegistration)
            .join(Athlete, Athlete.id == CompetitionRegistration.athlete_id)
            .where(
                CompetitionRegistration.competition_id == competition_id,
                Athlete.cpf == normalized_cpf,
            )
            .options(
                selectinload(CompetitionRegistration.athlete).selectinload(Athlete.team),
                selectinload(CompetitionRegistration.category),
            )
        )
        registration = result.scalar_one_or_none()
        if registration is None:
            raise NotFoundError("Athlete registration not found in this competition.")
        return registration

    async def _ensure_competition_exists(self, competition_id: int) -> Competition:
        competition = await self.session.get(Competition, competition_id)
        if competition is None:
            raise NotFoundError("Competition not found.")
        return competition

    async def _get_registration(
        self,
        *,
        competition_id: int,
        registration_id: int,
    ) -> CompetitionRegistration:
        result = await self.session.execute(
            select(CompetitionRegistration)
            .where(
                CompetitionRegistration.id == registration_id,
                CompetitionRegistration.competition_id == competition_id,
            )
            .options(
                selectinload(CompetitionRegistration.athlete).selectinload(Athlete.team),
                selectinload(CompetitionRegistration.category),
            )
        )
        registration = result.scalar_one_or_none()
        if registration is None:
            raise NotFoundError("Athlete registration not found in this competition.")
        return registration

    async def _get_checkin_by_registration(
        self,
        registration_id: int,
    ) -> CompetitionCheckin | None:
        result = await self.session.execute(
            select(CompetitionCheckin).where(CompetitionCheckin.registration_id == registration_id)
        )
        return result.scalar_one_or_none()

    def _to_read(
        self,
        checkin: CompetitionCheckin,
        registration: CompetitionRegistration,
    ) -> CompetitionCheckinRead:
        max_weight = max_weight_kg(registration.category.weight_class)
        checked_weight = Decimal(str(checkin.checked_weight))
        return CompetitionCheckinRead(
            id=checkin.id,
            competition_id=checkin.competition_id,
            registration_id=checkin.registration_id,
            athlete_id=checkin.athlete_id,
            checked_weight=checked_weight,
            gi=checkin.gi,
            overweight_confirmed=checkin.overweight_confirmed,
            status=checkin.status,
            is_overweight=max_weight is not None and checked_weight > max_weight,
            max_weight_kg=max_weight,
            athlete=registration.athlete,
            category=registration.category,
            created_at=checkin.created_at,
            updated_at=checkin.updated_at,
        )


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


def max_weight_kg(weight_class: str) -> Decimal | None:
    match = re.search(r"\(-\s*(\d+(?:\.\d+)?)\s*kg\)", weight_class, flags=re.IGNORECASE)
    if match is None:
        return None
    return Decimal(match.group(1))


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

        ranked_athlete_ids = await self._get_ranked_athlete_ids(
            athlete_ids={athlete.id for athlete in athletes}
        )
        placements = generate_ibjjf_style_placements(
            athletes,
            ranked_athlete_ids=ranked_athlete_ids,
        )
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
                selectinload(Bracket.matches).selectinload(Match.result),
            )
        )
        bracket = result.scalar_one_or_none()
        if bracket is None:
            raise NotFoundError("Bracket not found.")
        await self._mark_ranked_athletes(bracket)
        await self._mark_checkin_statuses(bracket)
        return bracket

    async def update_match_result(
        self,
        *,
        competition_id: int,
        match_id: int,
        payload: MatchResultUpdate,
    ) -> MatchResultRead:
        await CompetitionService(self.session).get(competition_id)
        match = await self._get_match_for_competition(competition_id=competition_id, match_id=match_id)
        if match.athlete_a_id is None or match.athlete_b_id is None:
            raise ValidationError("Both athletes are required to score a match.")

        allowed_methods = {None, "time", "submission", "disqualification"}
        if payload.finish_method not in allowed_methods:
            raise ValidationError("Invalid finish method.")

        winner_id = payload.winner_id
        if payload.finalized:
            if payload.finish_method == "time":
                winner_id = self._time_winner_id(match, payload)
            elif payload.finish_method in {"submission", "disqualification"}:
                if winner_id not in {match.athlete_a_id, match.athlete_b_id}:
                    raise ValidationError("Winner must be one of the match athletes.")
            else:
                raise ValidationError("Finish method is required to finalize a match.")

        result = await self._get_match_result(match_id)
        if result is None:
            result = MatchResult(match_id=match_id)
            self.session.add(result)

        result.athlete_a_points = payload.athlete_a_points
        result.athlete_a_advantages = payload.athlete_a_advantages
        result.athlete_a_penalties = payload.athlete_a_penalties
        result.athlete_b_points = payload.athlete_b_points
        result.athlete_b_advantages = payload.athlete_b_advantages
        result.athlete_b_penalties = payload.athlete_b_penalties
        result.finalized = payload.finalized
        result.finish_method = payload.finish_method if payload.finalized else None
        result.winner_id = winner_id if payload.finalized else None

        if payload.finalized:
            match.winner_id = result.winner_id
            match.status = MatchStatus.completed

        await self.session.commit()
        await self.session.refresh(result)
        return MatchResultRead.model_validate(result)

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

    async def _get_ranked_athlete_ids(self, athlete_ids: set[int]) -> set[int]:
        if not athlete_ids:
            return set()

        result = await self.session.execute(
            select(RankingEntry.athlete_id)
            .where(RankingEntry.athlete_id.in_(athlete_ids))
            .distinct()
        )
        return {int(athlete_id) for athlete_id in result.scalars().all()}

    async def _mark_ranked_athletes(self, bracket: Bracket) -> None:
        athletes = []
        for entry in bracket.entries:
            if entry.athlete is not None:
                athletes.append(entry.athlete)
        for match in bracket.matches:
            for athlete in (match.athlete_a, match.athlete_b, match.winner):
                if athlete is not None:
                    athletes.append(athlete)

        athletes_by_id = {athlete.id: athlete for athlete in athletes}
        ranked_athlete_ids = await self._get_ranked_athlete_ids(set(athletes_by_id))
        for athlete_id, athlete in athletes_by_id.items():
            athlete.is_ranked = athlete_id in ranked_athlete_ids

    async def _mark_checkin_statuses(self, bracket: Bracket) -> None:
        athletes = []
        for entry in bracket.entries:
            if entry.athlete is not None:
                athletes.append(entry.athlete)
        for match in bracket.matches:
            for athlete in (match.athlete_a, match.athlete_b, match.winner):
                if athlete is not None:
                    athletes.append(athlete)

        athletes_by_id = {athlete.id: athlete for athlete in athletes}
        if not athletes_by_id:
            return

        result = await self.session.execute(
            select(CompetitionCheckin.athlete_id, CompetitionCheckin.status).where(
                CompetitionCheckin.competition_id == bracket.competition_id,
                CompetitionCheckin.athlete_id.in_(athletes_by_id),
            )
        )
        statuses_by_athlete = {
            int(athlete_id): status for athlete_id, status in result.all()
        }
        for athlete_id, athlete in athletes_by_id.items():
            athlete.checkin_status = statuses_by_athlete.get(athlete_id, CHECKIN_STATUS_NO_SHOW)

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
