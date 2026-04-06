import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.redis import get_redis_pool
from app.models.notification import Notification, NotificationStatus

logger = logging.getLogger(__name__)


class RetryHandler:
    """Handles retry logic with exponential backoff and dead-letter queue."""

    async def handle_failure(
        self,
        session: AsyncSession,
        notification: Notification,
        message: dict[str, Any],
    ) -> None:
        next_retry = notification.retry_count + 1

        if next_retry >= settings.MAX_RETRIES:
            await self._send_to_dlq(session, notification, message)
        else:
            await self._schedule_retry(session, notification, message, next_retry)

    async def _schedule_retry(
        self,
        session: AsyncSession,
        notification: Notification,
        message: dict[str, Any],
        attempt: int,
    ) -> None:
        delay = settings.RETRY_BASE_DELAY * (2 ** attempt)
        logger.info(
            "Scheduling retry %d for notification %s in %.1fs",
            attempt,
            notification.id,
            delay,
        )

        notification.retry_count = attempt
        notification.status = NotificationStatus.PENDING
        notification.updated_at = datetime.now(timezone.utc)
        await session.commit()

        # Re-publish after the backoff delay
        asyncio.create_task(
            self._delayed_republish(message, attempt, delay),
            name=f"retry-{notification.id}-{attempt}",
        )

    async def _delayed_republish(
        self, message: dict[str, Any], attempt: int, delay: float
    ) -> None:
        await asyncio.sleep(delay)
        redis = await get_redis_pool()
        updated_message = {**message, "retry_count": attempt}
        await redis.publish(settings.REDIS_CHANNEL, json.dumps(updated_message))
        logger.debug("Re-published message for retry attempt %d", attempt)

    async def _send_to_dlq(
        self,
        session: AsyncSession,
        notification: Notification,
        message: dict[str, Any],
    ) -> None:
        logger.warning(
            "Notification %s exhausted retries (%d), sending to DLQ",
            notification.id,
            settings.MAX_RETRIES,
        )
        notification.status = NotificationStatus.DEAD_LETTER
        notification.updated_at = datetime.now(timezone.utc)
        await session.commit()

        redis = await get_redis_pool()
        dlq_message = {**message, "dead_letter": True}
        await redis.publish(settings.DEAD_LETTER_CHANNEL, json.dumps(dlq_message))
