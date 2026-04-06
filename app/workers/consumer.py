import asyncio
import json
import logging
import socket
import uuid
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session_factory
from app.core.redis import get_redis_pool
from app.models.notification import Notification, NotificationStatus
from app.services.email import send_email
from app.workers.retry import RetryHandler

logger = logging.getLogger(__name__)

# In-process cache (used within this process only)
worker_status: dict[int, dict[str, Any]] = {}

# Redis hash key where all worker statuses are stored cross-process
WORKER_STATUS_HASH = "worker_statuses"
_HOSTNAME = socket.gethostname()


async def _persist_worker_status(worker_id: int) -> None:
    """Write this worker's status to Redis so the dashboard can read it."""
    try:
        redis = await get_redis_pool()
        await redis.hset(
            WORKER_STATUS_HASH,
            f"{_HOSTNAME}:{worker_id}",
            json.dumps(worker_status[worker_id]),
        )
    except Exception as exc:
        logger.debug("Could not persist worker status to Redis: %s", exc)


async def process_message(worker_id: int, message: dict[str, Any]) -> None:
    """Process a single notification message: send email and update DB."""
    notification_id = uuid.UUID(message["notification_id"])
    retry_count = int(message.get("retry_count", 0))

    async with async_session_factory() as session:
        # Fetch notification
        result = await session.execute(
            select(Notification).where(Notification.id == notification_id)
        )
        notification: Notification | None = result.scalar_one_or_none()
        if notification is None:
            logger.warning("Notification %s not found, skipping", notification_id)
            return

        # Mark as sending
        notification.status = NotificationStatus.SENDING
        notification.updated_at = datetime.now(timezone.utc)
        await session.commit()

        try:
            await send_email(
                notification.recipient_email,
                notification.subject,
                notification.body,
            )
            notification.status = NotificationStatus.SENT
            notification.sent_at = datetime.now(timezone.utc)
            notification.updated_at = datetime.now(timezone.utc)
            await session.commit()
            logger.info("Worker %d: sent notification %s", worker_id, notification_id)
            worker_status[worker_id]["processed"] += 1

        except Exception as exc:
            notification.status = NotificationStatus.FAILED
            notification.retry_count = retry_count
            notification.error_message = str(exc)
            notification.updated_at = datetime.now(timezone.utc)
            await session.commit()

            worker_status[worker_id]["failed"] += 1
            logger.error(
                "Worker %d: failed notification %s (attempt %d): %s",
                worker_id,
                notification_id,
                retry_count,
                exc,
            )

            handler = RetryHandler()
            await handler.handle_failure(session, notification, message)

        finally:
            worker_status[worker_id]["last_activity"] = datetime.now(timezone.utc).isoformat()
            await _persist_worker_status(worker_id)


async def worker_loop(worker_id: int, queue: asyncio.Queue) -> None:
    """Continuously pull messages from the asyncio queue and process them."""
    worker_status[worker_id] = {
        "processed": 0,
        "failed": 0,
        "last_activity": datetime.now(timezone.utc).isoformat(),
    }
    logger.info("Worker %d started", worker_id)
    await _persist_worker_status(worker_id)  # register immediately so dashboard sees it
    while True:
        message = await queue.get()
        try:
            await process_message(worker_id, message)
        except Exception as exc:
            logger.exception("Worker %d unhandled error: %s", worker_id, exc)
        finally:
            queue.task_done()


async def redis_subscriber(queue: asyncio.Queue) -> None:
    """Subscribe to Redis channel and push messages onto the asyncio queue."""
    redis: aioredis.Redis = await get_redis_pool()
    pubsub = redis.pubsub()
    await pubsub.subscribe(settings.REDIS_CHANNEL)
    logger.info("Subscribed to Redis channel '%s'", settings.REDIS_CHANNEL)

    async for raw_message in pubsub.listen():
        if raw_message["type"] != "message":
            continue
        try:
            data = json.loads(raw_message["data"])
            await queue.put(data)
        except json.JSONDecodeError as exc:
            logger.error("Invalid JSON in channel message: %s", exc)


class WorkerPool:
    def __init__(self) -> None:
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._tasks: list[asyncio.Task] = []

    async def start(self) -> None:
        """Start the subscriber and worker tasks."""
        for worker_id in range(settings.WORKER_COUNT):
            task = asyncio.create_task(
                worker_loop(worker_id, self.queue),
                name=f"worker-{worker_id}",
            )
            self._tasks.append(task)

        subscriber_task = asyncio.create_task(
            redis_subscriber(self.queue),
            name="redis-subscriber",
        )
        self._tasks.append(subscriber_task)
        logger.info("WorkerPool started with %d workers", settings.WORKER_COUNT)

    async def stop(self) -> None:
        """Cancel all worker tasks gracefully."""
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        logger.info("WorkerPool stopped")
