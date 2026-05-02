# Colliseum API

Production-ready FastAPI backend for athlete registration in a Brazilian Jiu-Jitsu competition.

## Stack

- Python 3.11+
- FastAPI
- SQLAlchemy 2.x async ORM
- SQLite for development
- Pydantic v2
- Alembic-ready migrations

## Project Structure

```text
app/
  main.py
  core/
  database/
  models/
  routers/
  schemas/
  services/
alembic/
  env.py
  versions/
tests/
```

## Run Locally

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
copy .env.example .env
uvicorn app.main:app --reload
```

OpenAPI docs:

- Swagger UI: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc

On startup, the development database tables are created automatically. Alembic scaffolding is included for production migration workflows.

## Example Athlete Request

```json
{
  "name": "Maria Silva",
  "cpf": "529.982.247-25",
  "email": "maria.silva@example.com",
  "phone": "11-99999.1234",
  "team_id": 1,
  "belt": "blue",
  "graduation_date": "2024-12-10",
  "birth_date": "2002-05-14"
}
```

`birth_date` is stored as the source of truth. Competition categories are managed separately and should be attached during registration for a specific tournament.

## Tests

```bash
pytest
```
