from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.common import Belt, Sex

# Faixas acima da preta — equipe não é obrigatória
BELTS_ABOVE_BLACK = {Belt.red_black, Belt.red_white, Belt.red}


class Athlete(Base):
    __tablename__ = "athletes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    cpf: Mapped[str] = mapped_column(String(11), nullable=False, unique=True, index=True)
    email: Mapped[str] = mapped_column(String(254), nullable=False, unique=True, index=True)
    phone: Mapped[str] = mapped_column(String(13), nullable=False)
    sex: Mapped[Sex] = mapped_column(Enum(Sex, name="sex_enum"), nullable=False, index=True)
    team_id: Mapped[int | None] = mapped_column(
        ForeignKey("teams.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    belt: Mapped[Belt] = mapped_column(Enum(Belt, name="belt_enum"), nullable=False, index=True)
    graduation_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    birth_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    team = relationship("Team")
