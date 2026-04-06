import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.templating import Jinja2Templates

from app.core.config import settings
from app.core.database import engine
from app.core.redis import close_redis_pool
from dashboard.routes import router

logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

templates = Jinja2Templates(directory="dashboard/templates")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Dashboard startup")
    yield
    await close_redis_pool()
    await engine.dispose()
    logger.info("Dashboard shutdown")


app = FastAPI(
    title="Email Notification Dashboard",
    description="Monitoring dashboard for the email notification system",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(router)
