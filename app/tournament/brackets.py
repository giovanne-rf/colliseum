from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from math import log2

from app.models.athlete import Athlete


@dataclass(frozen=True)
class BracketPlacement:
    position: int
    athlete: Athlete | None
    is_bye: bool


def next_power_of_two(value: int) -> int:
    if value < 2:
        return 2
    return 1 << (value - 1).bit_length()


def seed_position_order(bracket_size: int) -> list[int]:
    if bracket_size < 2 or bracket_size & (bracket_size - 1) != 0:
        raise ValueError("Bracket size must be a power of two.")

    positions = [0]
    size = 1
    while size < bracket_size:
        size *= 2
        positions = [position for seed in positions for position in (seed, size - 1 - seed)]
    return positions


def earliest_possible_meeting_round(
    left_position: int,
    right_position: int,
    bracket_size: int,
) -> int:
    if left_position == right_position:
        raise ValueError("Positions must be different.")

    round_number = 1
    left = left_position
    right = right_position
    while left // 2 != right // 2:
        left //= 2
        right //= 2
        round_number += 1

    max_round = int(log2(bracket_size))
    return min(round_number, max_round)


def generate_ibjjf_style_placements(athletes: list[Athlete]) -> list[BracketPlacement]:
    if len(athletes) < 2:
        raise ValueError("At least two athletes are required to generate a bracket.")

    bracket_size = next_power_of_two(len(athletes))
    candidate_positions = seed_position_order(bracket_size)[: len(athletes)]
    ordered_athletes = _order_athletes_for_team_separation(athletes)
    assigned: dict[int, Athlete] = {}

    for athlete in ordered_athletes:
        position = _choose_best_position(
            athlete=athlete,
            assigned=assigned,
            candidate_positions=candidate_positions,
            bracket_size=bracket_size,
        )
        assigned[position] = athlete

    placements: list[BracketPlacement] = []
    for position in range(bracket_size):
        athlete = assigned.get(position)
        placements.append(
            BracketPlacement(
                position=position + 1,
                athlete=athlete,
                is_bye=athlete is None,
            )
        )
    return placements


def count_same_team_first_round_conflicts(placements: list[BracketPlacement]) -> int:
    conflicts = 0
    for index in range(0, len(placements), 2):
        left = placements[index].athlete
        right = placements[index + 1].athlete
        if left is not None and right is not None and left.team_id == right.team_id:
            conflicts += 1
    return conflicts


def _order_athletes_for_team_separation(athletes: list[Athlete]) -> list[Athlete]:
    team_counts = Counter(athlete.team_id for athlete in athletes)
    return sorted(
        athletes,
        key=lambda athlete: (-team_counts[athlete.team_id], athlete.team_id, athlete.name, athlete.id),
    )


def _choose_best_position(
    *,
    athlete: Athlete,
    assigned: dict[int, Athlete],
    candidate_positions: list[int],
    bracket_size: int,
) -> int:
    available_positions = [position for position in candidate_positions if position not in assigned]
    max_round = int(log2(bracket_size))

    def score(position: int) -> tuple[int, int, int, int]:
        same_team_rounds = [
            earliest_possible_meeting_round(position, assigned_position, bracket_size)
            for assigned_position, assigned_athlete in assigned.items()
            if assigned_athlete.team_id == athlete.team_id
        ]
        if same_team_rounds:
            earliest_round = min(same_team_rounds)
            total_rounds = sum(same_team_rounds)
        else:
            earliest_round = max_round
            total_rounds = max_round

        first_round_conflict = int(earliest_round == 1)
        seed_preference = -candidate_positions.index(position)
        return (earliest_round, total_rounds, -first_round_conflict, seed_preference)

    return max(available_positions, key=score)
