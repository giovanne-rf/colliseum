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


def team_payload(**overrides):
    payload = {
        "name": "Gracie Barra",
        "created_date": "2002-04-12",
        "responsible": "Carlos Gracie Jr.",
        "phone": "11-99999-1234",
    }
    payload.update(overrides)
    return payload


def athlete_payload(**overrides):
    payload = {
        "name": "Carlos Gracie Jr.",
        "cpf": "529.982.247-25",
        "email": "carlos.gracie@example.com",
        "phone": "11-98888.1234",
        "sex": "male",
        "team_id": None,
        "belt": "black",
        "graduation_date": "2024-01-01",
        "birth_date": "1990-01-01",
    }
    payload.update(overrides)
    return payload


async def test_create_list_get_update_and_delete_team(client: AsyncClient):
    create_response = await client.post("/teams", json=team_payload())

    assert create_response.status_code == 201
    team = create_response.json()
    assert team["name"] == "Gracie Barra"
    assert team["phone"] == "11-99999-1234"

    list_response = await client.get("/teams")
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1

    get_response = await client.get(f"/teams/{team['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["responsible"] == "Carlos Gracie Jr."

    update_response = await client.put(
        f"/teams/{team['id']}",
        json={"responsible": "Marcio Feitosa", "phone": "21-98888-1234"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["responsible"] == "Marcio Feitosa"

    delete_response = await client.delete(f"/teams/{team['id']}")
    assert delete_response.status_code == 204

    missing_response = await client.get(f"/teams/{team['id']}")
    assert missing_response.status_code == 404


async def test_create_team_assigns_responsible_athlete_to_team(client: AsyncClient):
    athlete_response = await client.post("/athletes", json=athlete_payload())
    assert athlete_response.status_code == 201
    assert athlete_response.json()["team_id"] is None

    team_response = await client.post("/teams", json=team_payload())
    assert team_response.status_code == 201
    team = team_response.json()

    updated_athlete_response = await client.get(f"/athletes/{athlete_response.json()['id']}")
    assert updated_athlete_response.status_code == 200
    assert updated_athlete_response.json()["team_id"] == team["id"]
    assert updated_athlete_response.json()["team"]["name"] == "Gracie Barra"


async def test_update_team_assigns_new_responsible_athlete_to_team(client: AsyncClient):
    athlete_response = await client.post(
        "/athletes",
        json=athlete_payload(
            name="Marcio Feitosa",
            cpf="390.533.447-05",
            email="marcio@example.com",
        ),
    )
    team_response = await client.post("/teams", json=team_payload(responsible="Carlos Gracie Jr."))
    team = team_response.json()

    update_response = await client.put(
        f"/teams/{team['id']}",
        json={"responsible": "Marcio Feitosa"},
    )

    assert update_response.status_code == 200
    updated_athlete_response = await client.get(f"/athletes/{athlete_response.json()['id']}")
    assert updated_athlete_response.json()["team_id"] == team["id"]


async def test_prevent_duplicate_team_name(client: AsyncClient):
    assert (await client.post("/teams", json=team_payload())).status_code == 201
    duplicate_response = await client.post(
        "/teams",
        json=team_payload(phone="31-99999-1234"),
    )

    assert duplicate_response.status_code == 409


async def test_create_team_without_responsible(client: AsyncClient):
    payload = team_payload()
    payload.pop("responsible")

    response = await client.post("/teams", json=payload)

    assert response.status_code == 201
    assert response.json()["responsible"] is None


async def test_create_teams_bulk(client: AsyncClient):
    response = await client.post(
        "/teams/bulk",
        json=[
            {
                "name": "Gracie Barra",
                "created_date": "2002-04-12",
                "responsible": "Carlos Gracie Jr.",
                "phone": "11-99999-1234",
            },
            {
                "name": "Alliance",
                "created_date": "1993-01-01",
                "responsible": "Fabio Gurgel",
                "phone": "21-99999-1234",
            },
        ],
    )

    assert response.status_code == 201
    assert len(response.json()) == 2


async def test_reject_invalid_team_phone_format(client: AsyncClient):
    response = await client.post(
        "/teams",
        json=team_payload(phone="11-99999.1234"),
    )

    assert response.status_code == 422


async def test_reject_future_created_date(client: AsyncClient):
    response = await client.post(
        "/teams",
        json=team_payload(created_date="2999-01-01"),
    )

    assert response.status_code == 422
