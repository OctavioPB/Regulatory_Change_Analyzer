"""
Manually trigger ingestion for a specific source.

Usage:
    python scripts/ingest_source.py --source cnbv
    python scripts/ingest_source.py --source sec
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import settings  # noqa: E402 — must come after sys.path update
from src.database import AsyncSessionLocal, init_db  # noqa: E402
from src.ingestion.cnbv import CNBVScraper  # noqa: E402
from src.ingestion.sec import SECScraper  # noqa: E402
from src.models.document import RegulatoryDocument  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

SCRAPERS = {
    "cnbv": CNBVScraper,
    "sec": SECScraper,
}


async def ingest(source: str) -> None:
    scraper_cls = SCRAPERS.get(source.lower())
    if scraper_cls is None:
        raise ValueError(f"Unknown source '{source}'. Valid options: {list(SCRAPERS)}")

    await init_db()
    scraper = scraper_cls()

    logger.info("Fetching from %s ...", source.upper())
    docs = await scraper.fetch_latest()
    logger.info("Found %d documents", len(docs))

    async with AsyncSessionLocal() as db:
        new_count = 0
        for raw_doc in docs:
            from sqlalchemy import select
            existing = await db.execute(
                select(RegulatoryDocument).where(RegulatoryDocument.external_id == raw_doc.external_id)
            )
            if existing.scalar_one_or_none() is not None:
                continue
            doc = RegulatoryDocument(
                external_id=raw_doc.external_id,
                source=raw_doc.source,
                title=raw_doc.title,
                url=raw_doc.url,
                publication_date=raw_doc.publication_date,
            )
            db.add(doc)
            new_count += 1
        await db.commit()
    logger.info("Ingested %d new documents from %s", new_count, source.upper())
    await scraper.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest regulatory documents from a source")
    parser.add_argument("--source", required=True, choices=list(SCRAPERS), help="Source name")
    args = parser.parse_args()
    asyncio.run(ingest(args.source))
