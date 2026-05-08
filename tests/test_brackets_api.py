from __future__ import annotations

from collections import defaultdict

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database.base import Base
from app.database.session import get_db_session
from app.main import app
from app.tournament.brackets import earliest_possible_meeting_round, next_power_of_two


@pytest.fixture
async def client():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    TestingSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def override_get_db_session():
        async with TestingSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_get_db_session
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as async_client:
        yield async_client

    app.dependency_overrides.clear()
    await engine.dispose()


async def create_team(client: AsyncClient, name: str) -> int:
    response = await client.post(
        "/teams",
        json={
            "name": name,
            "created_date": "2002-04-12",
            "responsible": "Responsavel",
            "phone": "11-99999-1234",
        },
    )
    assert response.status_code == 201
    return int(response.json()["id"])


async def create_category(client: AsyncClient) -> int:
    response = await client.post(
        "/categories/bulk",
        json=[{"weight_class": "Male - Light (-76.0 kg)", "belt": "blue", "age_group": "Adult"}],
    )
    assert response.status_code == 201
    return int(response.json()[0]["id"])


async def create_competition(client: AsyncClient) -> int:
    response = await client.post(
        "/competitions",
        json={"name": "Rio Open 2026", "event_date": "2026-08-15", "mat_count": 4},
    )
    assert response.status_code == 201
    return int(response.json()["id"])


async def create_athlete(client: AsyncClient, index: int, team_id: int) -> int:
    cpfs = [
        "529.982.247-25",
        "390.533.447-05",
        "111.444.777-35",
        "935.411.347-80",
        "123.456.789-09",
        "168.995.350-09",
    ]
    response = await client.post(
        "/athletes",
        json={
            "name": f"Atleta {index}",
            "cpf": cpfs[index - 1],
            "email": f"atleta{index}@example.com",
            "phone": f"11-9999{index}.1234",
            "sex": "male",
            "team_id": team_id,
            "belt": "blue",
            "graduation_date": "2024-12-10",
            "birth_date": "2002-05-14",
        },
    )
    assert response.status_code == 201
    return int(response.json()["id"])


async def add_ranking_points(client: AsyncClient, athlete_id: int) -> None:
    response = await client.post(
        "/ranking",
        json={
            "athlete_id": athlete_id,
            "belt": "blue",
            "age_group": "Adult",
            "points": 10,
            "competition_name": "Rio Open 2026",
        },
    )
    assert response.status_code == 201


def athlete_registration_payload(index: int, category_id: int):
    cpfs = [
        "529.982.247-25",
        "390.533.447-05",
        "111.444.777-35",
        "935.411.347-80",
        "123.456.789-09",
        "168.995.350-09",
    ]
    return {
        "cpf": cpfs[index - 1],
        "birth_date": "2002-05-14",
        "category_id": category_id,
    }


async def test_generate_bracket_uses_power_of_two_byes_and_separates_same_team(
    client: AsyncClient,
):
    team_a = await create_team(client, "Equipe A")
    team_b = await create_team(client, "Equipe B")
    category_id = await create_category(client)
    competition_id = await create_competition(client)
    athlete_ids = [
        await create_athlete(client, 1, team_a),
        await create_athlete(client, 2, team_a),
        await create_athlete(client, 3, team_b),
        await create_athlete(client, 4, team_b),
    ]

    for index, _athlete_id in enumerate(athlete_ids, start=1):
        response = await client.post(
            f"/competitions/{competition_id}/registrations",
            json=athlete_registration_payload(index, category_id),
        )
        assert response.status_code == 201

    response = await client.post(
        f"/competitions/{competition_id}/brackets",
        json={"category_id": category_id, "replace_existing": True},
    )

    assert response.status_code == 201
    bracket = response.json()
    assert bracket["bracket_size"] == 4
    assert bracket["bye_count"] == 0
    assert bracket["rounds"] == 2
    assert bracket["same_team_conflicts"] == 0
    assert len(bracket["entries"]) == 4
    assert len(bracket["matches"]) == 3

    positions_by_team = defaultdict(list)
    for entry in bracket["entries"]:
        if entry["athlete"] is not None:
            positions_by_team[entry["athlete"]["team_id"]].append(entry["position"] - 1)

    for positions in positions_by_team.values():
        assert len(positions) == 2
        assert earliest_possible_meeting_round(positions[0], positions[1], 4) == 2


