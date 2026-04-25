"""Trend signal extraction and aggregation service."""
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.document import RegulatoryDocument
from src.nlp.trend_extractor import extract_trend
from src.repositories import trend_repo

logger = logging.getLogger(__name__)


async def extract_signals_from_document(document_id: uuid.UUID, db: AsyncSession) -> bool:
    """Analyse a single document and persist a TrendSignal if it qualifies.

    Returns True if a signal was created/updated, False if the document was skipped.
    """
    doc = await db.get(RegulatoryDocument, document_id)
    if doc is None:
        logger.warning("Document %s not found", document_id)
        return False

    result = extract_trend(
        title=doc.title,
        text=doc.raw_text or "",
        publication_date=doc.publication_date,
    )
    if result is None:
        logger.debug("Document %s skipped (not a forward-looking signal)", document_id)
        return False

    await trend_repo.upsert_signal(db, document_id, result)
    logger.info(
        "Signal extracted: doc=%s type=%s domain=%s horizon=%dm",
        document_id, result.doc_type, result.domain, result.horizon_months,
    )
    return True


async def extract_all_signals(db: AsyncSession) -> dict[str, int]:
    """Extract trend signals from all regulatory documents not yet processed.

    Returns a summary dict with created/skipped counts.
    """
    from src.models.trend import TrendSignal
    from sqlalchemy import not_, exists

    stmt = select(RegulatoryDocument).where(
        not_(
            exists().where(TrendSignal.document_id == RegulatoryDocument.id)
        )
    )
    docs = list((await db.execute(stmt)).scalars().all())

    created = 0
    skipped = 0
    for doc in docs:
        ok = await extract_signals_from_document(doc.id, db)
        if ok:
            created += 1
        else:
            skipped += 1

    logger.info("Trend extraction complete: %d created, %d skipped", created, skipped)
    return {"created": created, "skipped": skipped}
