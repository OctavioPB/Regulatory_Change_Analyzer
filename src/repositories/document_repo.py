import logging
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ingestion.base import RawDocument
from src.models.document import RegulatoryDocument

logger = logging.getLogger(__name__)


async def get_by_external_id(db: AsyncSession, external_id: str) -> RegulatoryDocument | None:
    """Return the document with the given external_id, or None if absent."""
    result = await db.execute(
        select(RegulatoryDocument).where(RegulatoryDocument.external_id == external_id)
    )
    return result.scalar_one_or_none()


async def create_from_raw(
    db: AsyncSession,
    raw_doc: RawDocument,
    raw_text: str | None = None,
    file_path: str | None = None,
) -> RegulatoryDocument:
    """Persist a new RegulatoryDocument from a scraper's RawDocument payload.

    Args:
        db: Active async session (caller is responsible for commit).
        raw_doc: Metadata returned by a scraper.
        raw_text: Extracted plain text (may be None if fetching failed).
        file_path: Absolute path of the saved raw file on disk.

    Returns:
        The newly created, unflushed ORM instance.
    """
    doc = RegulatoryDocument(
        external_id=raw_doc.external_id,
        source=raw_doc.source,
        title=raw_doc.title,
        url=raw_doc.url,
        publication_date=raw_doc.publication_date,
        raw_text=raw_text,
        file_path=file_path,
    )
    db.add(doc)
    logger.debug("Queued new document: %s", raw_doc.external_id)
    return doc


async def list_recent(
    db: AsyncSession,
    source: str | None = None,
    limit: int = 50,
) -> list[RegulatoryDocument]:
    """Return the most recently fetched documents.

    Args:
        db: Active async session.
        source: Optional filter by source name (e.g. "CNBV").
        limit: Maximum number of results.

    Returns:
        List of RegulatoryDocument ordered by fetched_at descending.
    """
    stmt = select(RegulatoryDocument).order_by(RegulatoryDocument.fetched_at.desc()).limit(limit)
    if source:
        stmt = stmt.where(RegulatoryDocument.source == source.upper())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def count(db: AsyncSession, source: str | None = None) -> int:
    """Return the total number of stored documents, optionally filtered by source."""
    stmt = select(func.count(RegulatoryDocument.id))
    if source:
        stmt = stmt.where(RegulatoryDocument.source == source.upper())
    result = await db.execute(stmt)
    return result.scalar_one()
