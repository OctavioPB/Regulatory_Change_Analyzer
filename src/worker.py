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
    """Celery task: fetch latest documents from all configured sources."""
    from src.ingestion.cnbv import CNBVScraper
    from src.ingestion.sec import SECScraper
    from src.database import AsyncSessionLocal
    from src.models.document import RegulatoryDocument

    async def _run() -> dict:
        scrapers = [CNBVScraper(), SECScraper()]
        total = 0
        async with AsyncSessionLocal() as db:
            for scraper in scrapers:
                docs = await scraper.fetch_latest()
                for raw_doc in docs:
                    doc = RegulatoryDocument(
                        external_id=raw_doc.external_id,
                        source=raw_doc.source,
                        title=raw_doc.title,
                        url=raw_doc.url,
                        publication_date=raw_doc.publication_date,
                    )
                    db.add(doc)
                    total += 1
                await scraper.close()
            await db.commit()
        return {"ingested": total}

    return asyncio.run(_run())
