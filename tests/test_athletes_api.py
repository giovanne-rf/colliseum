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
        "sex": "female",
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
    assert athlete["sex"] == "female"
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


async def test_create_athletes_bulk(client: AsyncClient):
    team_id = await create_team(client)
    response = await client.post(
        "/athletes/bulk",
        json=[
            athlete_payload(team_id=team_id),
            athlete_payload(
                name="Joao Souza",
                cpf="390.533.447-05",
                email="joao.souza@example.com",
                phone="11-98888.1234",
                team_id=team_id,
                belt="purple",
                birth_date="1995-09-20",
            ),
        ],
    )

    assert response.status_code == 201
    athletes = response.json()
    assert [athlete["name"] for athlete in athletes] == ["Maria Silva", "Joao Souza"]
    assert athletes[0]["cpf"] == "52998224725"
    assert athletes[1]["cpf"] == "39053344705"
    assert athletes[0]["team"]["name"] == "Gracie Barra"
    assert athletes[1]["team"]["name"] == "Gracie Barra"


async def test_reject_athletes_bulk_duplicate_cpf_without_partial_insert(client: AsyncClient):
    team_id = await create_team(client)
    response = await client.post(
        "/athletes/bulk",
        json=[
            athlete_payload(team_id=team_id),
            athlete_payload(
                name="Joao Souza",
                email="joao.souza@example.com",
                phone="11-98888.1234",
                team_id=team_id,
            ),
        ],
    )

    assert response.status_code == 409

    list_response = await client.get("/athletes")
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 0


async def test_frontend_is_served(client: AsyncClient):
    root_response = await client.get("/")
    response = await client.get("/cadastros")
    teams_response = await client.get("/equipes")
    competitions_response = await client.get("/competicoes")
    registrations_response = await client.get("/inscricoes")
    brackets_response = await client.get("/chaves")
    checkin_response = await client.get("/checagem")

    assert root_response.status_code == 307
    assert root_response.headers["location"] == "/cadastros"
    assert response.status_code == 200
    assert "Colliseum" in response.text
    assert "react.production.min.js" in response.text
    assert "/static/react/app.jsx" in response.text
    assert "ibjjf-responsive-20260505" in response.text
    assert "svg-connectors-20260505" in response.text
    assert "/equipes" in response.text
    assert "/competicoes" in response.text
    assert "/inscricoes" in response.text
    assert "/chaves" in response.text
    assert "/checagem" in response.text
    assert teams_response.status_code == 200
    assert "/static/react/app.jsx" in teams_response.text
    assert "/cadastros" in teams_response.text
    assert "/competicoes" in teams_response.text
    assert "/inscricoes" in teams_response.text
    assert "/chaves" in teams_response.text
    assert "/checagem" in teams_response.text
    assert competitions_response.status_code == 200
    assert "/static/react/app.jsx" in competitions_response.text
    assert "/cadastros" in competitions_response.text
    assert registrations_response.status_code == 200
    assert "/static/react/app.jsx" in registrations_response.text
    assert brackets_response.status_code == 200
    assert "Chaves em formato paisagem" in brackets_response.text
    assert "/static/react/app.jsx" in brackets_response.text
    assert checkin_response.status_code == 200
    assert "/static/react/app.jsx" in checkin_response.text


async def test_frontend_assets_include_light_theme_cpf_validation_and_team_combobox(
    client: AsyncClient,
):
    styles_response = await client.get("/static/styles.css")
    react_shell_response = await client.get("/static/react.html")
    react_app_response = await client.get("/static/react/app.jsx")

    assert styles_response.status_code == 200
    assert "color-scheme: light" in styles_response.text
    assert react_shell_response.status_code == 200
    assert "react.production.min.js" in react_shell_response.text
    assert "/static/react/app.jsx" in react_shell_response.text
    assert react_app_response.status_code == 200
    assert "COLLISEUM" in react_app_response.text
    assert "site-nav" in react_app_response.text
    assert "function AthletesPage" in react_app_response.text
    assert "function TeamsPage" in react_app_response.text
    assert "function CompetitionsPage" in react_app_response.text
    assert "function RegistrationsPage" in react_app_response.text
    assert "function BracketsPage" in react_app_response.text
    assert "function CheckinPage" in react_app_response.text
    assert 'mat_count: "4"' in react_app_response.text
    assert "12 MATS" in react_app_response.text
    assert "registration-row" in react_app_response.text
    assert "/athletes/check-cpf?cpf=" in react_app_response.text
    assert "CPF ja cadastrado para outro atleta." in react_app_response.text
    assert "const cpfAvailable = await validateCpfOnBlur();" in react_app_response.text
    assert "/teams?limit=100&offset=0" in react_app_response.text
    assert "/athletes?belt=black&limit=100&offset=0" in react_app_response.text
    assert "registration-options" in react_app_response.text
    assert "generate-all" in react_app_response.text
    assert "BRACKET {index}/2" in react_app_response.text
    assert "FINALS" in react_app_response.text
    assert "function buildConnectorPath" in react_app_response.text
    assert "ibjjf-connectors" in react_app_response.text


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


async def test_allow_white_belt_at_any_valid_age(client: AsyncClient):
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
    assert athlete_response.status_code == 201


@pytest.mark.parametrize(
    ("belt", "birth_date", "minimum_age"),
    [
        ("gray", "2023-01-01", 4),
        ("yellow_black", "2020-01-01", 7),
        ("orange_white", "2018-01-01", 10),
        ("green_black", "2015-01-01", 13),
        ("blue", "2011-01-01", 16),
        ("purple", "2011-01-01", 16),
        ("brown", "2009-01-01", 18),
        ("black", "2008-01-01", 19),
        ("red_black", "1980-01-01", 50),
        ("red_white", "1975-01-01", 57),
        ("red", "1965-01-01", 67),
    ],
)
async def test_reject_athlete_below_minimum_age_for_belt(
    client: AsyncClient,
    belt: str,
    birth_date: str,
    minimum_age: int,
):
    team_id = await create_team(client)
    athlete_response = await client.post(
        "/athletes",
        json=athlete_payload(
            name=f"Atleta {belt}",
            cpf="935.411.347-80",
            email=f"{belt}@example.com",
            phone="41-99999.1234",
            team_id=team_id,
            belt=belt,
            birth_date=birth_date,
            graduation_date="2025-01-01",
        ),
    )

    assert athlete_response.status_code == 422
    assert str(minimum_age) in athlete_response.text


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
    check_response = await client.get("/athletes/check-cpf?cpf=529.982.247-25")
    assert check_response.status_code == 200
    assert check_response.json()["exists"] is True
    assert check_response.json()["cpf"] == "52998224725"

    available_response = await client.get("/athletes/check-cpf?cpf=123.456.789-09")
    assert available_response.status_code == 200
    assert available_response.json()["exists"] is False

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
