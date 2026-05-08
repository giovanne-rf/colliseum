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


def generate_ibjjf_style_placements(
    athletes: list[Athlete],
    ranked_athlete_ids: set[int] | None = None,
) -> list[BracketPlacement]:
    if len(athletes) < 2:
        raise ValueError("At least two athletes are required to generate a bracket.")

    ranked_ids = ranked_athlete_ids or set()
    bracket_size = next_power_of_two(len(athletes))
    bye_count = bracket_size - len(athletes)
    seed_order = seed_position_order(bracket_size)
    ordered_ranked = _order_athletes_for_team_separation(
        [athlete for athlete in athletes if athlete.id in ranked_ids]
    )
    ordered_unranked = _order_athletes_for_team_separation(
        [athlete for athlete in athletes if athlete.id not in ranked_ids]
    )
    assigned: dict[int, Athlete] = {}
    blocked_bye_positions: set[int] = set()

    bye_receivers = ordered_ranked[:bye_count]
    if len(bye_receivers) < bye_count:
        bye_receivers = [
            *bye_receivers,
            *ordered_unranked[: bye_count - len(bye_receivers)],
        ]

    bye_receiver_ids = {athlete.id for athlete in bye_receivers}
    available_bye_pairs = _seeded_first_round_pairs(bracket_size, seed_order)
    for athlete in bye_receivers:
        pair = _choose_best_bye_pair(
            athlete=athlete,
            assigned=assigned,
            available_pairs=available_bye_pairs,
            seed_order=seed_order,
            bracket_size=bracket_size,
        )
        available_bye_pairs.remove(pair)
        athlete_position = _choose_best_position(
            athlete=athlete,
            assigned=assigned,
            candidate_positions=list(pair),
            bracket_size=bracket_size,
            ranked_athlete_ids=ranked_ids,
            unassigned_unranked_count=0,
        )
        assigned[athlete_position] = athlete
        blocked_bye_positions.add(pair[0] if athlete_position == pair[1] else pair[1])

    candidate_positions = [
        position for position in seed_order if position not in assigned and position not in blocked_bye_positions
    ]
    remaining_athletes = [
        athlete
        for athlete in [*ordered_unranked, *ordered_ranked]
        if athlete.id not in bye_receiver_ids
    ]

    for athlete in remaining_athletes:
        assigned_athlete_ids = {assigned_athlete.id for assigned_athlete in assigned.values()}
        position = _choose_best_position(
            athlete=athlete,
            assigned=assigned,
            candidate_positions=candidate_positions,
            bracket_size=bracket_size,
            ranked_athlete_ids=ranked_ids,
            unassigned_unranked_count=sum(
                1
                for remaining in remaining_athletes
                if remaining.id != athlete.id
                and remaining.id not in assigned_athlete_ids
                and remaining.id not in ranked_ids
            ),
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
    ranked_athlete_ids: set[int] | None = None,
    unassigned_unranked_count: int = 0,
) -> int:
    available_positions = [position for position in candidate_positions if position not in assigned]
    max_round = int(log2(bracket_size))
    ranked_ids = ranked_athlete_ids or set()

    def score(position: int) -> tuple[int, int, int, int, int]:
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
        ranking_score = _ranking_pair_score(
            athlete=athlete,
            opponent=assigned.get(_first_round_opponent(position)),
            ranked_athlete_ids=ranked_ids,
            unassigned_unranked_count=unassigned_unranked_count,
        )
        seed_preference = -candidate_positions.index(position)
        return (earliest_round, total_rounds, -first_round_conflict, ranking_score, seed_preference)

    return max(available_positions, key=score)


def _seeded_first_round_pairs(bracket_size: int, seed_order: list[int]) -> list[tuple[int, int]]:
    pairs = [(position, position + 1) for position in range(0, bracket_size, 2)]
    return sorted(pairs, key=lambda pair: min(seed_order.index(pair[0]), seed_order.index(pair[1])))


def _choose_best_bye_pair(
    *,
    athlete: Athlete,
    assigned: dict[int, Athlete],
    available_pairs: list[tuple[int, int]],
    seed_order: list[int],
    bracket_size: int,
) -> tuple[int, int]:
    empty_pairs = [
        pair for pair in available_pairs if pair[0] not in assigned and pair[1] not in assigned
    ]

    def score(pair: tuple[int, int]) -> tuple[int, int, int]:
        best_position = _choose_best_position(
            athlete=athlete,
            assigned=assigned,
            candidate_positions=list(pair),
            bracket_size=bracket_size,
        )
        same_team_rounds = [
            earliest_possible_meeting_round(best_position, assigned_position, bracket_size)
            for assigned_position, assigned_athlete in assigned.items()
            if assigned_athlete.team_id == athlete.team_id
        ]
        earliest_round = min(same_team_rounds) if same_team_rounds else int(log2(bracket_size))
        seed_preference = -min(seed_order.index(pair[0]), seed_order.index(pair[1]))
        return (earliest_round, sum(same_team_rounds) if same_team_rounds else earliest_round, seed_preference)

    return max(empty_pairs, key=score)


def _first_round_opponent(position: int) -> int:
    return position + 1 if position % 2 == 0 else position - 1


def _ranking_pair_score(
    *,
    athlete: Athlete,
    opponent: Athlete | None,
    ranked_athlete_ids: set[int],
    unassigned_unranked_count: int,
) -> int:
    if opponent is None:
        return 0
    if not ranked_athlete_ids:
        return 0

    athlete_is_ranked = athlete.id in ranked_athlete_ids
    opponent_is_ranked = opponent.id in ranked_athlete_ids
    if athlete_is_ranked != opponent_is_ranked:
        return 2
    if athlete_is_ranked and opponent_is_ranked and unassigned_unranked_count > 0:
        return -2
    if athlete_is_ranked and opponent_is_ranked:
        return -1
    return 0
