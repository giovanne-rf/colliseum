from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.bracket import MatchStatus
from app.schemas.athlete import AthleteRead
from app.schemas.category import CategoryRead


class CompetitionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=160, examples=["Rio Open 2026"])
    event_date: date = Field(..., examples=["2026-08-15"])

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Field cannot be blank.")
        return normalized


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
