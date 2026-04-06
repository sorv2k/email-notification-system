import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select

from app.core.database import async_session_factory
from app.core.redis import get_redis_pool
from app.models.notification import Notification, NotificationStatus
from app.workers.consumer import WORKER_STATUS_HASH

logger = logging.getLogger(__name__)
router = APIRouter()
templates = Jinja2Templates(directory="dashboard/templates")


async def _collect_metrics() -> dict:
    metrics: dict = {
        "total": 0,
        "pending": 0,
        "sending": 0,
        "sent": 0,
        "failed": 0,
        "dead_letter": 0,
        "queue_depth": 0,
        "workers": [],
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }

    # Notification counts from DB
    try:
        async with async_session_factory() as session:
            rows = await session.execute(
                select(Notification.status, func.count())
                .group_by(Notification.status)
            )
            for row_status, count in rows.all():
                key = row_status.value if hasattr(row_status, "value") else str(row_status)
                metrics[key] = count
                metrics["total"] += count
    except Exception as exc:
        logger.error("DB metrics error: %s", exc)

    # Redis queue depth (approx: length of pending messages)
    try:
        redis = await get_redis_pool()
        # Use LLEN on a list key if using list-based queue, otherwise report 0
        # With pub/sub we report subscriber count as a proxy
        info = await redis.info("clients")
        metrics["queue_depth"] = info.get("connected_clients", 0)
    except Exception as exc:
        logger.error("Redis metrics error: %s", exc)

    # Worker statuses from Redis (populated by workers across all processes)
    try:
        redis = await get_redis_pool()
        raw = await redis.hgetall(WORKER_STATUS_HASH)
        metrics["workers"] = [
            {"worker_id": key, **json.loads(val)}
            for key, val in raw.items()
        ]
    except Exception as exc:
        logger.error("Worker status metrics error: %s", exc)

    return metrics


@router.get("/", include_in_schema=False)
async def root_redirect() -> RedirectResponse:
    return RedirectResponse(url="/dashboard")


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request) -> HTMLResponse:
    metrics = await _collect_metrics()
    return templates.TemplateResponse(
        "dashboard.html", {"request": request, "metrics": metrics}
    )


@router.get("/dashboard/metrics")
async def dashboard_metrics() -> dict:
    return await _collect_metrics()


@router.get("/dashboard/workers")
async def dashboard_workers() -> dict:
    try:
        redis = await get_redis_pool()
        raw = await redis.hgetall(WORKER_STATUS_HASH)
        workers = [{"worker_id": key, **json.loads(val)} for key, val in raw.items()]
    except Exception:
        workers = []
    return {"workers": workers}
