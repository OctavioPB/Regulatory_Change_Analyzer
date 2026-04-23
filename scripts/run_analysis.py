"""
Run the full analysis pipeline on all unprocessed regulatory documents.

Usage:
    python scripts/run_analysis.py
"""

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select  # noqa: E402

from src.database import AsyncSessionLocal, init_db  # noqa: E402
from src.mapping.embedder import embed_text  # noqa: E402
from src.mapping.semantic_mapper import find_similar_clauses  # noqa: E402
from src.models.document import RegulatoryChange, RegulatoryDocument  # noqa: E402
from src.models.impact import ImpactAlert, ImpactItem  # noqa: E402
from src.nlp.classifier import classify_change  # noqa: E402
from src.nlp.comparator import compare_texts  # noqa: E402
from src.recommendations.generator import generate_suggestion  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def run_analysis() -> None:
    await init_db()

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(RegulatoryDocument).where(RegulatoryDocument.raw_text.isnot(None))
        )
        documents = list(result.scalars().all())
        logger.info("Found %d documents with text to analyze", len(documents))

        for doc in documents:
            logger.info("Analyzing: %s", doc.title[:80])

            diff = compare_texts("", doc.raw_text or "")
            if diff.change_ratio < 0.01:
                logger.debug("No meaningful changes in %s", doc.external_id)
                continue

            change_type = classify_change(doc.raw_text or "")
            embedding = embed_text(doc.raw_text[:2000] if doc.raw_text else "")

            change = RegulatoryChange(
                document_id=doc.id,
                change_type=change_type,
                summary=doc.title,
                new_text=doc.raw_text[:4000] if doc.raw_text else None,
                embedding=embedding,
            )
            db.add(change)
            await db.flush()

            matches = await find_similar_clauses(doc.raw_text[:2000] or "", db, top_k=5)
            if not matches:
                continue

            alert = ImpactAlert(document_id=doc.id, title=f"Impact: {doc.title[:200]}")
            db.add(alert)
            await db.flush()

            for match in matches:
                suggestion = generate_suggestion(
                    change_type=change_type,
                    severity=match.severity,
                    clause_ref=match.clause_ref,
                    article_ref=change.article_ref or "",
                    source_title=doc.title,
                )
                item = ImpactItem(
                    alert_id=alert.id,
                    change_id=change.id,
                    clause_id=match.clause_id,
                    impact_type="contract",
                    affected_name=match.contract_name,
                    affected_ref=match.clause_ref,
                    severity=match.severity,
                    suggestion=suggestion,
                )
                db.add(item)

        await db.commit()
        logger.info("Analysis complete")


if __name__ == "__main__":
    asyncio.run(run_analysis())
