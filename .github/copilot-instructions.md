# GitHub Copilot Instructions

## Commands

### Running locally (without Docker)

```bash
# Copy and fill in credentials
cp .env.example .env

# Install runtime dependencies
pip install -r requirements.txt

# Install dev dependencies
pip install -r requirements-dev.txt

# Run database migrations
alembic upgrade head

# Start the API server (port 8000)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Start workers (in a separate terminal)
python -m app.workers.consumer

# Start the monitoring dashboard (port 8080)
uvicorn dashboard.main:app --reload --host 0.0.0.0 --port 8080
```

### Docker Compose (recommended)

```bash
# Build and start all services (api + 5 worker replicas + dashboard + postgres + redis)
docker compose up --build

# Scale workers manually (if not using deploy.replicas)
docker compose up --scale worker=5

# Stop everything
docker compose down

# Tear down including volumes
docker compose down -v
```

### Tests

```bash
# Run full test suite with coverage
pytest --cov=app --cov-report=term-missing

# Run a single test file
pytest tests/test_api.py -v

# Run a single test by name
pytest tests/test_workers.py::test_retry_handler_sends_to_dlq_at_max_retries -v
```

### Linting and type checking

```bash
# Lint and auto-fix
ruff check . --fix

# Format
ruff format .

# Type check
mypy app/ dashboard/
```

### Migrations

```bash
# Apply all pending migrations
alembic upgrade head

# Generate a new migration from model changes
alembic revision --autogenerate -m "describe_your_change"

# Downgrade one step
alembic downgrade -1

# Show current revision
alembic current
```

---

## Architecture

### Pub/Sub flow

```
POST /notifications
      │
      ▼
  FastAPI API (app/main.py)
      │  creates Notification row (status=pending) in PostgreSQL
      │
      ▼
  publisher.publish_notification()
      │  JSON payload → Redis PUBLISH email_notifications
      │
      ▼
  WorkerPool (app/workers/consumer.py)
      │  Redis SUBSCRIBE → asyncio.Queue
      │  5 concurrent asyncio worker tasks pull from queue
      │
      ▼
  process_message() per worker
      │  status → sending
      │
      ├── send_email() via Resend
      │       └── success → status=sent, sent_at=now
      │
      └── failure
              │
              ▼
          RetryHandler.handle_failure()
              │  retry_count < MAX_RETRIES → re-PUBLISH to main channel
              │                              (after exponential backoff delay)
              │                              status=pending, retry_count+1
              │
              └── retry_count >= MAX_RETRIES → PUBLISH to dead_letter channel
                                               status=dead_letter
```

### Worker pool pattern

`WorkerPool` (consumer.py) starts on API lifespan startup:
1. A single `redis_subscriber` coroutine subscribes to `settings.REDIS_CHANNEL` and pushes decoded JSON onto an `asyncio.Queue`.
2. `settings.WORKER_COUNT` (default 5) worker coroutines (`worker_loop`) consume from that queue concurrently.
3. Each worker maintains stats in the module-level `worker_status` dict (keyed by integer worker_id 0–4), which the dashboard reads.

### Retry / DLQ flow

- `RetryHandler.handle_failure()` is called whenever `send_email()` raises.
- Delay formula: `RETRY_BASE_DELAY * 2^attempt` (e.g. 2s, 4s, 8s for base=1.0).
- On each retry the notification row is updated: `retry_count += 1`, `status=pending`.
- After `MAX_RETRIES` failures the message is published to `DEAD_LETTER_CHANNEL` and the row is set to `status=dead_letter`.

### Dashboard data collection

`dashboard/routes.py::_collect_metrics()` aggregates:
- Per-status notification counts via a `GROUP BY` query on PostgreSQL.
- Redis client/connection info as a proxy for queue activity.
- In-process `worker_status` dict exported from `app.workers.consumer`.

The dashboard HTML auto-refreshes every 5 seconds via `<meta http-equiv="refresh" content="5">`.

---

## Key conventions

- **All DB access is async**: use `AsyncSession` and `await session.execute(...)`. Never import or call synchronous SQLAlchemy.
- **Pydantic v2**: use `@field_validator`, `@model_validator`, and `model_validate()`. Never use the Pydantic v1 `@validator` decorator.
- **Settings**: always import from `app.core.config` (`from app.core.config import settings`). Never read `os.environ` directly in application code.
- **Worker IDs** are integers `0` through `WORKER_COUNT - 1` (default `0`–`4`).
- **Notification status transitions**:
  - `pending` → `sending` → `sent` (success)
  - `sending` → `failed` (email error, retry available)
  - `failed` → `pending` (retry scheduled via RetryHandler)
  - `failed` → `dead_letter` (max retries exhausted)
- **Redis channel names** always come from `settings.REDIS_CHANNEL` / `settings.DEAD_LETTER_CHANNEL`. Never hardcode channel strings in application code.
- **Tests** use `fakeredis` + `aiosqlite` (SQLite in-memory). Never connect to a real Redis or PostgreSQL instance in tests.
- **Email client** (`resend_client` in `app/services/email.py`) is a module-level variable so tests can patch it with `patch("app.services.email.resend_client", ...)`.

## Project Goal
Portfolio project demonstrating distributed systems.
Target: handles 10K+ emails, sub-200ms dashboard response.

## Do Not Change
- Retry exponential backoff formula
- Worker count configuration pattern  
- Database schema once migrations are applied
- Redis channel names (always use settings)

## Code Style
- Type hints on all functions
- Docstrings on all service and worker functions
- No print statements, structured logging only