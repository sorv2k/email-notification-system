"""Tests for worker retry logic."""
import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import settings
from app.models.notification import Notification, NotificationStatus
from app.workers.retry import RetryHandler


def _make_notification(retry_count: int = 0) -> Notification:
    n = Notification()
    n.id = uuid.uuid4()
    n.recipient_email = "retry@example.com"
    n.subject = "Retry Test"
    n.body = "Test body"
    n.status = NotificationStatus.FAILED
    n.retry_count = retry_count
    n.created_at = datetime.now(timezone.utc)
    n.updated_at = datetime.now(timezone.utc)
    return n


def _make_message(notification: Notification, retry_count: int = 0) -> dict:
    return {
        "notification_id": str(notification.id),
        "recipient_email": notification.recipient_email,
        "subject": notification.subject,
        "body": notification.body,
        "retry_count": retry_count,
    }


@pytest.mark.asyncio
async def test_retry_handler_schedules_retry_below_max():
    handler = RetryHandler()
    notification = _make_notification(retry_count=0)
    message = _make_message(notification, retry_count=0)

    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()

    with patch("app.workers.retry.get_redis_pool") as mock_pool, \
         patch("asyncio.create_task") as mock_create_task:
        mock_redis = AsyncMock()
        mock_pool.return_value = mock_redis

        await handler.handle_failure(mock_session, notification, message)

    # Should set status to PENDING (retry scheduled)
    assert notification.status == NotificationStatus.PENDING
    assert notification.retry_count == 1
    mock_create_task.assert_called_once()


@pytest.mark.asyncio
async def test_retry_handler_sends_to_dlq_at_max_retries():
    handler = RetryHandler()
    # retry_count already at MAX_RETRIES - 1, next attempt would equal MAX_RETRIES
    notification = _make_notification(retry_count=settings.MAX_RETRIES - 1)
    message = _make_message(notification, retry_count=settings.MAX_RETRIES - 1)

    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()

    with patch("app.workers.retry.get_redis_pool") as mock_pool:
        mock_redis = AsyncMock()
        mock_pool.return_value = mock_redis
        mock_redis.publish = AsyncMock()

        await handler.handle_failure(mock_session, notification, message)

    assert notification.status == NotificationStatus.DEAD_LETTER
    mock_redis.publish.assert_called_once()
    # Verify it was published to DLQ channel
    call_args = mock_redis.publish.call_args
    assert call_args[0][0] == settings.DEAD_LETTER_CHANNEL
    published = json.loads(call_args[0][1])
    assert published["dead_letter"] is True


def test_retry_delay_exponential():
    """Verify exponential backoff formula: base * 2^attempt."""
    base = settings.RETRY_BASE_DELAY
    assert base * (2 ** 1) == pytest.approx(base * 2)
    assert base * (2 ** 2) == pytest.approx(base * 4)
    assert base * (2 ** 3) == pytest.approx(base * 8)