async def test_create_competition_registrations_bulk(client: AsyncClient):
    team_a = await create_team(client, "Equipe Bulk A")
    team_b = await create_team(client, "Equipe Bulk B")
    category_id = await create_category(client)
    competition_id = await create_competition(client)
    await create_athlete(client, 1, team_a)
    await create_athlete(client, 2, team_b)

    response = await client.post(
        f"/competitions/{competition_id}/registrations/bulk",
        json=[
            athlete_registration_payload(1, category_id),
            athlete_registration_payload(2, category_id),
        ],
    )

    assert response.status_code == 201
    registrations = response.json()
    assert len(registrations) == 2
    assert [registration["category_id"] for registration in registrations] == [
        category_id,
        category_id,
    ]
    assert [registration["athlete"]["name"] for registration in registrations] == [
        "Atleta 1",
        "Atleta 2",
    ]


async def test_reject_competition_registrations_bulk_duplicate_without_partial_insert(
    client: AsyncClient,
):
    team_id = await create_team(client, "Equipe Bulk Duplicada")
    category_id = await create_category(client)
    competition_id = await create_competition(client)
    await create_athlete(client, 1, team_id)

    response = await client.post(
        f"/competitions/{competition_id}/registrations/bulk",
        json=[
            athlete_registration_payload(1, category_id),
            athlete_registration_payload(1, category_id),
        ],
    )

    assert response.status_code == 409

    list_response = await client.get(f"/competitions/{competition_id}/registrations")
    assert list_response.status_code == 200
    assert list_response.json() == []


async def test_generate_bracket_adds_byes_for_non_power_of_two(client: AsyncClient):
    teams = [await create_team(client, f"Equipe {index}") for index in range(1, 7)]
    category_id = await create_category(client)
    competition_id = await create_competition(client)

    for index, team_id in enumerate(teams, start=1):
        await create_athlete(client, index, team_id)
        response = await client.post(
            f"/competitions/{competition_id}/registrations",
            json=athlete_registration_payload(index, category_id),
        )
        assert response.status_code == 201

    response = await client.post(
        f"/competitions/{competition_id}/brackets",
        json={"category_id": category_id},
    )

    assert response.status_code == 201
    bracket = response.json()
    assert bracket["bracket_size"] == next_power_of_two(6)
    assert bracket["bye_count"] == 2
    assert sum(1 for entry in bracket["entries"] if entry["is_bye"]) == 2
    assert [match["status"] for match in bracket["matches"]].count("bye") == 2


async def test_generate_bracket_gives_byes_to_ranked_athletes_first(client: AsyncClient):
    teams = [await create_team(client, f"Equipe Bye Ranking {index}") for index in range(1, 7)]
    category_id = await create_category(client)
    competition_id = await create_competition(client)
    athlete_ids = []

    for index, team_id in enumerate(teams, start=1):
        athlete_ids.append(await create_athlete(client, index, team_id))
        response = await client.post(
            f"/competitions/{competition_id}/registrations",
            json=athlete_registration_payload(index, category_id),
        )
        assert response.status_code == 201

    await add_ranking_points(client, athlete_ids[0])
    await add_ranking_points(client, athlete_ids[1])

    response = await client.post(
        f"/competitions/{competition_id}/brackets",
        json={"category_id": category_id},
    )

    assert response.status_code == 201
    bracket = response.json()
    ranked_ids = set(athlete_ids[:2])
    ranked_entry_flags = {
        entry["athlete"]["id"]: entry["athlete"]["is_ranked"]
        for entry in bracket["entries"]
        if entry["athlete"] is not None
    }
    assert ranked_entry_flags[athlete_ids[0]] is True
    assert ranked_entry_flags[athlete_ids[2]] is False
    bye_winner_ids = {
        match["winner"]["id"]
        for match in bracket["matches"]
        if match["round_number"] == 1 and match["status"] == "bye"
    }
    assert len(bye_winner_ids) == 2
    assert bye_winner_ids == ranked_ids


async def test_generate_bracket_keeps_same_team_ranked_byes_on_opposite_extremes(
    client: AsyncClient,
):
    team_a = await create_team(client, "Equipe Ranked Extremos")
    other_teams = [
        await create_team(client, f"Equipe Ranked Extremos {index}") for index in range(1, 5)
    ]
    category_id = await create_category(client)
    competition_id = await create_competition(client)
    athlete_ids = [
        await create_athlete(client, 1, team_a),
        await create_athlete(client, 2, team_a),
    ]

    for index, team_id in enumerate(other_teams, start=3):
        athlete_ids.append(await create_athlete(client, index, team_id))

    for index, _athlete_id in enumerate(athlete_ids, start=1):
        response = await client.post(
            f"/competitions/{competition_id}/registrations",
            json=athlete_registration_payload(index, category_id),
        )
        assert response.status_code == 201

    await add_ranking_points(client, athlete_ids[0])
    await add_ranking_points(client, athlete_ids[1])

    response = await client.post(
        f"/competitions/{competition_id}/brackets",
        json={"category_id": category_id},
    )

    assert response.status_code == 201
    bracket = response.json()
    positions = [
        entry["position"] - 1
        for entry in bracket["entries"]
        if entry["athlete"] is not None and entry["athlete"]["team_id"] == team_a
    ]
    assert len(positions) == 2
    assert earliest_possible_meeting_round(positions[0], positions[1], bracket["bracket_size"]) == bracket["rounds"]


