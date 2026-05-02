from __future__ import annotations

from sqlalchemy import Enum, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.common import Belt


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("weight_class", "belt", "age_group", name="uq_category_identity"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    weight_class: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    belt: Mapped[Belt] = mapped_column(Enum(Belt, name="belt_enum"), nullable=False, index=True)
    age_group: Mapped[str] = mapped_column(String(80), nullable=False, index=True)

