import asyncio
import logging

from celery import Celery

from src.config import settings

logger = logging.getLogger(__name__)

celery_app = Celery(
    "rca_worker",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "scrape-all-sources": {
            "task": "src.worker.scrape_all_sources",
            "schedule": settings.scrape_interval_hours * 3600,
        }
    },
)


@celery_app.task(name="src.worker.scrape_all_sources")
def scrape_all_sources() -> dict:
    """Celery task: fetch and persist latest documents from all configured sources."""
    from src.database import AsyncSessionLocal, init_db
    from src.services import ingestion_service

    async def _run() -> dict:
        await init_db()
        totals: dict[str, int] = {"fetched": 0, "new": 0, "skipped": 0, "failed": 0}

        for source in ingestion_service.SUPPORTED_SOURCES:
            async with AsyncSessionLocal() as db:
                result = await ingestion_service.run(source, db)
                await db.commit()

            totals["fetched"] += result.fetched
            totals["new"] += result.new
            totals["skipped"] += result.skipped
            totals["failed"] += result.failed

            logger.info(
                "[%s] new=%d skipped=%d failed=%d",
                result.source, result.new, result.skipped, result.failed,
            )

        return totals

    return asyncio.run(_run())
