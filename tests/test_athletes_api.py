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


def athlete_payload(**overrides):
    payload = {
        "name": "Maria Silva",
        "cpf": "529.982.247-25",
        "email": "maria.silva@example.com",
        "phone": "11-99999.1234",
        "team_id": 1,
        "belt": "blue",
        "graduation_date": "2024-12-10",
        "birth_date": "2002-05-14",
    }
    payload.update(overrides)
    return payload


async def create_team(client: AsyncClient, name: str = "Gracie Barra") -> int:
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


async def test_create_and_get_athlete(client: AsyncClient):
    team_id = await create_team(client)
    athlete_response = await client.post("/athletes", json=athlete_payload(team_id=team_id))

    assert athlete_response.status_code == 201
    athlete = athlete_response.json()
    assert athlete["name"] == "Maria Silva"
    assert athlete["cpf"] == "52998224725"
    assert athlete["email"] == "maria.silva@example.com"
    assert athlete["phone"] == "11-99999.1234"
    assert athlete["team_id"] == team_id
    assert athlete["team"]["name"] == "Gracie Barra"
    assert athlete["graduation_date"] == "2024-12-10"
    assert athlete["birth_date"] == "2002-05-14"
    assert "category" not in athlete
    assert "category_id" not in athlete
    assert isinstance(athlete["age"], int)

    get_response = await client.get(f"/athletes/{athlete['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["team"]["name"] == "Gracie Barra"


async def test_frontend_is_served(client: AsyncClient):
    root_response = await client.get("/")
    response = await client.get("/cadastros")
    teams_response = await client.get("/equipes")

    assert root_response.status_code == 307
    assert root_response.headers["location"] == "/cadastros"
    assert response.status_code == 200
    assert "Cadastro de Atletas" in response.text
    assert "Dados Federativos" in response.text
    assert "Dados da Equipe" not in response.text
    assert "Cadastrar equipe" not in response.text
    assert "/static/athletes.js" in response.text
    assert "/equipes" in response.text
    assert "Categoria" not in response.text
    assert "categoryId" not in response.text
    assert "Email" in response.text
    assert "Data da graduacao" in response.text
    assert "Carregando equipes" in response.text
    assert teams_response.status_code == 200
    assert "Cadastro de Equipes" in teams_response.text
    assert "Dados da Equipe" in teams_response.text
    assert "Cadastrar equipe" in teams_response.text
    assert "/static/teams.js" in teams_response.text
    assert "/cadastros" in teams_response.text


async def test_frontend_assets_include_light_theme_cpf_validation_and_team_combobox(
    client: AsyncClient,
):
    styles_response = await client.get("/static/styles.css")
    athlete_script_response = await client.get("/static/athletes.js")
    team_script_response = await client.get("/static/teams.js")

    assert styles_response.status_code == 200
    assert "color-scheme: light" in styles_response.text
    assert athlete_script_response.status_code == 200
    assert "function isValidCpf" in athlete_script_response.text
    assert "setCustomValidity" in athlete_script_response.text
    assert "warnInvalidCpfOnBlur" in athlete_script_response.text
    assert "reportValidity" in athlete_script_response.text
    assert "category_id" not in athlete_script_response.text
    assert "graduation_date" in athlete_script_response.text
    assert "function loadTeams" in athlete_script_response.text
    assert "/teams?limit=100&offset=0" in athlete_script_response.text
    assert "team_id" in athlete_script_response.text
    assert team_script_response.status_code == 200
    assert "function buildTeamPayload" in team_script_response.text
    assert "function submitTeam" in team_script_response.text
    assert "maskTeamPhone" in team_script_response.text


async def test_create_categories_bulk(client: AsyncClient):
    response = await client.post(
        "/categories/bulk",
        json=[
            {"weight_class": "Male - Rooster (-57.5 kg)", "belt": "white", "age_group": "Adult"},
            {"weight_class": "Male - Light (-76.0 kg)", "belt": "blue", "age_group": "Adult"},
        ],
    )

    assert response.status_code == 201
    assert len(response.json()) == 2


async def test_prevent_duplicate_athlete_same_name_and_team(client: AsyncClient):
    team_id = await create_team(client)
    payload = athlete_payload(cpf="390.533.447-05", email="joao@example.com", team_id=team_id)

    assert (await client.post("/athletes", json=payload)).status_code == 201
    duplicate_response = await client.post(
        "/athletes",
        json={**payload, "cpf": "111.444.777-35", "email": "joao.outro@example.com"},
    )
    assert duplicate_response.status_code == 409


async def test_reject_athlete_under_four_today(client: AsyncClient):
    team_id = await create_team(client)
    athlete_response = await client.post(
        "/athletes",
        json=athlete_payload(
            name="Pedro Lima",
            cpf="935.411.347-80",
            email="pedro@example.com",
            phone="41-99999.1234",
            team_id=team_id,
            belt="white",
            birth_date="2024-08-11",
        ),
    )
    assert athlete_response.status_code == 422


async def test_reject_invalid_cpf(client: AsyncClient):
    team_id = await create_team(client)
    athlete_response = await client.post(
        "/athletes",
        json=athlete_payload(
            name="Carlos Mendes",
            cpf="111.111.111-11",
            email="carlos@example.com",
            phone="51-99999.1234",
            team_id=team_id,
            belt="white",
            birth_date="1998-04-10",
        ),
    )
    assert athlete_response.status_code == 422


async def test_prevent_duplicate_athlete_same_cpf(client: AsyncClient):
    team_id = await create_team(client)
    first_payload = athlete_payload(
        name="Lucas Pereira",
        cpf="529.982.247-25",
        email="lucas@example.com",
        phone="61-99999.1234",
        team_id=team_id,
        belt="white",
        birth_date="1998-07-02",
    )
    second_payload = {
        **first_payload,
        "name": "Lucas Pereira Filho",
        "email": "lucas.filho@example.com",
        "phone": "61-98888.1234",
    }

    assert (await client.post("/athletes", json=first_payload)).status_code == 201
    duplicate_response = await client.post("/athletes", json=second_payload)
    assert duplicate_response.status_code == 409


async def test_prevent_duplicate_athlete_same_email(client: AsyncClient):
    team_id = await create_team(client)
    first_payload = athlete_payload(email="duplicado@example.com", team_id=team_id)
    second_payload = athlete_payload(
        name="Outra Pessoa",
        cpf="390.533.447-05",
        email="DUPLICADO@example.com",
        phone="21-99999.1234",
        team_id=team_id,
    )

    assert (await client.post("/athletes", json=first_payload)).status_code == 201
    duplicate_response = await client.post("/athletes", json=second_payload)
    assert duplicate_response.status_code == 409


async def test_reject_invalid_email(client: AsyncClient):
    team_id = await create_team(client)
    athlete_response = await client.post(
        "/athletes",
        json=athlete_payload(email="email-invalido", team_id=team_id),
    )
    assert athlete_response.status_code == 422


async def test_reject_invalid_phone_format(client: AsyncClient):
    team_id = await create_team(client)
    athlete_response = await client.post(
        "/athletes",
        json=athlete_payload(
            name="Bruna Almeida",
            cpf="390.533.447-05",
            email="bruna@example.com",
            phone="(11) 99999-1234",
            team_id=team_id,
            belt="white",
            birth_date="1997-11-03",
        ),
    )
    assert athlete_response.status_code == 422
