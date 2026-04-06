from typing import Optional

import redis.asyncio as aioredis

from app.core.config import settings

_redis_pool: Optional[aioredis.Redis] = None


async def get_redis_pool() -> aioredis.Redis:
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_pool


async def close_redis_pool() -> None:
    global _redis_pool
    if _redis_pool is not None:
        await _redis_pool.close()
        _redis_pool = None
