import json
import logging
import uuid

import redis.asyncio as aioredis

from app.core.config import settings
from app.core.redis import get_redis_pool

logger = logging.getLogger(__name__)


async def publish_notification(
    notification_id: uuid.UUID,
    recipient_email: str,
    subject: str,
    body: str,
    retry_count: int = 0,
) -> None:
    """Publish a notification message to the Redis channel for worker processing."""
    redis: aioredis.Redis = await get_redis_pool()
    payload = json.dumps(
        {
            "notification_id": str(notification_id),
            "recipient_email": recipient_email,
            "subject": subject,
            "body": body,
            "retry_count": retry_count,
        }
    )
    await redis.publish(settings.REDIS_CHANNEL, payload)
    logger.debug(
        "Published notification %s to channel '%s' (retry=%d)",
        notification_id,
        settings.REDIS_CHANNEL,
        retry_count,
    )
