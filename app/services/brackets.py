from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
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
    CompetitionSchedule,
    CompetitionCheckin,
    CompetitionCheckinClosure,
    CompetitionCheckinControl,
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
    CompetitionCheckinClosureRead,
    CompetitionCheckinControlRead,
    CompetitionFinalCheckRead,
    CompetitionCheckinLookupRead,
    CompetitionCheckinRead,
    CompetitionCreate,
    CompetitionScheduleRead,
    CompetitionRegistrationCreate,
    MatchScheduleRead,
    MatchResultRead,
    MatchResultUpdate,
    ScheduleCategoryRead,
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
NO_FIGHTERS_FINISH_METHOD = "No fighters"
MAX_MATCHES_PER_MAT_DAY = 80
MAX_ATHLETES_PER_BRACKET = 16
BETWEEN_MATCHES_MINUTES = 3


_INVALID_FINISH_METHOD = object()
SAME_ATHLETE_REST_MINUTES = 20
_MIN_SCHEDULE_DATETIME = datetime.min.replace(tzinfo=UTC)


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
        data = payload.model_dump()
        for index in range(1, 5):
            data[f"dia_{index}"] = (
                payload.event_date + timedelta(days=index - 1)
                if index <= payload.competition_days
                else None
            )
        competition = Competition(**data)
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


class ScheduleService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_for_competition(self, competition_id: int) -> CompetitionScheduleRead:
        competition = await CompetitionService(self.session).get(competition_id)
        result = await self.session.execute(
            select(CompetitionSchedule)
            .where(CompetitionSchedule.competition_id == competition_id)
            .options(
                selectinload(CompetitionSchedule.category),
            )
            .order_by(
                CompetitionSchedule.day_number,
                CompetitionSchedule.scheduled_start,
                CompetitionSchedule.mat_number,
            )
        )
        rows = list(result.scalars().all())
        grouped: dict[int, list[CompetitionSchedule]] = {}
        for row in rows:
            grouped.setdefault(row.bracket_id, []).append(row)

        categories = []
        for bracket_rows in grouped.values():
            first = min(bracket_rows, key=lambda item: item.scheduled_start)
            categories.append(
                ScheduleCategoryRead(
                    bracket_id=first.bracket_id,
                    category_id=first.category_id,
                    category=first.category,
                    sex=_category_sex(first.category.weight_class),
                    mat_number=first.mat_number,
                    day_number=first.day_number,
                    start_time=first.scheduled_start,
                    fight_count=len(bracket_rows),
                )
            )
        categories.sort(key=lambda item: (item.day_number, item.start_time, item.sex, item.category.age_group))
        return CompetitionScheduleRead(
            competition=competition,
            categories=categories,
            matches=[MatchScheduleRead.model_validate(row) for row in rows],
        )


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
        if options.athlete.team_id is None:
            raise ValidationError("Atleta deve estar associado a uma academia antes de se inscrever na competição.")
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
        categories = list(result.scalars().all())
        if categories:
            return categories
        return await self._create_default_eligible_categories(
            athlete=athlete,
            age_group=age_group,
            sex_prefix=sex_prefix,
        )

    async def _create_default_eligible_categories(
        self,
        *,
        athlete: Athlete,
        age_group: str,
        sex_prefix: str,
    ) -> list[Category]:
        categories = [
            Category(weight_class=weight_class, belt=athlete.belt, age_group=age_group)
            for weight_class in _ibjjf_weight_classes(sex_prefix)
        ]
        self.session.add_all(categories)
        try:
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
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

        for category in categories:
            await self.session.refresh(category)
        return categories


