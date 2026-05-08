from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.bracket import MatchStatus
from app.schemas.athlete import AthleteRead
from app.schemas.category import CategoryRead


class CompetitionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=160, examples=["Rio Open 2026"])
    event_date: date = Field(..., examples=["2026-08-15"])
    mat_count: int = Field(..., ge=4, le=12, examples=[4])

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Field cannot be blank.")
        return normalized

    @field_validator("mat_count")
    @classmethod
    def mat_count_must_be_even(cls, value: int) -> int:
        if value % 2 != 0:
            raise ValueError("Mat count must be an even number.")
        return value


class CompetitionRead(CompetitionCreate):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CompetitionRegistrationCreate(BaseModel):
    cpf: str = Field(..., min_length=11, max_length=14, examples=["529.982.247-25"])
    birth_date: date = Field(..., examples=["2002-05-14"])
    category_id: int = Field(..., gt=0, examples=[1])


class CompetitionRegistrationRead(BaseModel):
    id: int
    competition_id: int
    athlete_id: int
    category_id: int
    athlete: AthleteRead
    category: CategoryRead
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CompetitionCheckinCreate(BaseModel):
    registration_id: int = Field(..., gt=0, examples=[1])
    checked_weight: Decimal = Field(..., gt=0, decimal_places=2, examples=["76.50"])
    gi: bool = Field(default=True, examples=[True])
    overweight_confirmed: bool = Field(default=False)


class CompetitionCheckinRead(BaseModel):
    id: int
    competition_id: int
    registration_id: int
    athlete_id: int
    checked_weight: Decimal
    gi: bool
    overweight_confirmed: bool
    status: str
    is_overweight: bool
    max_weight_kg: Decimal | None = None
    athlete: AthleteRead
    category: CategoryRead
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CompetitionCheckinLookupRead(BaseModel):
    registration_id: int
    competition_id: int
    athlete: AthleteRead
    category: CategoryRead
    max_weight_kg: Decimal | None = None
    status: str
    checkin: CompetitionCheckinRead | None = None


class CompetitionFinalCheckRead(BaseModel):
    registration_id: int
    competition_id: int
    athlete: AthleteRead
    category: CategoryRead
    checked_weight: Decimal | None = None
    status: str
    is_overweight: bool = False


class RegistrationOptionsRead(BaseModel):
    athlete: AthleteRead
    competition_id: int
    age: int
    age_group: str
    categories: list[CategoryRead]


class BracketGenerateRequest(BaseModel):
    category_id: int = Field(..., gt=0, examples=[1])
    replace_existing: bool = Field(default=True)


class BracketGenerateAllRequest(BaseModel):
    replace_existing: bool = Field(default=True)


class BracketEntryRead(BaseModel):
    position: int
    is_bye: bool
    athlete: AthleteRead | None = None

    model_config = ConfigDict(from_attributes=True)


class MatchResultUpdate(BaseModel):
    athlete_a_points: int = Field(default=0, ge=0)
    athlete_a_advantages: int = Field(default=0, ge=0)
    athlete_a_penalties: int = Field(default=0, ge=0)
    athlete_b_points: int = Field(default=0, ge=0)
    athlete_b_advantages: int = Field(default=0, ge=0)
    athlete_b_penalties: int = Field(default=0, ge=0)
    finish_method: str | None = Field(default=None, max_length=30)
    winner_id: int | None = Field(default=None, gt=0)
    finalized: bool = Field(default=False)


class MatchResultRead(BaseModel):
    id: int
    match_id: int
    athlete_a_points: int
    athlete_a_advantages: int
    athlete_a_penalties: int
    athlete_b_points: int
    athlete_b_advantages: int
    athlete_b_penalties: int
    winner_id: int | None = None
    finish_method: str | None = None
    finalized: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MatchRead(BaseModel):
    id: int
    round_number: int
    match_number: int
    position_start: int
    position_end: int
    athlete_a: AthleteRead | None = None
    athlete_b: AthleteRead | None = None
    winner: AthleteRead | None = None
    status: MatchStatus
    result: MatchResultRead | None = None

    model_config = ConfigDict(from_attributes=True)


class BracketRead(BaseModel):
    id: int
    competition_id: int
    category_id: int
    bracket_size: int
    bye_count: int
    rounds: int
    same_team_conflicts: int
    category: CategoryRead
    entries: list[BracketEntryRead]
    matches: list[MatchRead]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BracketBatchGenerateRead(BaseModel):
    competition_id: int
    generated_count: int
    skipped_count: int
    brackets: list[BracketRead]
