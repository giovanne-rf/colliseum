from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from app.core.dates import calculate_age
from app.core.validators import validate_and_normalize_cpf, validate_email, validate_phone
from app.models.common import Belt, Sex
from app.schemas.team import TeamRead


class AthleteBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=160, examples=["Maria Silva"])
    cpf: str = Field(..., min_length=11, max_length=14, examples=["529.982.247-25"])
    email: str = Field(..., min_length=6, max_length=254, examples=["maria.silva@example.com"])
    phone: str = Field(..., min_length=13, max_length=13, examples=["11-99999.1234"])
    sex: Sex = Field(..., examples=[Sex.female])
    team_id: int = Field(..., gt=0, examples=[1])
    belt: Belt = Field(..., examples=[Belt.blue])
    graduation_date: date = Field(..., examples=["2024-12-10"])
    birth_date: date = Field(..., examples=["2002-05-14"])

    @field_validator("name")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Field cannot be blank.")
        return normalized

    @field_validator("cpf")
    @classmethod
    def validate_cpf(cls, value: str) -> str:
        return validate_and_normalize_cpf(value)

    @field_validator("email")
    @classmethod
    def validate_email_address(cls, value: str) -> str:
        return validate_email(value)

    @field_validator("phone")
    @classmethod
    def validate_phone_format(cls, value: str) -> str:
        return validate_phone(value)

    @field_validator("birth_date", "graduation_date")
    @classmethod
    def date_cannot_be_future(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("Date cannot be in the future.")
        return value

    @field_validator("graduation_date")
    @classmethod
    def graduation_date_cannot_precede_birth_date(cls, value: date, info) -> date:
        birth_date = info.data.get("birth_date")
        if birth_date is not None and value < birth_date:
            raise ValueError("Graduation date cannot be before birth date.")
        return value


class AthleteCreate(AthleteBase):
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "Maria Silva",
                    "cpf": "529.982.247-25",
                    "email": "maria.silva@example.com",
                    "phone": "11-99999.1234",
                    "sex": "female",
                    "team_id": 1,
                    "belt": "blue",
                    "graduation_date": "2024-12-10",
                    "birth_date": "2002-05-14",
                }
            ]
        }
    }


class AthleteUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=160, examples=["Maria Silva"])
    cpf: str | None = Field(None, min_length=11, max_length=14, examples=["529.982.247-25"])
    email: str | None = Field(None, min_length=6, max_length=254, examples=["maria@example.com"])
    phone: str | None = Field(None, min_length=13, max_length=13, examples=["11-99999.1234"])
    sex: Sex | None = Field(None, examples=[Sex.female])
    team_id: int | None = Field(None, gt=0, examples=[2])
    belt: Belt | None = Field(None, examples=[Belt.purple])
    graduation_date: date | None = Field(None, examples=["2024-12-10"])
    birth_date: date | None = Field(None, examples=["2001-05-14"])

    @field_validator("name")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.strip()
        if not normalized:
            raise ValueError("Field cannot be blank.")
        return normalized

    @field_validator("cpf")
    @classmethod
    def validate_optional_cpf(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return validate_and_normalize_cpf(value)

    @field_validator("email")
    @classmethod
    def validate_optional_email_address(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return validate_email(value)

    @field_validator("phone")
    @classmethod
    def validate_optional_phone_format(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return validate_phone(value)

    @field_validator("birth_date", "graduation_date")
    @classmethod
    def optional_date_cannot_be_future(cls, value: date | None) -> date | None:
        if value is not None and value > date.today():
            raise ValueError("Date cannot be in the future.")
        return value

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "email": "maria@example.com",
                    "phone": "11-98888.1234",
                    "sex": "female",
                    "team_id": 2,
                    "belt": "purple",
                    "graduation_date": "2024-12-10",
                    "birth_date": "2001-05-14",
                }
            ]
        }
    }


class AthleteRead(AthleteBase):
    id: int
    team: TeamRead
    is_ranked: bool = False

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    @property
    def age(self) -> int:
        return calculate_age(self.birth_date)


class AthleteList(BaseModel):
    items: list[AthleteRead]
    total: int
    limit: int
    offset: int


class CpfAvailabilityRead(BaseModel):
    cpf: str
    exists: bool
    athlete_id: int | None = None
