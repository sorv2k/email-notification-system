"""Entry point so workers can be started with: python -m app.workers.consumer"""
import asyncio
import logging

from app.core.config import settings
from app.workers.consumer import WorkerPool

logging.basicConfig(level=settings.LOG_LEVEL)


async def main() -> None:
    pool = WorkerPool()
    await pool.start()
    # Run forever; Docker/systemd manages lifecycle
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
