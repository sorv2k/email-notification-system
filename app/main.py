import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI

from app.api.routes import health, notifications
from app.core.config import settings
from app.core.database import engine
from app.core.redis import close_redis_pool
from app.models.notification import Base
from app.workers.consumer import WorkerPool

logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

_worker_pool: WorkerPool | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    global _worker_pool
    # Create tables (idempotent; real migrations handled by Alembic)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    _worker_pool = WorkerPool()
    await _worker_pool.start()
    logger.info("Application startup complete")

    yield

    if _worker_pool:
        await _worker_pool.stop()
    await close_redis_pool()
    await engine.dispose()
    logger.info("Application shutdown complete")


app = FastAPI(
    title="Email Notification System",
    description="Async email notification system backed by Redis pub/sub and Resend",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(notifications.router)
