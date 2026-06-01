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
    academies_response = await client.get("/academias")
    academy_edit_response = await client.get("/academias/123")
    teams_response = await client.get("/equipes")
    competitions_response = await client.get("/competicoes")
    registrations_response = await client.get("/inscricoes")
    brackets_response = await client.get("/chaves")
    saved_brackets_response = await client.get("/chaves/salvas")
    bracket_by_id_response = await client.get("/chaves/123")
    schedule_response = await client.get("/cronograma")
    checkin_response = await client.get("/checagem")
    weighin_response = await client.get("/checkin/pesagem")
    ready_checkin_response = await client.get("/checkin")
    final_check_response = await client.get("/checagem-final")
    check_panel_response = await client.get("/checagem/painel")

    assert root_response.status_code == 307
    assert root_response.headers["location"] == "/cadastros"
    assert response.status_code == 200
    assert "FJJPE" in response.text
    assert "react.production.min.js" in response.text
    assert "/static/react/app.js" in response.text
    assert "bracket-split-20260601" in response.text
    assert "/academias" in response.text
    assert "/equipes" in response.text
    assert "/competicoes" in response.text
    assert "/inscricoes" in response.text
    assert "/chaves" in response.text
    assert "/checagem" in response.text
    assert academies_response.status_code == 200
    assert "/static/react/app.js" in academies_response.text
    assert academy_edit_response.status_code == 200
    assert "/static/react/app.js" in academy_edit_response.text
    assert teams_response.status_code == 200
    assert "/static/react/app.js" in teams_response.text
    assert "/cadastros" in teams_response.text
    assert "/competicoes" in teams_response.text
    assert "/inscricoes" in teams_response.text
    assert "/chaves" in teams_response.text
    assert "/checagem" in teams_response.text
    assert competitions_response.status_code == 200
    assert "/static/react/app.js" in competitions_response.text
    assert "/cadastros" in competitions_response.text
    assert registrations_response.status_code == 200
    assert "/static/react/app.js" in registrations_response.text
    assert brackets_response.status_code == 200
    assert "Chaves em formato paisagem" in brackets_response.text
    assert "/static/react/app.js" in brackets_response.text
    assert saved_brackets_response.status_code == 200
    assert "/static/react/app.js" in saved_brackets_response.text
    assert bracket_by_id_response.status_code == 200
    assert "/static/react/app.js" in bracket_by_id_response.text
    assert schedule_response.status_code == 200
    assert "/static/react/app.js" in schedule_response.text
    assert checkin_response.status_code == 200
    assert "/static/react/app.js" in checkin_response.text
    assert weighin_response.status_code == 200
    assert "/static/react/app.js" in weighin_response.text
    assert ready_checkin_response.status_code == 200
    assert "/static/react/app.js" in ready_checkin_response.text
    assert final_check_response.status_code == 200
    assert "/static/react/app.js" in final_check_response.text
    assert check_panel_response.status_code == 200
    assert "/static/react/app.js" in check_panel_response.text


