from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.common import Belt


class CategoryBase(BaseModel):
    weight_class: str = Field(..., min_length=1, max_length=80, examples=["Lightweight"])
    belt: Belt = Field(..., examples=[Belt.blue])
    age_group: str = Field(..., min_length=1, max_length=80, examples=["Adult"])

    @field_validator("weight_class", "age_group")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Field cannot be blank.")
        return normalized


class CategoryCreate(CategoryBase):
    model_config = {
        "json_schema_extra": {
            "examples": [
                {"weight_class": "Lightweight", "belt": "blue", "age_group": "Adult"}
            ]
        }
    }


class CategoryRead(CategoryBase):
    id: int

    model_config = ConfigDict(from_attributes=True)

