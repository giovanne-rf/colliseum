from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database.base import Base
from app.database.session import get_db_session
from app.main import app


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


async def create_team(client: AsyncClient) -> int:
    response = await client.post(
        "/teams",
        json={
            "name": "Ranking Team",
            "created_date": "2002-04-12",
            "responsible": "Responsavel",
            "phone": "11-99999-1234",
        },
    )
    assert response.status_code == 201
    return int(response.json()["id"])


async def create_athlete(client: AsyncClient, team_id: int, index: int = 1) -> int:
    cpfs = ["529.982.247-25", "390.533.447-05", "111.444.777-35"]
    response = await client.post(
        "/athletes",
        json={
            "name": f"Atleta Ranking {index}",
            "cpf": cpfs[index - 1],
            "email": f"ranking{index}@example.com",
            "phone": f"11-9999{index}.1234",
            "sex": "male",
            "team_id": team_id,
            "belt": "brown",
            "graduation_date": "2024-12-10",
            "birth_date": "2002-05-14",
        },
    )
    assert response.status_code == 201
    return int(response.json()["id"])


async def create_black_belt_without_team(client: AsyncClient) -> int:
    response = await client.post(
        "/athletes",
        json={
            "name": "Professor Sem Academia",
            "cpf": "935.411.347-80",
            "email": "professor.sem.academia@example.com",
            "phone": "11-98888.1234",
            "sex": "male",
            "team_id": None,
            "belt": "black",
            "graduation_date": "2000-12-10",
            "birth_date": "1982-05-14",
        },
    )
    assert response.status_code == 201
    return int(response.json()["id"])


async def create_category(client: AsyncClient) -> int:
    response = await client.post(
        "/categories/bulk",
        json=[{"weight_class": "Male - Light (-76.0 kg)", "belt": "brown", "age_group": "Adult"}],
    )
    assert response.status_code == 201
    return int(response.json()[0]["id"])


async def create_competition(client: AsyncClient, name: str = "Copa Bandido") -> int:
    response = await client.post(
        "/competitions",
        json={"name": name, "event_date": "2026-08-15", "mat_count": 4},
    )
    assert response.status_code == 201
    return int(response.json()["id"])


async def register_athlete(
    client: AsyncClient,
    *,
    athlete_index: int,
    competition_id: int,
    category_id: int,
) -> None:
    cpfs = ["529.982.247-25", "390.533.447-05", "111.444.777-35"]
    response = await client.post(
        f"/competitions/{competition_id}/registrations",
        json={
            "cpf": cpfs[athlete_index - 1],
            "birth_date": "2002-05-14",
            "category_id": category_id,
        },
    )
    assert response.status_code == 201


async def test_create_and_list_ranking_entry(client: AsyncClient):
    team_id = await create_team(client)
    athlete_id = await create_athlete(client, team_id)
    category_id = await create_category(client)
    competition_id = await create_competition(client)
    await register_athlete(
        client,
        athlete_index=1,
        competition_id=competition_id,
        category_id=category_id,
    )

    options_response = await client.get("/ranking/options?belt=brown&age_group=Adult")
    assert options_response.status_code == 200
    options = options_response.json()
    assert options["belts"] == ["brown"]
    assert options["age_groups"] == ["Adult"]
    assert options["athletes"][0]["id"] == athlete_id

    create_response = await client.post(
        "/ranking",
        json={
            "athlete_id": athlete_id,
            "belt": "brown",
            "age_group": "Adult",
            "points": 15,
            "competition_name": "Copa Bandido",
        },
    )
    assert create_response.status_code == 201
    entry = create_response.json()
    assert entry["points"] == 15
    assert entry["athlete"]["name"] == "Atleta Ranking 1"

    list_response = await client.get("/ranking/entries")
    assert list_response.status_code == 200
    page = list_response.json()
    assert page["total"] == 1
    assert page["items"][0]["competition_name"] == "Copa Bandido"


async def test_ranking_options_allow_black_belt_without_team(client: AsyncClient):
    athlete_id = await create_black_belt_without_team(client)

    response = await client.get("/ranking/options?belt=black&age_group=Master 3")

    assert response.status_code == 200
    options = response.json()
    assert options["athletes"][0]["id"] == athlete_id
    assert options["athletes"][0]["team_name"] == "Sem academia"


async def test_ranking_standings_group_by_belt_age_and_order_by_points(client: AsyncClient):
    team_id = await create_team(client)
    first_athlete_id = await create_athlete(client, team_id, index=1)
    second_athlete_id = await create_athlete(client, team_id, index=2)
    category_id = await create_category(client)
    competition_id = await create_competition(client)
    await register_athlete(
        client,
        athlete_index=1,
        competition_id=competition_id,
        category_id=category_id,
    )
    await register_athlete(
        client,
        athlete_index=2,
        competition_id=competition_id,
        category_id=category_id,
    )

    for athlete_id, points in (
        (first_athlete_id, 10),
        (second_athlete_id, 20),
        (first_athlete_id, 15),
    ):
        response = await client.post(
            "/ranking",
            json={
                "athlete_id": athlete_id,
                "belt": "brown",
                "age_group": "Adult",
                "points": points,
                "competition_name": "Copa Bandido",
            },
        )
        assert response.status_code == 201

    response = await client.get("/ranking/standings")

    assert response.status_code == 200
    standings = response.json()
    assert standings["total_ranked"] == 2
    assert len(standings["groups"]) == 1
    group = standings["groups"][0]
    assert group["belt"] == "brown"
    assert group["age_group"] == "Adult"
    assert [item["athlete_id"] for item in group["athletes"]] == [
        first_athlete_id,
        second_athlete_id,
    ]
    assert [item["position"] for item in group["athletes"]] == [1, 2]
    assert [item["total_points"] for item in group["athletes"]] == [25, 20]
    assert [item["entry_count"] for item in group["athletes"]] == [2, 1]


async def test_reject_ranking_entry_when_belt_does_not_match_athlete(client: AsyncClient):
    team_id = await create_team(client)
    athlete_id = await create_athlete(client, team_id)
    category_id = await create_category(client)
    competition_id = await create_competition(client)
    await register_athlete(
        client,
        athlete_index=1,
        competition_id=competition_id,
        category_id=category_id,
    )

    response = await client.post(
        "/ranking",
        json={
            "athlete_id": athlete_id,
            "belt": "black",
            "age_group": "Adult",
            "points": 10,
            "competition_name": "Copa Bandido",
        },
    )

    assert response.status_code == 422


async def test_reject_ranking_entry_when_athlete_is_not_registered_in_competition(
    client: AsyncClient,
):
    team_id = await create_team(client)
    athlete_id = await create_athlete(client, team_id)
    await create_competition(client)

    response = await client.post(
        "/ranking",
        json={
            "athlete_id": athlete_id,
            "belt": "brown",
            "age_group": "Adult",
            "points": 10,
            "competition_name": "Copa Bandido",
        },
    )

    assert response.status_code == 422
