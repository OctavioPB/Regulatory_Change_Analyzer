"""
Manually trigger ingestion for a specific source.

Usage:
    python scripts/ingest_source.py --source cnbv
    python scripts/ingest_source.py --source sec
    python scripts/ingest_source.py --source all
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import AsyncSessionLocal, init_db  # noqa: E402
from src.services import ingestion_service  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s")
logger = logging.getLogger(__name__)


async def main(source: str) -> None:
    await init_db()

    sources = (
        ingestion_service.SUPPORTED_SOURCES if source == "all" else [source.lower()]
    )

    for src in sources:
        async with AsyncSessionLocal() as db:
            result = await ingestion_service.run(src, db)
            await db.commit()

        logger.info(
            "[%s] fetched=%d  new=%d  skipped=%d  failed=%d",
            result.source, result.fetched, result.new, result.skipped, result.failed,
        )
        if result.errors:
            for err in result.errors:
                logger.warning("  ↳ %s", err)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest regulatory documents from a source")
    parser.add_argument(
        "--source",
        required=True,
        choices=ingestion_service.SUPPORTED_SOURCES + ["all"],
        help="Source name, or 'all' to run every configured source",
    )
    args = parser.parse_args()
    asyncio.run(main(args.source))
