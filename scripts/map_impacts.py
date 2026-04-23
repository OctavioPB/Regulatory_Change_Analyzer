"""
Map detected regulatory changes to affected contracts, creating ImpactAlerts.

Usage:
    python scripts/map_impacts.py
    python scripts/map_impacts.py --document-id <uuid>
    python scripts/map_impacts.py --change-id <uuid>

Run after run_analysis.py so that RegulatoryChange records exist in the DB.
"""

import argparse
import asyncio
import logging
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import AsyncSessionLocal, init_db  # noqa: E402
from src.services import impact_service  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s")
logger = logging.getLogger(__name__)


async def main(document_id: str | None, change_id: str | None) -> None:
    await init_db()

    async with AsyncSessionLocal() as db:
        if change_id:
            result = await impact_service.map_change_to_contracts(uuid.UUID(change_id), db)
            if result.error:
                logger.error("Mapping failed: %s", result.error)
            elif result.skipped:
                logger.info("Change skipped (no targets found or no text)")
            else:
                logger.info(
                    "Done — alerts_created=%d  items_created=%d",
                    result.alerts_created,
                    result.items_created,
                )

        elif document_id:
            result = await impact_service.map_document_impacts(uuid.UUID(document_id), db)
            logger.info(
                "Done — changes_processed=%d  alerts_created=%d  items_created=%d  errors=%d",
                result.changes_processed,
                result.alerts_created,
                result.items_created,
                len(result.errors),
            )
            for err in result.errors:
                logger.error("  Error: %s", err)

        else:
            # Process all documents that have changes but no impact alerts yet
            from sqlalchemy import select, func, not_, exists
            from src.models.document import RegulatoryDocument, RegulatoryChange
            from src.models.impact import ImpactAlert

            stmt = (
                select(RegulatoryDocument.id)
                .join(RegulatoryChange, RegulatoryChange.document_id == RegulatoryDocument.id)
                .where(
                    not_(
                        exists(
                            select(ImpactAlert.id).where(
                                ImpactAlert.document_id == RegulatoryDocument.id
                            )
                        )
                    )
                )
                .distinct()
            )
            rows = await db.execute(stmt)
            doc_ids = [row[0] for row in rows.fetchall()]

            if not doc_ids:
                logger.info("No documents pending impact mapping.")
                return

            logger.info("Processing %d documents…", len(doc_ids))
            totals = {"processed": 0, "alerts": 0, "items": 0, "errors": 0}

            for did in doc_ids:
                res = await impact_service.map_document_impacts(did, db)
                totals["processed"] += res.changes_processed
                totals["alerts"] += res.alerts_created
                totals["items"] += res.items_created
                totals["errors"] += len(res.errors)

            logger.info(
                "All done — changes_processed=%d  alerts=%d  items=%d  errors=%d",
                totals["processed"], totals["alerts"], totals["items"], totals["errors"],
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Map regulatory changes to contract impacts")
    parser.add_argument(
        "--document-id",
        default=None,
        help="UUID of a specific document to process (default: all pending)",
    )
    parser.add_argument(
        "--change-id",
        default=None,
        help="UUID of a specific RegulatoryChange to map",
    )
    args = parser.parse_args()

    if args.document_id and args.change_id:
        parser.error("Provide --document-id OR --change-id, not both.")

    asyncio.run(main(args.document_id, args.change_id))
