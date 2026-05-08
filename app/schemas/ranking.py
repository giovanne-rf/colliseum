from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.common import Belt
from app.schemas.athlete import AthleteRead


class RankingEntryCreate(BaseModel):
    athlete_id: int = Field(..., gt=0, examples=[1])
    belt: Belt = Field(..., examples=[Belt.brown])
    age_group: str = Field(..., min_length=1, max_length=80, examples=["Adult"])
    points: int = Field(..., gt=0, examples=[10])
    competition_name: str = Field(..., min_length=1, max_length=160, examples=["Copa Bandido"])

    @field_validator("age_group", "competition_name")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Field cannot be blank.")
        return normalized


class RankingEntryRead(BaseModel):
    id: int
    athlete_id: int
    belt: Belt
    age_group: str
    points: int
    competition_name: str
    athlete: AthleteRead
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RankingEntryList(BaseModel):
    items: list[RankingEntryRead]
    total: int
    limit: int
    offset: int


class RankingAthleteOption(BaseModel):
    id: int
    name: str
    team_name: str
    belt: Belt
    age_group: str


class RankingOptionsRead(BaseModel):
    belts: list[Belt]
    age_groups: list[str]
    athletes: list[RankingAthleteOption]


class RankingStandingRead(BaseModel):
    position: int
    athlete_id: int
    athlete: AthleteRead
    belt: Belt
    age_group: str
    total_points: int
    entry_count: int


class RankingStandingGroupRead(BaseModel):
    belt: Belt
    age_group: str
    athletes: list[RankingStandingRead]


class RankingStandingsRead(BaseModel):
    groups: list[RankingStandingGroupRead]
    total_ranked: int
