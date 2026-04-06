# Email Notification System

An asynchronous email notification service that accepts notification requests via REST API, queues them in Redis, and processes them with background workers. Notifications are stored in PostgreSQL with automatic retries and exponential backoff for failed deliveries.

## Tech Stack

Python 3.11, FastAPI, PostgreSQL 16, Redis 7, SQLAlchemy, Alembic, Resend API, Docker

## Prerequisites

- Python 3.11 or higher
- PostgreSQL 16 (or Docker)
- Redis 7 (or Docker)
- Resend API key (get from resend.com)
- Docker and Docker Compose for containerized setup

## Running Locally

### With Docker Compose

```bash
cp .env.example .env
# Edit .env and add your RESEND_API_KEY
docker compose up --build
```

This starts the API at http://localhost:8000, dashboard at http://localhost:8080/dashboard, and 5 background workers.

### Without Docker

Start PostgreSQL and Redis:

```bash
docker run -d -p 5432:5432 \
  -e POSTGRES_USER=user -e POSTGRES_PASSWORD=pass \
  -e POSTGRES_DB=emaildb postgres:16-alpine

docker run -d -p 6379:6379 redis:7-alpine
```

Set up the application:

```bash
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env with your RESEND_API_KEY

alembic upgrade head
uvicorn app.main:app --reload
```

In separate terminals, start the dashboard and workers:

```bash
uvicorn dashboard.main:app --reload --port 8080
python -m app.workers.consumer
```

API documentation is available at http://localhost:8000/docs. Send notifications with POST requests to `/notifications` endpoint.
