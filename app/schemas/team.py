from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.validators import validate_team_phone


class TeamBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=160, examples=["Gracie Barra"])
    created_date: date = Field(..., examples=["2002-04-12"])
    responsible: str = Field(..., min_length=1, max_length=160, examples=["Carlos Gracie Jr."])
    phone: str = Field(..., min_length=13, max_length=13, examples=["11-99999-1234"])

    @field_validator("name", "responsible")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Field cannot be blank.")
        return normalized

    @field_validator("created_date")
    @classmethod
    def created_date_cannot_be_future(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("Created date cannot be in the future.")
        return value

    @field_validator("phone")
    @classmethod
    def validate_phone_format(cls, value: str) -> str:
        return validate_team_phone(value)


class TeamCreate(TeamBase):
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "Gracie Barra",
                    "created_date": "2002-04-12",
                    "responsible": "Carlos Gracie Jr.",
                    "phone": "11-99999-1234",
                }
            ]
        }
    }


class TeamUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=160, examples=["Alliance"])
    created_date: date | None = Field(None, examples=["1993-01-01"])
    responsible: str | None = Field(None, min_length=1, max_length=160, examples=["Fabio Gurgel"])
    phone: str | None = Field(None, min_length=13, max_length=13, examples=["21-98888-1234"])

    @field_validator("name", "responsible")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.strip()
        if not normalized:
            raise ValueError("Field cannot be blank.")
        return normalized

    @field_validator("created_date")
    @classmethod
    def optional_created_date_cannot_be_future(cls, value: date | None) -> date | None:
        if value is not None and value > date.today():
            raise ValueError("Created date cannot be in the future.")
        return value

    @field_validator("phone")
    @classmethod
    def validate_optional_phone_format(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return validate_team_phone(value)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "responsible": "Fabio Gurgel",
                    "phone": "21-98888-1234",
                }
            ]
        }
    }


class TeamRead(TeamBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class TeamList(BaseModel):
    items: list[TeamRead]
    total: int
    limit: int
    offset: int