async def test_generate_bracket_avoids_ranked_vs_ranked_when_unranked_is_available(
    client: AsyncClient,
):
    teams = [await create_team(client, f"Equipe Ranking Disponivel {index}") for index in range(1, 7)]
    category_id = await create_category(client)
    competition_id = await create_competition(client)
    athlete_ids = []

    for index, team_id in enumerate(teams, start=1):
        athlete_ids.append(await create_athlete(client, index, team_id))
        response = await client.post(
            f"/competitions/{competition_id}/registrations",
            json=athlete_registration_payload(index, category_id),
        )
        assert response.status_code == 201

    for athlete_id in athlete_ids[:3]:
        await add_ranking_points(client, athlete_id)

    response = await client.post(
        f"/competitions/{competition_id}/brackets",
        json={"category_id": category_id},
    )

    assert response.status_code == 201
    bracket = response.json()
    ranked_ids = set(athlete_ids[:3])
    bye_winner_ids = {
        match["winner"]["id"]
        for match in bracket["matches"]
        if match["round_number"] == 1 and match["status"] == "bye"
    }
    assert len(bye_winner_ids) == 2
    assert bye_winner_ids.issubset(ranked_ids)

    first_round_matches = [
        match
        for match in bracket["matches"]
        if match["round_number"] == 1 and match["status"] != "bye"
    ]
    for match in first_round_matches:
        match_athlete_ids = {match["athlete_a"]["id"], match["athlete_b"]["id"]}
        assert not match_athlete_ids.issubset(ranked_ids)


async def test_generate_all_brackets_for_competition_categories(client: AsyncClient):
    teams = [await create_team(client, f"Equipe Lote {index}") for index in range(1, 5)]
    category_id = await create_category(client)
    competition_id = await create_competition(client)

    for index, team_id in enumerate(teams, start=1):
        await create_athlete(client, index, team_id)
        response = await client.post(
            f"/competitions/{competition_id}/registrations",
            json=athlete_registration_payload(index, category_id),
        )
        assert response.status_code == 201

    response = await client.post(
        f"/competitions/{competition_id}/brackets/generate-all",
        json={"replace_existing": True},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["competition_id"] == competition_id
    assert payload["generated_count"] == 1
    assert payload["skipped_count"] == 0
    assert len(payload["brackets"]) == 1
    assert payload["brackets"][0]["category_id"] == category_id
    assert len(payload["brackets"][0]["entries"]) == 4


async def test_reject_bracket_with_less_than_two_registered_athletes(client: AsyncClient):
    team_id = await create_team(client, "Equipe A")
    category_id = await create_category(client)
    competition_id = await create_competition(client)
    await create_athlete(client, 1, team_id)
    response = await client.post(
        f"/competitions/{competition_id}/registrations",
        json=athlete_registration_payload(1, category_id),
    )
    assert response.status_code == 201

    response = await client.post(
        f"/competitions/{competition_id}/brackets",
        json={"category_id": category_id},
    )

    assert response.status_code == 422


async def test_registration_options_validate_cpf_birth_date_and_filter_categories(
    client: AsyncClient,
):
    team_id = await create_team(client, "Equipe A")
    category_id = await create_category(client)
    competition_id = await create_competition(client)
    await create_athlete(client, 1, team_id)

    options_response = await client.get(
        f"/competitions/{competition_id}/registration-options",
        params={"cpf": "529.982.247-25", "birth_date": "2002-05-14"},
    )

    assert options_response.status_code == 200
    options = options_response.json()
    assert options["athlete"]["name"] == "Atleta 1"
    assert options["age"] == 24
    assert options["age_group"] == "Adult"
    assert [category["id"] for category in options["categories"]] == [category_id]

    invalid_response = await client.get(
        f"/competitions/{competition_id}/registration-options",
        params={"cpf": "529.982.247-25", "birth_date": "2001-05-14"},
    )
    assert invalid_response.status_code == 422