async def test_frontend_assets_include_light_theme_cpf_validation_and_team_combobox(
    client: AsyncClient,
):
    styles_response = await client.get("/static/styles.css")
    react_shell_response = await client.get("/static/react.html")
    react_app_response = await client.get("/static/react/app.jsx")
    react_bundle_response = await client.get("/static/react/app.js")

    assert styles_response.status_code == 200
    assert "color-scheme: light" in styles_response.text
    assert react_shell_response.status_code == 200
    assert "react.production.min.js" in react_shell_response.text
    assert "/static/react/app.js?v=bracket-split-20260601" in react_shell_response.text
    assert "@babel/standalone" not in react_shell_response.text
    assert 'type="text/babel"' not in react_shell_response.text
    assert '<link rel="icon" type="image/png" href="/static/fjjpe-logo.png" />' in react_shell_response.text
    assert react_app_response.status_code == 200
    assert react_bundle_response.status_code == 200
    assert "React.createElement" in react_bundle_response.text
    assert "FJJPE" in react_app_response.text
    assert "fjjpe-logo.png" in react_app_response.text
    assert "site-nav" in react_app_response.text
    assert "function AthletesPage" in react_app_response.text
    assert '{path === "/cadastros" && <AthletesPage />}' in react_app_response.text
    assert "function AtletaEditPage" in react_app_response.text
    assert "Alterar Cadastro de Atleta" in react_app_response.text
    assert "Atualizar" in react_app_response.text
    assert 'label: "ACADEMIAS"' in react_app_response.text
    assert '["/academias", "Listagem"]' in react_app_response.text
    assert '["/equipes", "Cadastro"]' in react_app_response.text
    assert "function AcademiesListPage" in react_app_response.text
    assert "function AcademyEditPage" in react_app_response.text
    assert "Academias Cadastradas" in react_app_response.text
    assert "Alterar Cadastro de Academia" in react_app_response.text
    assert "/teams/${teamId}" in react_app_response.text
    assert "function TeamsPage" in react_app_response.text
    assert "function CompetitionsPage" in react_app_response.text
    assert "function RegistrationsPage" in react_app_response.text
    assert "function BracketsPage" in react_app_response.text
    assert "function SavedBracketsPage" in react_app_response.text
    assert "function BracketByIdPage" in react_app_response.text
    assert "function SchedulePage" in react_app_response.text
    assert "function FightPanel" in react_app_response.text
    assert "function fightDurationSeconds" in react_app_response.text
    assert "function CheckinPage" in react_app_response.text
    assert "function FinalCheckPage" in react_app_response.text
    assert "function CheckOverviewPage" in react_app_response.text
    assert "function CheckPanelPage" in react_app_response.text
    assert "function WeighinPage" in react_app_response.text
    assert "function AthleteListPage" in react_app_response.text
    assert "/checkin/pesagem" in react_app_response.text
    assert "/checkin" in react_app_response.text
    assert '["/chaves", "GERAR CHAVES"]' in react_app_response.text
    assert '["/chaves/salvas", "CHAVES SALVAS"]' in react_app_response.text
    assert '["/cronograma", "CRONOGRAMA"]' in react_app_response.text
    assert 'label: "PAINEL DE CHECAGEM"' in react_app_response.text
    assert '["/checkin/pesagem", "Pesagem"]' in react_app_response.text
    assert '["/checkin", "Checkin"]' in react_app_response.text
    assert '["/checagem", "Checagem geral"]' in react_app_response.text
    assert '["/checagem-final", "Checagem final"]' in react_app_response.text
    assert '["/checagem/painel", "Painel Geral"]' in react_app_response.text
    assert "Listagem de Atletas" in react_app_response.text
    assert "Status da checagem" in react_app_response.text
    assert "Iniciar checkin?" in react_app_response.text
    assert "Checkin Iniciado" in react_app_response.text
    assert "Checkin finalizado" in react_app_response.text
    assert "No weight" in react_app_response.text
    assert "Categoria em checagem" in react_app_response.text
    assert "Proxima categoria" in react_app_response.text
    assert "Checkin ainda nao iniciado para esta categoria." in react_app_response.text
    assert "Encerrar checkin?" in react_app_response.text
    assert "Nenhum atleta encontrado para os filtros selecionados." in react_app_response.text
    assert "{filtered.length} atleta(s) exibido(s) de {rows.length} na checagem final" in react_app_response.text
    assert "Nova pesagem bloqueada" in react_app_response.text
    assert "CHECKED" in react_app_response.text
    assert "NO CHECKED" in react_app_response.text
    assert "READY TO FIGHT" not in react_app_response.text
    assert "NOT READY TO FIGHT" not in react_app_response.text
    assert "Atleta ja foi checado. Status: Checked." in react_app_response.text
    assert "Status: Out of weight." in react_app_response.text
    assert "Status: No Show" in react_app_response.text
    assert "Atleta nao bateu o peso" in react_app_response.text
    assert "checkin-options" in react_app_response.text
    assert 'mat_count: "4"' in react_app_response.text
    assert 'start_time: "09:00"' in react_app_response.text
    assert 'competition_type: "Oficial"' in react_app_response.text
    assert 'competition_days: "2"' in react_app_response.text
    assert "Hora de inicio" in react_app_response.text
    assert "Tipo de campeonato" in react_app_response.text
    assert "Chancelado" in react_app_response.text
    assert "Dias de competicao" in react_app_response.text
    assert "Confirmar criacao da competicao?" in react_app_response.text
    assert "Datas inferidas" in react_app_response.text
    assert "dia_1" not in react_app_response.text
    assert "12 MATS" in react_app_response.text
    assert "registration-row" in react_app_response.text
    assert "/athletes/check-cpf?cpf=" in react_app_response.text
    assert "CPF ja cadastrado para outro atleta." in react_app_response.text
    assert "const cpfAvailable = await validateCpfOnBlur();" in react_app_response.text
    assert "/teams?limit=${limit}&offset=${offset}" in react_app_response.text
    assert "function loadAllTeams" in react_app_response.text
    assert "Selecione a categoria de peso" in react_app_response.text
    assert "category.weight_class" in react_app_response.text
    assert "Selecione a academia do atleta." in react_app_response.text
    assert "Sem academia (faixa preta)" in react_app_response.text
    assert "Atleta sem academia cadastrada" in react_app_response.text
    assert "data.athlete.team_id ? String(data.athlete.team_id) : \"\"" in react_app_response.text
    assert "/athletes?belt=black&limit=100&offset=0" in react_app_response.text
    assert "registration-options" in react_app_response.text
    assert "Gerar todas" not in react_app_response.text
    assert "ja possuem chave salva" in react_app_response.text
    assert "Consulta de Chaves" in react_app_response.text
    assert "Consulta da Chave" in react_app_response.text
    assert "/competitions/brackets/${bracketId}" in react_app_response.text
    assert "URL da chave" in react_app_response.text
    assert "Abrir URL" in react_app_response.text
    assert "Vencedor da luta" in react_app_response.text
    assert "function originMatchForSlot" in react_app_response.text
    assert "/schedule" in react_app_response.text
    assert "Horarios estimados por categoria" in react_app_response.text
    assert "ibjjf-match-schedule" in react_app_response.text
    assert "Exibicao da Chave" in react_app_response.text
    assert "Categoria de idade" in react_app_response.text
    assert "Categoria de peso" in react_app_response.text
    assert "Selecione a faixa, a categoria de idade e a categoria de peso" in react_app_response.text
    assert "Gerar chaves" not in react_app_response.text
    assert "ID {bracket.id}" in react_app_response.text
    assert "BRACKET {index}/2" in react_app_response.text
    assert "FINALS" in react_app_response.text
    assert "function buildConnectorPath" in react_app_response.text
    assert "ibjjf-connectors" in react_app_response.text
    assert "Classificacao Final" in react_app_response.text
    assert "function bracketPodiumItems" in react_app_response.text
    assert "bracket-check-status" in react_app_response.text
    assert "no-fighters" in styles_response.text
    assert "fight-clock" in react_app_response.text
    assert "width: 100vw" in styles_response.text
    assert "height: 100vh" in styles_response.text
    assert "Finalizar por tempo" in react_app_response.text
    assert "Finalizacao" in react_app_response.text
    assert "Desclassificacao" in react_app_response.text
    assert "Encerrar luta por tempo?" in react_app_response.text
    assert "Luta encerrada" not in react_app_response.text
    assert "Luta ja finalizada" in react_app_response.text
    assert "Nao e possivel reabrir ou alterar o resultado." in react_app_response.text
    assert "match-result-dot" in react_app_response.text
    assert "result-loser" in react_app_response.text
    assert "result-winner" in react_app_response.text
    assert "CHECKED" in react_app_response.text


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


async def test_require_team_unless_athlete_is_black_belt(client: AsyncClient):
    white_response = await client.post(
        "/athletes",
        json=athlete_payload(team_id=None),
    )
    assert white_response.status_code == 422
    assert "academy" in white_response.text

    black_response = await client.post(
        "/athletes",
        json=athlete_payload(
            name="Faixa Preta Sem Academia",
            cpf="390.533.447-05",
            email="preta.sem.academia@example.com",
            phone="81-98888.1234",
            team_id=None,
            belt="black",
            birth_date="1990-01-01",
            graduation_date="2024-01-01",
        ),
    )
    assert black_response.status_code == 201
    assert black_response.json()["team_id"] is None


async def test_reject_update_that_removes_team_from_non_black_belt(client: AsyncClient):
    team_id = await create_team(client)
    athlete_response = await client.post("/athletes", json=athlete_payload(team_id=team_id))
    athlete_id = athlete_response.json()["id"]

    update_response = await client.put(f"/athletes/{athlete_id}", json={"team_id": None})

    assert update_response.status_code == 422
    assert "academy" in update_response.text


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

