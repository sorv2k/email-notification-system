import logging

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db, get_redis
from app.models.schemas import HealthResponse

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)


@router.get("/health", response_model=HealthResponse)
async def health_check(
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
) -> HealthResponse:
    # Check database
    db_status = "ok"
    try:
        await db.execute(text("SELECT 1"))
    except Exception as exc:
        logger.error("DB health check failed: %s", exc)
        db_status = "error"

    # Check Redis
    redis_status = "ok"
    try:
        await redis.ping()
    except Exception as exc:
        logger.error("Redis health check failed: %s", exc)
        redis_status = "error"

    overall = "ok" if db_status == "ok" and redis_status == "ok" else "degraded"
    return HealthResponse(status=overall, database=db_status, redis=redis_status)
