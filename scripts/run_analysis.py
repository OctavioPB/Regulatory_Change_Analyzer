"""
Run the NLP analysis pipeline on all documents pending analysis.

Usage:
    python scripts/run_analysis.py
    python scripts/run_analysis.py --document-id <uuid>
"""

import argparse
import asyncio
import logging
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import AsyncSessionLocal, init_db  # noqa: E402
from src.services import nlp_service  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s")
logger = logging.getLogger(__name__)


async def main(document_id: str | None) -> None:
    await init_db()

    async with AsyncSessionLocal() as db:
        if document_id:
            result = await nlp_service.analyze_document(uuid.UUID(document_id), db)
            await db.commit()
            if result.error:
                logger.error("Analysis failed: %s", result.error)
            elif result.skipped:
                logger.info("Document skipped (already analyzed or no text)")
            else:
                logger.info("Changes created: %d", result.changes_created)
        else:
            totals = await nlp_service.analyze_all_pending(db)
            await db.commit()
            logger.info(
                "Done — analyzed=%d  changes_created=%d  errors=%d",
                totals["analyzed"],
                totals["changes_created"],
                totals["errors"],
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run NLP analysis on regulatory documents")
    parser.add_argument(
        "--document-id",
        default=None,
        help="UUID of a specific document to analyze (default: all pending)",
    )
    args = parser.parse_args()
    asyncio.run(main(args.document_id))
