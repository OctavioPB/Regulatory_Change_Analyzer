import asyncio
import logging
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.mapping import embedder
from src.models.document import RegulatoryChange, RegulatoryDocument
from src.nlp.pipeline import AnalysisResult, SectionChange, analyze
from src.nlp.regulation_id import regulation_key, title_prefilter
from src.repositories import audit_repo

logger = logging.getLogger(__name__)


@dataclass
class NlpResult:
    document_id: uuid.UUID
    changes_created: int = 0
    skipped: bool = False
    error: str | None = None


async def analyze_document(document_id: uuid.UUID, db: AsyncSession) -> NlpResult:
    """Run the NLP pipeline on a stored document and persist RegulatoryChange records.

    Diffs against the previous version of the same regulation (same source and circular
    number). If none is found, analyzes the document in isolation (all content is "new").

    Args:
        document_id: UUID of the RegulatoryDocument to analyze.
        db: Active async session; caller must commit after this returns.

    Returns:
        NlpResult with the count of persisted RegulatoryChange records.
    """
    result = await db.execute(
        select(RegulatoryDocument).where(RegulatoryDocument.id == document_id)
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        return NlpResult(document_id=document_id, error="Document not found")

    if not doc.raw_text:
        return NlpResult(document_id=document_id, skipped=True, error="No raw text available")

    already_analyzed = await db.execute(
        select(RegulatoryChange.id).where(RegulatoryChange.document_id == document_id).limit(1)
    )
    if already_analyzed.scalar_one_or_none() is not None:
        logger.debug("Document %s already has RegulatoryChange records, skipping", document_id)
        return NlpResult(document_id=document_id, skipped=True)

    old_text = await _find_previous_text(doc, db)
    # difflib section comparison is CPU-bound — run it off the event loop
    analysis: AnalysisResult = await asyncio.to_thread(analyze, doc.raw_text, old_text)

    if not analysis.has_changes:
        logger.info("No significant changes detected in document %s", document_id)
        return NlpResult(document_id=document_id, changes_created=0)

    embeddings = await _embed_sections(analysis.changes)
    for section_change, embedding in zip(analysis.changes, embeddings):
        db.add(_to_orm(section_change, doc, embedding))
    count = len(analysis.changes)

    await audit_repo.log(
        db,
        action="document_analyzed",
        entity_type="RegulatoryDocument",
        entity_id=str(document_id),
        detail=f"changes_created={count} source={doc.source}",
    )
    logger.info("Document %s → %d RegulatoryChange records created", document_id, count)
    return NlpResult(document_id=document_id, changes_created=count)


async def analyze_all_pending(db: AsyncSession) -> dict[str, int]:
    """Analyze every document that does not yet have RegulatoryChange records.

    Args:
        db: Active async session; caller must commit after this returns.

    Returns:
        Dict with aggregate counts: {'analyzed': N, 'changes_created': N, 'errors': N}.
    """
    # Documents that have text but no associated RegulatoryChange yet
    stmt = (
        select(RegulatoryDocument)
        .where(RegulatoryDocument.raw_text.isnot(None))
        .where(
            ~RegulatoryDocument.id.in_(
                select(RegulatoryChange.document_id).distinct()
            )
        )
        .order_by(RegulatoryDocument.publication_date.asc())
    )
    result = await db.execute(stmt)
    docs = list(result.scalars().all())

    logger.info("Found %d documents pending NLP analysis", len(docs))

    totals = {"analyzed": 0, "changes_created": 0, "errors": 0}
    for doc in docs:
        nlp_result = await analyze_document(doc.id, db)
        if nlp_result.error and not nlp_result.skipped:
            totals["errors"] += 1
            logger.warning("NLP error for %s: %s", doc.id, nlp_result.error)
        elif not nlp_result.skipped:
            totals["analyzed"] += 1
            totals["changes_created"] += nlp_result.changes_created

    return totals


_PREVIOUS_CANDIDATES = 50


async def _find_previous_text(doc: RegulatoryDocument, db: AsyncSession) -> str:
    """Text of the latest earlier version of the *same* regulation, to diff against.

    Same source and same circular number (``regulation_key``), published before this
    document. A title with no recognisable number gets no baseline and is analysed on its
    own — diffing it against an unrelated circular would invent repeals.

    Returns empty string if no prior version exists.
    """
    key = regulation_key(doc.title)
    if key is None:
        logger.debug("No regulation identifier in %r — analysing without a baseline", doc.title)
        return ""
    result = await db.execute(
        select(RegulatoryDocument.title, RegulatoryDocument.raw_text)
        .where(RegulatoryDocument.source == doc.source)
        .where(RegulatoryDocument.id != doc.id)
        .where(RegulatoryDocument.publication_date < doc.publication_date)
        .where(RegulatoryDocument.raw_text.isnot(None))
        .where(RegulatoryDocument.title.ilike(title_prefilter(key)))
        .order_by(RegulatoryDocument.publication_date.desc())
        .limit(_PREVIOUS_CANDIDATES)
    )
    for title, raw_text in result.all():
        if regulation_key(title) == key:
            logger.debug("Found previous version of %s for %s", key, doc.external_id)
            return raw_text or ""
    return ""


async def _embed_sections(changes: list[SectionChange]) -> list[list[float] | None]:
    """Embed all changed sections in one batch (in a worker thread).

    One batched ``encode`` call is several times faster than one call per
    section, and keeping it off the event loop leaves the API responsive.
    """
    if not changes or not await asyncio.to_thread(embedder.available):
        return [None] * len(changes)
    texts = [(c.new_text or "")[:2000] for c in changes]
    try:
        vectors = await asyncio.to_thread(embedder.embed_batch, texts)
    except Exception as exc:
        logger.warning("Batch embedding failed: %s", exc)
        return [None] * len(changes)
    return [v if t else None for v, t in zip(vectors, texts)]


def _to_orm(
    section_change: SectionChange,
    doc: RegulatoryDocument,
    embedding: list[float] | None = None,
) -> RegulatoryChange:
    """Convert a SectionChange into a RegulatoryChange ORM instance."""
    return RegulatoryChange(
        document_id=doc.id,
        article_ref=section_change.section_ref[:100],
        change_type=section_change.change_type,
        summary=section_change.summary[:500],
        old_text=section_change.old_text[:4000] if section_change.old_text else None,
        new_text=section_change.new_text[:4000],
        embedding=embedding,
    )