class CheckinService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def lookup(self, *, competition_id: int, cpf: str) -> CompetitionCheckinLookupRead:
        registration = await self._find_registration_by_cpf(
            competition_id=competition_id,
            cpf=cpf,
        )
        checkin = await self._get_checkin_by_registration(registration.id)
        checkin_started = await self._is_checkin_started(
            competition_id=competition_id,
            category_id=registration.category_id,
        )
        checkin_closed = await self._is_checkin_closed(
            competition_id=competition_id,
            category_id=registration.category_id,
        )
        return CompetitionCheckinLookupRead(
            registration_id=registration.id,
            competition_id=registration.competition_id,
            athlete=registration.athlete,
            category=registration.category,
            max_weight_kg=max_weight_kg(registration.category.weight_class),
            is_super_heavy=is_super_heavy_category(registration.category.weight_class),
            checkin_started=checkin_started,
            checkin_closed=checkin_closed,
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
        closures_result = await self.session.execute(
            select(CompetitionCheckinClosure.category_id).where(
                CompetitionCheckinClosure.competition_id == competition_id
            )
        )
        closed_category_ids = {int(category_id) for category_id in closures_result.scalars().all()}
        controls_result = await self.session.execute(
            select(CompetitionCheckinControl).where(
                CompetitionCheckinControl.competition_id == competition_id
            )
        )
        controls_by_category = {
            int(control.category_id): control for control in controls_result.scalars().all()
        }

        rows: list[CompetitionFinalCheckRead] = []
        for registration in registrations:
            checkin = checkins_by_registration.get(registration.id)
            control = controls_by_category.get(registration.category_id)
            checked_weight = Decimal(str(checkin.checked_weight)) if checkin is not None else None
            max_weight = max_weight_kg(registration.category.weight_class)
            is_super_heavy = is_super_heavy_category(registration.category.weight_class)
            status = checkin.status if checkin is not None else CHECKIN_STATUS_NO_SHOW
            if (
                registration.category_id in closed_category_ids
                and status not in {CHECKIN_STATUS_CHECKED, CHECKIN_STATUS_OUT_OF_WEIGHT}
            ):
                status = CHECKIN_STATUS_NO_SHOW
            rows.append(
                CompetitionFinalCheckRead(
                    registration_id=registration.id,
                    competition_id=registration.competition_id,
                    athlete=registration.athlete,
                    category=registration.category,
                    checked_weight=checked_weight,
                    weight_display="Pesadíssimo" if is_super_heavy and checkin is not None else None,
                    status=status,
                    is_overweight=(
                        checked_weight is not None
                        and max_weight is not None
                        and checked_weight > max_weight
                    ),
                    checkin_started=control is not None,
                    checkin_started_at=control.started_at if control is not None else None,
                    checkin_closed=registration.category_id in closed_category_ids,
                    checkin_closed_at=control.closed_at if control is not None else None,
                )
            )
        return rows

    async def start_category_checkin(
        self,
        *,
        competition_id: int,
        category_id: int,
    ) -> CompetitionCheckinControlRead:
        await self._ensure_competition_exists(competition_id)
        await self._ensure_bracket_generated(competition_id=competition_id, category_id=category_id)
        category = await self.session.get(Category, category_id)
        if category is None:
            raise NotFoundError("Category not found.")

        existing = await self._get_checkin_control(
            competition_id=competition_id,
            category_id=category_id,
        )
        if existing is not None:
            return CompetitionCheckinControlRead(
                id=existing.id,
                competition_id=existing.competition_id,
                category_id=existing.category_id,
                category=category,
                started_at=existing.started_at,
                closed_at=existing.closed_at,
            )

        control = CompetitionCheckinControl(
            competition_id=competition_id,
            category_id=category_id,
        )
        self.session.add(control)
        await self.session.commit()
        await self.session.refresh(control)
        return CompetitionCheckinControlRead(
            id=control.id,
            competition_id=control.competition_id,
            category_id=control.category_id,
            category=category,
            started_at=control.started_at,
            closed_at=control.closed_at,
        )

    async def close_category_checkin(
        self,
        *,
        competition_id: int,
        category_id: int,
    ) -> CompetitionCheckinClosureRead:
        await self._ensure_competition_exists(competition_id)
        await self._ensure_bracket_generated(competition_id=competition_id, category_id=category_id)

        category = await self.session.get(Category, category_id)
        if category is None:
            raise NotFoundError("Category not found.")

        existing = await self._get_checkin_closure(
            competition_id=competition_id,
            category_id=category_id,
        )
        if existing is not None:
            return CompetitionCheckinClosureRead(
                id=existing.id,
                competition_id=existing.competition_id,
                category_id=existing.category_id,
                category=category,
                closed_at=existing.closed_at,
            )

        control = await self._get_checkin_control(
            competition_id=competition_id,
            category_id=category_id,
        )
        if control is None:
            raise ValidationError("Checkin ainda nao iniciado para esta categoria.")

        control.closed_at = datetime.now(UTC)
        closure = CompetitionCheckinClosure(
            competition_id=competition_id,
            category_id=category_id,
        )
        self.session.add(closure)
        await self.session.flush()
        await BracketService(self.session).advance_status_walkovers_for_competition(
            competition_id=competition_id,
        )
        await self.session.commit()
        await self.session.refresh(closure)
        return CompetitionCheckinClosureRead(
            id=closure.id,
            competition_id=closure.competition_id,
            category_id=closure.category_id,
            category=category,
            closed_at=closure.closed_at,
        )

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
        await self._ensure_bracket_generated_for_registration(registration)
        await self._ensure_checkin_is_open(registration)
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
        if checkin.status == CHECKIN_STATUS_OUT_OF_WEIGHT:
            await self.session.flush()
            await BracketService(self.session).advance_status_walkovers_for_competition(
                competition_id=competition_id,
            )

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
        await self._ensure_bracket_generated_for_registration(registration)
        await self._ensure_checkin_is_open(registration)
        checkin = await self._get_checkin_by_registration(registration.id)
        if checkin is None:
            if not is_super_heavy_category(registration.category.weight_class):
                raise ValidationError("Athlete must be weighed before ready to fight.")
            checkin = CompetitionCheckin(
                competition_id=competition_id,
                registration_id=registration.id,
                athlete_id=registration.athlete_id,
                checked_weight=Decimal("0.00"),
                gi=True,
                overweight_confirmed=False,
                status=CHECKIN_STATUS_NO_CHECKED,
            )
            self.session.add(checkin)
            await self.session.flush()

        max_weight = max_weight_kg(registration.category.weight_class)
        checked_weight = Decimal(str(checkin.checked_weight))
        if max_weight is not None and checked_weight > max_weight:
            checkin.status = CHECKIN_STATUS_OUT_OF_WEIGHT
            await self.session.commit()
            raise ValidationError("Athlete is not available for ready to fight because weight is over category limit.")

        checkin.status = CHECKIN_STATUS_CHECKED
        await self.session.flush()
        bracket_service = BracketService(self.session)
        await bracket_service.advance_checked_byes_for_athlete(
            competition_id=competition_id,
            athlete_id=registration.athlete_id,
        )
        await bracket_service.advance_status_walkovers_for_competition(
            competition_id=competition_id,
        )
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
        await self._ensure_bracket_generated_for_registration(registration)
        await self._ensure_checkin_is_open(registration)
        checkin = await self._get_checkin_by_registration(registration.id)
        if checkin is None:
            if not is_super_heavy_category(registration.category.weight_class):
                raise ValidationError("Athlete must be weighed before not ready to fight.")
            checkin = CompetitionCheckin(
                competition_id=competition_id,
                registration_id=registration.id,
                athlete_id=registration.athlete_id,
                checked_weight=Decimal("0.00"),
                gi=True,
                overweight_confirmed=False,
                status=CHECKIN_STATUS_NO_CHECKED,
            )
            self.session.add(checkin)
            await self.session.flush()

        max_weight = max_weight_kg(registration.category.weight_class)
        checked_weight = Decimal(str(checkin.checked_weight))
        checkin.status = (
            CHECKIN_STATUS_OUT_OF_WEIGHT
            if max_weight is not None and checked_weight > max_weight
            else CHECKIN_STATUS_NO_CHECKED
        )
        if checkin.status == CHECKIN_STATUS_OUT_OF_WEIGHT:
            await self.session.flush()
            await BracketService(self.session).advance_status_walkovers_for_competition(
                competition_id=competition_id,
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

    async def _get_checkin_closure(
        self,
        *,
        competition_id: int,
        category_id: int,
    ) -> CompetitionCheckinClosure | None:
        result = await self.session.execute(
            select(CompetitionCheckinClosure).where(
                CompetitionCheckinClosure.competition_id == competition_id,
                CompetitionCheckinClosure.category_id == category_id,
            )
        )
        return result.scalar_one_or_none()

    async def _get_checkin_control(
        self,
        *,
        competition_id: int,
        category_id: int,
    ) -> CompetitionCheckinControl | None:
        result = await self.session.execute(
            select(CompetitionCheckinControl).where(
                CompetitionCheckinControl.competition_id == competition_id,
                CompetitionCheckinControl.category_id == category_id,
            )
        )
        return result.scalar_one_or_none()

    async def _is_checkin_started(self, *, competition_id: int, category_id: int) -> bool:
        return await self._get_checkin_control(
            competition_id=competition_id,
            category_id=category_id,
        ) is not None

    async def _is_checkin_closed(self, *, competition_id: int, category_id: int) -> bool:
        return await self._get_checkin_closure(
            competition_id=competition_id,
            category_id=category_id,
        ) is not None

    async def _ensure_checkin_is_open(self, registration: CompetitionRegistration) -> None:
        if await self._is_checkin_closed(
            competition_id=registration.competition_id,
            category_id=registration.category_id,
        ):
            raise ValidationError("Checkin encerrado.")
        if not await self._is_checkin_started(
            competition_id=registration.competition_id,
            category_id=registration.category_id,
        ):
            raise ValidationError("Checkin ainda nao iniciado para esta categoria.")

    async def _ensure_bracket_generated(self, *, competition_id: int, category_id: int) -> None:
        result = await self.session.execute(
            select(Bracket.id).where(
                Bracket.competition_id == competition_id,
                Bracket.category_id == category_id,
            )
        )
        if result.scalar_one_or_none() is None:
            raise ValidationError("Bracket must be generated before category check-in.")

    async def _ensure_bracket_generated_for_registration(
        self,
        registration: CompetitionRegistration,
    ) -> None:
        result = await self.session.execute(
            select(Bracket.id).where(
                Bracket.competition_id == registration.competition_id,
                Bracket.category_id == registration.category_id,
            )
        )
        if result.scalar_one_or_none() is None:
            raise ValidationError(
                "Bracket must be generated before athlete weigh-in or check-in."
            )

    def _to_read(
        self,
        checkin: CompetitionCheckin,
        registration: CompetitionRegistration,
    ) -> CompetitionCheckinRead:
        max_weight = max_weight_kg(registration.category.weight_class)
        checked_weight = Decimal(str(checkin.checked_weight))
        is_super_heavy = is_super_heavy_category(registration.category.weight_class)
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
            weight_display="Pesadíssimo" if is_super_heavy else None,
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


def _ibjjf_weight_classes(sex_prefix: str) -> list[str]:
    if sex_prefix == "Female":
        return [
            "Female - Rooster (-48.5 kg)",
            "Female - Light Feather (-53.5 kg)",
            "Female - Feather (-58.5 kg)",
            "Female - Light (-64.0 kg)",
            "Female - Middle (-69.0 kg)",
            "Female - Medium Heavy (-74.0 kg)",
            "Female - Heavy (-79.3 kg)",
            "Female - Super Heavy (+79.3 kg)",
        ]
    return [
        "Male - Rooster (-57.5 kg)",
        "Male - Light Feather (-64.0 kg)",
        "Male - Feather (-70.0 kg)",
        "Male - Light (-76.0 kg)",
        "Male - Middle (-82.3 kg)",
        "Male - Medium Heavy (-88.3 kg)",
        "Male - Heavy (-94.3 kg)",
        "Male - Super Heavy (-100.5 kg)",
        "Male - Ultra Heavy (+100.5 kg)",
    ]


def _normalize_finish_method(value: str | None) -> str | None | object:
    if value is None:
        return None
    aliases = {
        "Pontos": "Pontos",
        "Finalização": "Finalização",
        "Finalizacao": "Finalização",
        "Desclassificação do oponente": "Desclassificação do oponente",
        "Desclassificacao do oponente": "Desclassificação do oponente",
    }
    return aliases.get(value, _INVALID_FINISH_METHOD)


def max_weight_kg(weight_class: str) -> Decimal | None:
    match = re.search(r"\(-\s*(\d+(?:\.\d+)?)\s*kg\)", weight_class, flags=re.IGNORECASE)
    if match is None:
        return None
    return Decimal(match.group(1))


def is_super_heavy_category(weight_class: str) -> bool:
    normalized = (
        weight_class.casefold()
        .replace("í", "i")
        .replace("é", "e")
        .replace("-", " ")
    )
    return any(
        marker in normalized
        for marker in ("super pesado", "super heavy", "ultra heavy", "pesadissimo")
    )


def _parse_start_time(value: str) -> time:
    hour, minute = value.split(":", 1)
    return time(hour=int(hour), minute=int(minute))


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _category_sex(weight_class: str) -> str:
    normalized = weight_class.lower()
    if "female" in normalized or "feminino" in normalized:
        return "female"
    if "male" in normalized or "masculino" in normalized:
        return "male"
    return "male"


def _fight_duration_minutes(category: Category) -> int:
    belt = str(category.belt)
    age_group = category.age_group.lower()
    if age_group == "adult":
        return {
            "white": 5,
            "blue": 6,
            "purple": 7,
            "brown": 8,
            "black": 10,
        }.get(belt, 5)
    if "juven" in age_group:
        return 5
    if "master 1" in age_group:
        return 6 if belt in {"purple", "brown", "black"} else 5
    if "master" in age_group:
        return 5
    return 5


class BracketService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def generate(
        self,
        *,
        competition_id: int,
        category_id: int,
        replace_existing: bool = False,
    ) -> list[Bracket]:
        _ = replace_existing
        competition = await CompetitionService(self.session).get(competition_id)
        category = await self.session.get(Category, category_id)
        if category is None:
            raise NotFoundError("Category not found.")

        existing = await self._get_existing_bracket(competition_id, category_id)
        if existing is not None:
            raise ConflictError("Bracket already exists for this competition and category.")

        athletes = await self._get_registered_athletes(competition_id, category_id)
        if len(athletes) < 2:
            raise ValidationError("At least two registered athletes are required to generate a bracket.")

        ranked_athlete_ids = await self._get_ranked_athlete_ids(
            athlete_ids={athlete.id for athlete in athletes}
        )
        athlete_groups = self._split_athletes_for_brackets(
            athletes,
            ranked_athlete_ids=ranked_athlete_ids,
        )
        bracket_ids: list[int] = []
        for group in athlete_groups:
            bracket = await self._create_single_bracket(
                competition=competition,
                category=category,
                athletes=group,
                ranked_athlete_ids=ranked_athlete_ids,
            )
            bracket_ids.append(bracket.id)

        await self.advance_status_walkovers_for_competition(competition_id=competition_id)
        await self.session.commit()
        return [await self.get(bracket_id) for bracket_id in bracket_ids]

    async def _create_single_bracket(
        self,
        *,
        competition: Competition,
        category: Category,
        athletes: list[Athlete],
        ranked_athlete_ids: set[int],
    ) -> Bracket:
        placements = generate_ibjjf_style_placements(
            athletes,
            ranked_athlete_ids=ranked_athlete_ids,
        )
        bracket_size = next_power_of_two(len(athletes))
        rounds = bracket_size.bit_length() - 1
        bracket = Bracket(
            competition_id=competition.id,
            category_id=category.id,
            bracket_size=bracket_size,
            bye_count=bracket_size - len(athletes),
            rounds=rounds,
            same_team_conflicts=count_same_team_first_round_conflicts(placements),
        )
        self.session.add(bracket)
        await self.session.flush()

        checked_athlete_ids = await self._get_checked_athlete_ids(
            competition_id=competition.id,
            athlete_ids={athlete.id for athlete in athletes},
        )

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
        matches = self._build_matches(bracket.id, placements, bracket_size)
        self._advance_bye_winners(matches, checked_athlete_ids=checked_athlete_ids)
        self.session.add_all(matches)
        await self.session.flush()
        await self._schedule_matches(
            competition=competition,
            bracket=bracket,
            category=category,
            matches=matches,
        )
        await self.session.flush()
        return bracket

    async def generate_all(
        self,
        *,
        competition_id: int,
        replace_existing: bool = False,
    ) -> tuple[list[Bracket], int]:
        _ = replace_existing
        await CompetitionService(self.session).get(competition_id)
        category_ids = await self._get_registered_category_ids(competition_id)
        brackets: list[Bracket] = []
        skipped_count = 0

        for category_id, athlete_count in category_ids:
            if athlete_count < 2:
                skipped_count += 1
                continue
            if await self._get_existing_bracket(competition_id, category_id) is not None:
                skipped_count += 1
                continue
            brackets.extend(
                await self.generate(
                    competition_id=competition_id,
                    category_id=category_id,
                    replace_existing=False,
                )
            )

        if not brackets:
            raise ValidationError(
                "At least one category with two or more registered athletes is required."
            )

        return brackets, skipped_count

    @staticmethod
    def _split_athletes_for_brackets(
        athletes: list[Athlete],
        *,
        ranked_athlete_ids: set[int],
    ) -> list[list[Athlete]]:
        if len(athletes) <= MAX_ATHLETES_PER_BRACKET:
            return [athletes]

        bracket_count = (len(athletes) + MAX_ATHLETES_PER_BRACKET - 1) // MAX_ATHLETES_PER_BRACKET
        groups: list[list[Athlete]] = [[] for _ in range(bracket_count)]
        team_counts: dict[int | None, int] = {}
        for athlete in athletes:
            team_counts[athlete.team_id] = team_counts.get(athlete.team_id, 0) + 1

        ordered_athletes = sorted(
            athletes,
            key=lambda athlete: (
                athlete.id not in ranked_athlete_ids,
                -team_counts.get(athlete.team_id, 0),
                athlete.team_id or 0,
                athlete.name,
                athlete.id,
            ),
        )

        for athlete in ordered_athletes:
            available_indexes = [
                index
                for index, group in enumerate(groups)
                if len(group) < MAX_ATHLETES_PER_BRACKET
            ]
            best_index = min(
                available_indexes,
                key=lambda index: (
                    sum(1 for item in groups[index] if item.team_id == athlete.team_id),
                    len(groups[index]),
                    index,
                ),
            )
            groups[best_index].append(athlete)

        return groups
    async def list_for_competition(self, competition_id: int) -> list[Bracket]:
        await CompetitionService(self.session).get(competition_id)
        result = await self.session.execute(
            select(Bracket)
            .where(Bracket.competition_id == competition_id)
            .options(
                selectinload(Bracket.category),
                selectinload(Bracket.entries).selectinload(BracketEntry.athlete).selectinload(Athlete.team),
                selectinload(Bracket.matches).selectinload(Match.athlete_a).selectinload(Athlete.team),
                selectinload(Bracket.matches).selectinload(Match.athlete_b).selectinload(Athlete.team),
                selectinload(Bracket.matches).selectinload(Match.winner).selectinload(Athlete.team),
                selectinload(Bracket.matches).selectinload(Match.result),
                selectinload(Bracket.matches).selectinload(Match.schedule),
            )
            .order_by(Bracket.id)
        )
        brackets = list(result.scalars().all())
        for bracket in brackets:
            await self._mark_ranked_athletes(bracket)
            await self._mark_checkin_statuses(bracket)
        return brackets

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
                selectinload(Bracket.matches).selectinload(Match.schedule),
            )
        )
        bracket = result.scalar_one_or_none()
        if bracket is None:
            raise NotFoundError("Bracket not found.")
        await self._mark_ranked_athletes(bracket)
        await self._mark_checkin_statuses(bracket)
        return bracket

    async def delete(self, bracket_id: int) -> None:
        bracket = await self.session.get(Bracket, bracket_id)
        if bracket is None:
            raise NotFoundError("Bracket not found.")
        await self._delete_bracket(bracket_id)
        await self.session.commit()

    async def delete_all(self, competition_id: int) -> None:
        await CompetitionService(self.session).get(competition_id)
        result = await self.session.execute(
            select(Bracket.id).where(Bracket.competition_id == competition_id)
        )
        for bracket_id in result.scalars().all():
            await self._delete_bracket(int(bracket_id))
        await self._clear_competition_checkin_state(competition_id)
        await self.session.commit()

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

        finish_method = _normalize_finish_method(payload.finish_method)
        if finish_method is _INVALID_FINISH_METHOD:
            raise ValidationError("Invalid finish method.")

        winner_id = payload.winner_id
        if payload.finalized:
            if finish_method == "Pontos":
                winner_id = self._time_winner_id(match, payload)
            elif finish_method in {"Finalização", "Desclassificação do oponente"}:
                if winner_id not in {match.athlete_a_id, match.athlete_b_id}:
                    raise ValidationError("Winner must be one of the match athletes.")
            else:
                raise ValidationError("Finish method is required to finalize a match.")

        result = await self._get_match_result(match_id)
        if result is not None and result.finalized:
            raise ConflictError("Match is already finalized.")
        if result is None:
            result = MatchResult(match_id=match_id)
            self.session.add(result)

        result.athlete_a_points = payload.athlete_a_points
        result.athlete_a_advantages = payload.athlete_a_advantages
        result.athlete_a_penalties = payload.athlete_a_penalties
        result.athlete_b_points = payload.athlete_b_points
        result.athlete_b_advantages = payload.athlete_b_advantages
        result.athlete_b_penalties = payload.athlete_b_penalties
        if payload.start_match and result.started_at is None:
            result.started_at = datetime.now(UTC)
        result.finalized = payload.finalized
        result.finish_method = finish_method if payload.finalized else None
        result.winner_id = winner_id if payload.finalized else None
        if payload.finalized and result.started_at is None:
            result.started_at = datetime.now(UTC)
        result.finished_at = datetime.now(UTC) if payload.finalized else None

        if payload.finalized:
            match.winner_id = winner_id
            match.status = MatchStatus.completed
            await self.session.flush()
            await self._advance_available_winners(match.bracket_id)
            await self.session.flush()
            await self._reschedule_mat_after_finished_match(
                competition_id=competition_id,
                match_id=match_id,
                finished_at=result.finished_at,
            )

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

    async def _get_match_for_competition(self, *, competition_id: int, match_id: int) -> Match:
        result = await self.session.execute(
            select(Match)
            .join(Bracket, Bracket.id == Match.bracket_id)
            .where(Match.id == match_id, Bracket.competition_id == competition_id)
        )
        match = result.scalar_one_or_none()
        if match is None:
            raise NotFoundError("Match not found.")
        return match

    async def _get_match_result(self, match_id: int) -> MatchResult | None:
        result = await self.session.execute(
            select(MatchResult).where(MatchResult.match_id == match_id)
        )
        return result.scalar_one_or_none()

    async def _schedule_matches(
        self,
        *,
        competition: Competition,
        bracket: Bracket,
        category: Category,
        matches: list[Match],
    ) -> None:
        result = await self.session.execute(
            select(CompetitionSchedule)
            .where(CompetitionSchedule.competition_id == competition.id)
            .options(selectinload(CompetitionSchedule.match))
            .order_by(CompetitionSchedule.day_number, CompetitionSchedule.mat_number)
        )
        existing_rows = list(result.scalars().all())
        day_count = max(1, min(competition.competition_days, 4))
        start_clock = _parse_start_time(competition.start_time)
        mat_states: dict[tuple[int, int], dict[str, object]] = {}
        for day_number in range(1, day_count + 1):
            day_date = getattr(competition, f"dia_{day_number}") or (
                competition.event_date + timedelta(days=day_number - 1)
            )
            start_at = _as_utc(datetime.combine(day_date, start_clock))
            for mat_number in range(1, competition.mat_count + 1):
                mat_states[(day_number, mat_number)] = {"count": 0, "next": start_at}

        category_mat = None
        athlete_available: dict[int, datetime] = {}
        for row in existing_rows:
            key = (row.day_number, row.mat_number)
            state = mat_states.get(key)
            if state is None:
                continue
            state["count"] = int(state["count"]) + 1
            row_start = _as_utc(row.scheduled_start)
            row_finish = row_start + timedelta(minutes=row.estimated_minutes)
            row_next = row_finish + timedelta(minutes=BETWEEN_MATCHES_MINUTES)
            if row_next > state["next"]:
                state["next"] = row_next
            if row.category_id == category.id:
                category_mat = row.mat_number
            if row.match is not None:
                for athlete_id in (row.match.athlete_a_id, row.match.athlete_b_id):
                    if athlete_id is None:
                        continue
                    ready_at = row_finish + timedelta(minutes=SAME_ATHLETE_REST_MINUTES)
                    athlete_available[athlete_id] = max(
                        athlete_available.get(athlete_id, _MIN_SCHEDULE_DATETIME),
                        ready_at,
                    )

        estimated_minutes = _fight_duration_minutes(category)
        ordered_matches = sorted(matches, key=lambda item: (item.round_number, item.match_number))
        for match in ordered_matches:
            mat_options = list(mat_states)
            if category_mat is not None:
                preferred = [
                    key
                    for key in mat_options
                    if key[1] == category_mat
                    and int(mat_states[key]["count"]) < MAX_MATCHES_PER_MAT_DAY
                ]
                if preferred:
                    mat_options = preferred

            athlete_ids = [
                athlete_id
                for athlete_id in (match.athlete_a_id, match.athlete_b_id)
                if athlete_id is not None
            ]
            rest_ready_at = max(
                [
                    athlete_available.get(athlete_id, _MIN_SCHEDULE_DATETIME)
                    for athlete_id in athlete_ids
                ],
                default=_MIN_SCHEDULE_DATETIME,
            )
            candidates = []
            for key in mat_options:
                state = mat_states[key]
                if int(state["count"]) >= MAX_MATCHES_PER_MAT_DAY:
                    continue
                candidates.append((_as_utc(max(state["next"], rest_ready_at)), int(state["count"]), key))
            if not candidates:
                raise ValidationError("Competition schedule has no available MAT slots.")

            scheduled_start, _, (day_number, mat_number) = min(
                candidates,
                key=lambda item: (item[0], item[1], item[2][0], item[2][1]),
            )
            if category_mat is None:
                category_mat = mat_number

            schedule = CompetitionSchedule(
                competition_id=competition.id,
                bracket_id=bracket.id,
                category_id=category.id,
                match_id=match.id,
                mat_number=mat_number,
                day_number=day_number,
                scheduled_start=scheduled_start,
                estimated_minutes=estimated_minutes,
            )
            self.session.add(schedule)
            state = mat_states[(day_number, mat_number)]
            state["count"] = int(state["count"]) + 1
            estimated_finish = scheduled_start + timedelta(minutes=estimated_minutes)
            state["next"] = estimated_finish + timedelta(minutes=BETWEEN_MATCHES_MINUTES)
            for athlete_id in athlete_ids:
                athlete_available[athlete_id] = estimated_finish + timedelta(
                    minutes=SAME_ATHLETE_REST_MINUTES
                )

    async def _reschedule_mat_after_finished_match(
        self,
        *,
        competition_id: int,
        match_id: int,
        finished_at: datetime | None,
    ) -> None:
        if finished_at is None:
            return
        finished_at = _as_utc(finished_at)

        current_result = await self.session.execute(
            select(CompetitionSchedule)
            .where(
                CompetitionSchedule.competition_id == competition_id,
                CompetitionSchedule.match_id == match_id,
            )
            .options(selectinload(CompetitionSchedule.match))
        )
        current_schedule = current_result.scalar_one_or_none()
        if current_schedule is None:
            return

        rows_result = await self.session.execute(
            select(CompetitionSchedule)
            .where(
                CompetitionSchedule.competition_id == competition_id,
                CompetitionSchedule.day_number == current_schedule.day_number,
                CompetitionSchedule.mat_number == current_schedule.mat_number,
                CompetitionSchedule.scheduled_start > current_schedule.scheduled_start,
            )
            .options(
                selectinload(CompetitionSchedule.match).selectinload(Match.result),
            )
            .order_by(CompetitionSchedule.scheduled_start, CompetitionSchedule.id)
        )
        rows = list(rows_result.scalars().all())
        if not rows:
            return

        athlete_available: dict[int, datetime] = {}
        current_match = current_schedule.match
        for athlete_id in (current_match.athlete_a_id, current_match.athlete_b_id):
            if athlete_id is not None:
                athlete_available[athlete_id] = finished_at + timedelta(
                    minutes=SAME_ATHLETE_REST_MINUTES
                )

        next_start = finished_at + timedelta(minutes=BETWEEN_MATCHES_MINUTES)
        for row in rows:
            match = row.match
            match_result = match.result
            if match_result is not None and match_result.finalized:
                actual_finish = _as_utc(
                    match_result.finished_at
                    or (row.scheduled_start + timedelta(minutes=row.estimated_minutes))
                )
                next_start = max(
                    next_start,
                    actual_finish + timedelta(minutes=BETWEEN_MATCHES_MINUTES),
                )
                for athlete_id in (match.athlete_a_id, match.athlete_b_id):
                    if athlete_id is not None:
                        athlete_available[athlete_id] = actual_finish + timedelta(
                            minutes=SAME_ATHLETE_REST_MINUTES
                        )
                continue

            athlete_ids = [
                athlete_id
                for athlete_id in (match.athlete_a_id, match.athlete_b_id)
                if athlete_id is not None
            ]
            rest_ready_at = max(
                [
                    athlete_available.get(athlete_id, _MIN_SCHEDULE_DATETIME)
                    for athlete_id in athlete_ids
                ],
                default=_MIN_SCHEDULE_DATETIME,
            )
            row.scheduled_start = max(next_start, rest_ready_at)
            estimated_finish = row.scheduled_start + timedelta(minutes=row.estimated_minutes)
            next_start = estimated_finish + timedelta(minutes=BETWEEN_MATCHES_MINUTES)
            for athlete_id in athlete_ids:
                athlete_available[athlete_id] = estimated_finish + timedelta(
                    minutes=SAME_ATHLETE_REST_MINUTES
                )

    async def advance_checked_byes_for_athlete(self, *, competition_id: int, athlete_id: int) -> None:
        result = await self.session.execute(
            select(Match)
            .join(Bracket, Bracket.id == Match.bracket_id)
            .where(
                Bracket.competition_id == competition_id,
                Match.status == MatchStatus.bye,
                Match.winner_id == athlete_id,
            )
        )
        for match in result.scalars().all():
            await self._advance_winner(match=match, winner_id=athlete_id)

    async def advance_status_walkovers_for_competition(self, *, competition_id: int) -> None:
        result = await self.session.execute(
            select(Bracket.id).where(Bracket.competition_id == competition_id)
        )
        for bracket_id in result.scalars().all():
            await self._advance_status_walkovers_for_bracket(bracket_id)

    async def _advance_status_walkovers_for_bracket(self, bracket_id: int) -> None:
        bracket = await self.session.get(Bracket, bracket_id)
        if bracket is None:
            return

        result = await self.session.execute(
            select(Match)
            .where(Match.bracket_id == bracket_id)
            .order_by(Match.round_number, Match.match_number)
        )
        matches = list(result.scalars().all())
        if not matches:
            return

        athlete_ids = {
            athlete_id
            for match in matches
            for athlete_id in (match.athlete_a_id, match.athlete_b_id)
            if athlete_id is not None
        }
        statuses = await self._get_checkin_statuses(
            competition_id=bracket.competition_id,
            athlete_ids=athlete_ids,
        )
        checkin_closed = await self._is_category_checkin_closed(
            competition_id=bracket.competition_id,
            category_id=bracket.category_id,
        )

        changed = True
        while changed:
            changed = False
            for match in matches:
                if match.winner_id is not None or match.status == MatchStatus.completed:
                    continue
                winner_id = self._walkover_winner_id(
                    match,
                    statuses,
                    matches=matches,
                    no_show_is_unavailable=checkin_closed,
                )
                if winner_id is None:
                    if self._match_has_no_fighters(
                        match,
                        statuses,
                        no_show_is_unavailable=checkin_closed,
                    ):
                        match.status = MatchStatus.completed
                        await self._upsert_automatic_match_result(
                            match=match,
                            winner_id=None,
                            finish_method=NO_FIGHTERS_FINISH_METHOD,
                        )
                        changed = True
                    continue
                match.winner_id = winner_id
                match.status = MatchStatus.completed
                await self._upsert_automatic_match_result(
                    match=match,
                    winner_id=winner_id,
                    finish_method=NO_FIGHTERS_FINISH_METHOD,
                )
                await self._advance_winner(match=match, winner_id=winner_id)
                changed = True

    async def _advance_available_winners(self, bracket_id: int) -> None:
        bracket = await self.session.get(Bracket, bracket_id)
        if bracket is None:
            return

        result = await self.session.execute(
            select(Match)
            .where(Match.bracket_id == bracket_id)
            .order_by(Match.round_number, Match.match_number)
        )
        matches = list(result.scalars().all())
        await self._sync_finalized_match_results(matches)
        checked_athlete_ids = await self._get_checked_athlete_ids(
            competition_id=bracket.competition_id,
            athlete_ids={match.winner_id for match in matches if match.winner_id is not None},
        )
        for match in matches:
            if match.winner_id is None:
                continue
            if match.status == MatchStatus.completed or (
                match.status == MatchStatus.bye and match.winner_id in checked_athlete_ids
            ):
                await self._advance_winner(match=match, winner_id=match.winner_id)

    async def _sync_finalized_match_results(self, matches: list[Match]) -> None:
        match_ids = [match.id for match in matches]
        if not match_ids:
            return

        result = await self.session.execute(
            select(MatchResult).where(
                MatchResult.match_id.in_(match_ids),
                MatchResult.finalized.is_(True),
                MatchResult.winner_id.is_not(None),
            )
        )
        results_by_match = {
            match_result.match_id: match_result for match_result in result.scalars().all()
        }
        for match in matches:
            match_result = results_by_match.get(match.id)
            if match_result is None:
                continue
            match.winner_id = match_result.winner_id
            match.status = MatchStatus.completed

    async def _advance_winner(self, *, match: Match, winner_id: int | None) -> None:
        if winner_id is None:
            return

        next_result = await self.session.execute(
            select(Match)
            .where(
                Match.bracket_id == match.bracket_id,
                Match.round_number == match.round_number + 1,
                Match.position_start <= match.position_start,
                Match.position_end >= match.position_end,
            )
            .order_by(Match.position_end - Match.position_start)
        )
        next_match = next_result.scalars().first()
        if next_match is None:
            return

        middle = (next_match.position_start + next_match.position_end) // 2
        if match.position_end <= middle:
            if next_match.athlete_a_id is None:
                next_match.athlete_a_id = winner_id
        else:
            if next_match.athlete_b_id is None:
                next_match.athlete_b_id = winner_id

    @staticmethod
    def _time_winner_id(match: Match, payload: MatchResultUpdate) -> int:
        comparisons = [
            (payload.athlete_a_points, payload.athlete_b_points, True),
            (payload.athlete_a_advantages, payload.athlete_b_advantages, True),
            (payload.athlete_a_penalties, payload.athlete_b_penalties, False),
        ]
        for left, right, higher_wins in comparisons:
            if left == right:
                continue
            if higher_wins:
                return match.athlete_a_id if left > right else match.athlete_b_id
            return match.athlete_a_id if left < right else match.athlete_b_id
        raise ValidationError("Time result is tied after points, advantages, and penalties.")

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

    async def _clear_competition_checkin_state(self, competition_id: int) -> None:
        await self.session.execute(
            delete(CompetitionSchedule).where(CompetitionSchedule.competition_id == competition_id)
        )
        await self.session.execute(
            delete(CompetitionCheckin).where(CompetitionCheckin.competition_id == competition_id)
        )
        await self.session.execute(
            delete(CompetitionCheckinClosure).where(
                CompetitionCheckinClosure.competition_id == competition_id
            )
        )
        await self.session.execute(
            delete(CompetitionCheckinControl).where(
                CompetitionCheckinControl.competition_id == competition_id
            )
        )
        await self.session.flush()

    async def _delete_bracket(self, bracket_id: int) -> None:
        match_ids_result = await self.session.execute(
            select(Match.id).where(Match.bracket_id == bracket_id)
        )
        match_ids = [int(match_id) for match_id in match_ids_result.scalars().all()]
        await self.session.execute(
            delete(CompetitionSchedule).where(CompetitionSchedule.bracket_id == bracket_id)
        )
        if match_ids:
            await self.session.execute(delete(MatchResult).where(MatchResult.match_id.in_(match_ids)))
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

    async def _get_checked_athlete_ids(self, *, competition_id: int, athlete_ids: set[int]) -> set[int]:
        if not athlete_ids:
            return set()

        result = await self.session.execute(
            select(CompetitionCheckin.athlete_id).where(
                CompetitionCheckin.competition_id == competition_id,
                CompetitionCheckin.athlete_id.in_(athlete_ids),
                CompetitionCheckin.status == CHECKIN_STATUS_CHECKED,
            )
        )
        return {int(athlete_id) for athlete_id in result.scalars().all()}

    async def _get_checkin_statuses(self, *, competition_id: int, athlete_ids: set[int]) -> dict[int, str]:
        if not athlete_ids:
            return {}

        result = await self.session.execute(
            select(CompetitionCheckin.athlete_id, CompetitionCheckin.status).where(
                CompetitionCheckin.competition_id == competition_id,
                CompetitionCheckin.athlete_id.in_(athlete_ids),
            )
        )
        return {int(athlete_id): status for athlete_id, status in result.all()}

    async def _is_category_checkin_closed(self, *, competition_id: int, category_id: int) -> bool:
        result = await self.session.execute(
            select(CompetitionCheckinClosure.id).where(
                CompetitionCheckinClosure.competition_id == competition_id,
                CompetitionCheckinClosure.category_id == category_id,
            )
        )
        return result.scalar_one_or_none() is not None

    @staticmethod
    def _walkover_winner_id(
        match: Match,
        statuses: dict[int, str],
        *,
        matches: list[Match] | None = None,
        no_show_is_unavailable: bool = False,
    ) -> int | None:
        athlete_a_status = statuses.get(match.athlete_a_id, CHECKIN_STATUS_NO_SHOW)
        athlete_b_status = statuses.get(match.athlete_b_id, CHECKIN_STATUS_NO_SHOW)
        unavailable_statuses = {CHECKIN_STATUS_OUT_OF_WEIGHT, CHECKIN_STATUS_NO_CHECKED}
        if no_show_is_unavailable:
            unavailable_statuses.add(CHECKIN_STATUS_NO_SHOW)
        if (
            athlete_a_status == CHECKIN_STATUS_CHECKED
            and athlete_b_status in unavailable_statuses
            and (match.athlete_b_id is not None or BracketService._missing_slot_is_resolved(match, matches, "b"))
        ):
            return match.athlete_a_id
        if (
            athlete_b_status == CHECKIN_STATUS_CHECKED
            and athlete_a_status in unavailable_statuses
            and (match.athlete_a_id is not None or BracketService._missing_slot_is_resolved(match, matches, "a"))
        ):
            return match.athlete_b_id
        return None

    @staticmethod
    def _missing_slot_is_resolved(
        match: Match,
        matches: list[Match] | None,
        side: str,
    ) -> bool:
        if match.round_number <= 1:
            return True
        if not matches:
            return False
        origin = BracketService._origin_match_for_slot(match, matches, side)
        return origin is not None and origin.status == MatchStatus.completed and origin.winner_id is None

    @staticmethod
    def _origin_match_for_slot(
        match: Match,
        matches: list[Match],
        side: str,
    ) -> Match | None:
        middle = (match.position_start + match.position_end) // 2
        start = match.position_start if side == "a" else middle + 1
        end = middle if side == "a" else match.position_end
        candidates = [
            candidate
            for candidate in matches
            if candidate.round_number == match.round_number - 1
            and candidate.position_start == start
            and candidate.position_end == end
        ]
        return candidates[0] if candidates else None

    @staticmethod
    def _match_has_no_fighters(
        match: Match,
        statuses: dict[int, str],
        *,
        no_show_is_unavailable: bool = False,
    ) -> bool:
        if not no_show_is_unavailable:
            return False
        athlete_ids = [athlete_id for athlete_id in (match.athlete_a_id, match.athlete_b_id) if athlete_id is not None]
        if not athlete_ids:
            return False
        unavailable_statuses = {
            CHECKIN_STATUS_OUT_OF_WEIGHT,
            CHECKIN_STATUS_NO_CHECKED,
            CHECKIN_STATUS_NO_SHOW,
        }
        return all(statuses.get(athlete_id, CHECKIN_STATUS_NO_SHOW) in unavailable_statuses for athlete_id in athlete_ids)

    async def _upsert_automatic_match_result(
        self,
        *,
        match: Match,
        winner_id: int | None,
        finish_method: str,
    ) -> None:
        query = await self.session.execute(
            select(MatchResult).where(MatchResult.match_id == match.id)
        )
        result = query.scalar_one_or_none()
        if result is None:
            result = MatchResult(match_id=match.id)
            self.session.add(result)
        result.athlete_a_points = 0
        result.athlete_a_advantages = 0
        result.athlete_a_penalties = 0
        result.athlete_b_points = 0
        result.athlete_b_advantages = 0
        result.athlete_b_penalties = 0
        result.winner_id = winner_id
        result.finish_method = finish_method
        result.finalized = True
        result.finished_at = datetime.now(UTC)

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
        bracket.checkin_closed = await self._is_category_checkin_closed(
            competition_id=bracket.competition_id,
            category_id=bracket.category_id,
        )
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
            status = statuses_by_athlete.get(athlete_id, CHECKIN_STATUS_NO_SHOW)
            if bracket.checkin_closed and status not in {CHECKIN_STATUS_CHECKED, CHECKIN_STATUS_OUT_OF_WEIGHT}:
                status = CHECKIN_STATUS_NO_SHOW
            athlete.checkin_status = status

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

    def _advance_bye_winners(self, matches: list[Match], *, checked_athlete_ids: set[int]) -> None:
        for match in sorted(matches, key=lambda item: (item.round_number, item.match_number)):
            if (
                match.winner_id is None
                or match.status != MatchStatus.bye
                or match.winner_id not in checked_athlete_ids
            ):
                continue

            next_match = self._find_next_match(matches, match)
            if next_match is None:
                continue

            middle = (next_match.position_start + next_match.position_end) // 2
            if match.position_end <= middle and next_match.athlete_a_id is None:
                next_match.athlete_a_id = match.winner_id
            elif match.position_end > middle and next_match.athlete_b_id is None:
                next_match.athlete_b_id = match.winner_id

    @staticmethod
    def _find_next_match(matches: list[Match], match: Match) -> Match | None:
        candidates = [
            candidate
            for candidate in matches
            if candidate.round_number == match.round_number + 1
            and candidate.position_start <= match.position_start
            and candidate.position_end >= match.position_end
        ]
        if not candidates:
            return None
        return min(candidates, key=lambda item: item.position_end - item.position_start)

