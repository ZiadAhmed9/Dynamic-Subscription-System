# Dynamic Subscription System

Configuration-driven subscription engine built with Python, Flask, and SQLAlchemy.

## Overview
This system lets communities manage subscriptions for services (car wash, gardening, pool cleaning, etc.) without backend code changes. New services and plans are created through API endpoints.

## Prerequisites
- Python 3.11+
- `pip`
- Optional: Docker Desktop (for containerized run)

## Quick Start (Recommended: Local SQLite)

1. Create and activate a virtual environment.

```bash
python -m venv venv
```

PowerShell:
```powershell
.\venv\Scripts\Activate.ps1
```

Command Prompt (`cmd.exe`):
```bat
venv\Scripts\activate.bat
```

Linux/macOS:
```bash
source venv/bin/activate
```

2. Install dependencies.

```bash
pip install -r requirements.txt
```

3. Seed demo data (also creates tables).

```bash
python seed.py
```

4. Start the server.

```bash
python -m flask --app app run
```

5. Open Swagger UI.

`http://localhost:5000/`

## Docker Setup (PostgreSQL + API)

1. Build and start containers.

```bash
docker compose up --build -d
```

2. Seed demo data inside the API container.

```bash
docker compose exec api python seed.py
```

3. Open Swagger UI.

`http://localhost:5000/`

4. Stop containers when done.

```bash
docker compose down
```

## Run Tests

```bash
python -m pytest tests -v --tb=short
```

## Run Live API Smoke Test
Start the server first, then run:

```bash
python postman_test.py
```

## API Endpoints

### Mobile (`/mobile`)
- `GET /mobile/services` - List active services with plans
- `GET /mobile/customers/<id>/assets` - List customer assets (optional asset type filter)
- `GET /mobile/customers/<id>/services/<service_id>/assets` - List customer assets applicable to a service
- `POST /mobile/subscriptions` - Create a subscription request
- `GET /mobile/subscriptions/<id>` - Get request details and cost breakdown

### Dashboard (`/dashboard`)
- `POST /dashboard/services` - Create service
- `PUT /dashboard/services/<id>` - Update service
- `GET /dashboard/services` - List services
- `POST /dashboard/plans` - Create plan with rules JSON
- `PUT /dashboard/plans/<id>` - Update plan and rules
- `GET /dashboard/plans` - List plans
- `GET /dashboard/subscriptions` - List requests (supports filters)
- `PATCH /dashboard/subscriptions/<id>/status` - Update request status
- `POST /dashboard/customers` - Create customer
- `POST /dashboard/customers/<id>/assets` - Add customer asset

## Architecture

```text
API Layer (Flask-RESTX): HTTP handling, docs
Service Layer: use-case orchestration
Domain Layer: rule engine and pricing engine
Repository Layer: SQLAlchemy data access
```

## Tech Stack

- Python 3.11
- Flask (App Factory Pattern)
- Flask-RESTX (Swagger)
- SQLAlchemy (ORM)
- Pydantic (Validation)
- PostgreSQL (Docker setup)
- SQLite (Local dev)
- Pytest (Testing)
- Docker & Docker Compose

## Project Structure

```text
app/
  __init__.py            # Flask app factory
  extensions.py          # SQLAlchemy singleton
  config/settings.py     # Environment configs
  domain/                # Models, rule engine, pricing engine
  repositories/          # BaseRepository + domain repositories
  services/              # Use-case services
  schemas/               # Pydantic validation
  api/                   # Mobile and dashboard endpoints
```

## Database Design
![Database Design](images/image.png)

## Design Decisions

- Layered architecture to isolate business logic from HTTP concerns.
- Rule engine and pricing logic are configuration-driven (JSON).
- SQLite for simplicity in local development.
- PostgreSQL for production-grade Docker setup.

## Notes
- Default local database is SQLite (`dev.db`) unless `DATABASE_URL` is set.
- Rule and pricing logic is data-driven from plan JSON rules.
- New services can be added through dashboard endpoints without code changes.
