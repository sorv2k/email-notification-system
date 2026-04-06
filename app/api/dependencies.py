from collections.abc import AsyncGenerator

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.redis import get_redis_pool


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_session():
        yield session


async def get_redis() -> aioredis.Redis:
    return await get_redis_pool()
