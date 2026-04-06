"""Pytest fixtures shared across all test modules."""
import asyncio
import uuid
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import fakeredis
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.models.notification import Notification, NotificationStatus

# ---------------------------------------------------------------------------
# Test database (SQLite in-memory via aiosqlite)
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def test_db(test_engine) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session
        await session.rollback()


# ---------------------------------------------------------------------------
# Fake Redis
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def test_redis():
    server = fakeredis.FakeAsyncRedis(decode_responses=True)
    yield server
    await server.aclose()


# ---------------------------------------------------------------------------
# Mock Resend
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_sendgrid():
    mock_client = MagicMock()
    mock_client.send.return_value = {"id": "test-email-id"}

    with patch("app.services.email.resend_client", mock_client):
        yield mock_client


# ---------------------------------------------------------------------------
# FastAPI test client
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def test_client(test_db, test_redis, mock_sendgrid) -> AsyncGenerator[AsyncClient, None]:
    from app.api.dependencies import get_db, get_redis
    from app.main import app

    async def override_get_db():
        yield test_db

    async def override_get_redis():
        return test_redis

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis

    # Patch publisher so tests don't need real Redis publish
    with patch("app.services.publisher.get_redis_pool", return_value=test_redis):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Sample notification factory
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_notification_data() -> dict[str, Any]:
    return {
        "recipient_email": "test@example.com",
        "subject": "Test Subject",
        "body": "Test body content.",
    }
