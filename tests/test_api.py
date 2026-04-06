"""Tests for API endpoints."""
import uuid
from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_create_notification(test_client, sample_notification_data):
    with patch("app.services.publisher.get_redis_pool") as mock_pool:
        mock_redis = mock_pool.return_value
        mock_redis.publish = AsyncMock(return_value=0)  # type: ignore

        response = await test_client.post("/notifications", json=sample_notification_data)

    assert response.status_code == 201
    data = response.json()
    assert data["recipient_email"] == sample_notification_data["recipient_email"]
    assert data["subject"] == sample_notification_data["subject"]
    assert data["status"] == "pending"
    assert "id" in data


@pytest.mark.asyncio
async def test_create_notification_invalid_email(test_client):
    payload = {"recipient_email": "not-an-email", "subject": "Hi", "body": "Body"}
    response = await test_client.post("/notifications", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_notification_blank_subject(test_client):
    payload = {"recipient_email": "user@example.com", "subject": "   ", "body": "Body"}
    response = await test_client.post("/notifications", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_notification_not_found(test_client):
    random_id = uuid.uuid4()
    response = await test_client.get(f"/notifications/{random_id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_notification(test_client, sample_notification_data):
    with patch("app.services.publisher.get_redis_pool") as mock_pool:
        mock_redis = mock_pool.return_value
        mock_redis.publish = AsyncMock(return_value=0)  # type: ignore

        create_resp = await test_client.post("/notifications", json=sample_notification_data)

    notification_id = create_resp.json()["id"]
    get_resp = await test_client.get(f"/notifications/{notification_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == notification_id


@pytest.mark.asyncio
async def test_list_notifications(test_client, sample_notification_data):
    with patch("app.services.publisher.get_redis_pool") as mock_pool:
        mock_redis = mock_pool.return_value
        mock_redis.publish = AsyncMock(return_value=0)  # type: ignore

        await test_client.post("/notifications", json=sample_notification_data)

    response = await test_client.get("/notifications")
    assert response.status_code == 200
    body = response.json()
    assert "items" in body
    assert "total" in body
    assert body["total"] >= 1


@pytest.mark.asyncio
async def test_health_check(test_client):
    response = await test_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("ok", "degraded")
    assert "database" in data
    assert "redis" in data
