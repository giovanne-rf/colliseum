from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.common import Belt


class RankingEntry(Base):
    __tablename__ = "ranking_entries"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    athlete_id: Mapped[int] = mapped_column(
        ForeignKey("athletes.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    belt: Mapped[Belt] = mapped_column(Enum(Belt, name="belt_enum"), nullable=False, index=True)
    age_group: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    competition_name: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    athlete = relationship("Athlete")
