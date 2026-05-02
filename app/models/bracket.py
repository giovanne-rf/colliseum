from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class MatchStatus(StrEnum):
    pending = "pending"
    bye = "bye"
    completed = "completed"


class Competition(Base):
    __tablename__ = "competitions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False, unique=True, index=True)
    event_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class CompetitionRegistration(Base):
    __tablename__ = "competition_registrations"
    __table_args__ = (
        UniqueConstraint(
            "competition_id",
            "athlete_id",
            name="uq_registration_competition_athlete",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    competition_id: Mapped[int] = mapped_column(
        ForeignKey("competitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    athlete_id: Mapped[int] = mapped_column(
        ForeignKey("athletes.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    athlete = relationship("Athlete")
    category = relationship("Category")
    competition = relationship("Competition")


class Bracket(Base):
    __tablename__ = "brackets"
    __table_args__ = (
        UniqueConstraint("competition_id", "category_id", name="uq_bracket_competition_category"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    competition_id: Mapped[int] = mapped_column(
        ForeignKey("competitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    bracket_size: Mapped[int] = mapped_column(Integer, nullable=False)
    bye_count: Mapped[int] = mapped_column(Integer, nullable=False)
    rounds: Mapped[int] = mapped_column(Integer, nullable=False)
    same_team_conflicts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    category = relationship("Category")
    competition = relationship("Competition")
    entries = relationship(
        "BracketEntry",
        cascade="all, delete-orphan",
        order_by=lambda: BracketEntry.position,
    )
    matches = relationship(
        "Match",
        cascade="all, delete-orphan",
        order_by=lambda: (Match.round_number, Match.match_number),
    )


class BracketEntry(Base):
    __tablename__ = "bracket_entries"
    __table_args__ = (
        UniqueConstraint("bracket_id", "position", name="uq_bracket_entry_position"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    bracket_id: Mapped[int] = mapped_column(
        ForeignKey("brackets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    athlete_id: Mapped[int | None] = mapped_column(
        ForeignKey("athletes.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    team_id: Mapped[int | None] = mapped_column(
        ForeignKey("teams.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    is_bye: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    athlete = relationship("Athlete")
    team = relationship("Team")


class Match(Base):
    __tablename__ = "matches"
    __table_args__ = (
        UniqueConstraint("bracket_id", "round_number", "match_number", name="uq_match_round_number"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    bracket_id: Mapped[int] = mapped_column(
        ForeignKey("brackets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    round_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    match_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    position_start: Mapped[int] = mapped_column(Integer, nullable=False)
    position_end: Mapped[int] = mapped_column(Integer, nullable=False)
    athlete_a_id: Mapped[int | None] = mapped_column(
        ForeignKey("athletes.id", ondelete="RESTRICT"),
        nullable=True,
    )
    athlete_b_id: Mapped[int | None] = mapped_column(
        ForeignKey("athletes.id", ondelete="RESTRICT"),
        nullable=True,
    )
    winner_id: Mapped[int | None] = mapped_column(
        ForeignKey("athletes.id", ondelete="RESTRICT"),
        nullable=True,
    )
    status: Mapped[MatchStatus] = mapped_column(String(20), nullable=False, default=MatchStatus.pending)

    athlete_a = relationship("Athlete", foreign_keys=[athlete_a_id])
    athlete_b = relationship("Athlete", foreign_keys=[athlete_b_id])
    winner = relationship("Athlete", foreign_keys=[winner_id])
