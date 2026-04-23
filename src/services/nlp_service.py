import logging
import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.document import RegulatoryChange, RegulatoryDocument
from src.nlp.pipeline import AnalysisResult, SectionChange, analyze

logger = logging.getLogger(__name__)

# Try to import sentence-transformers; if unavailable, embeddings are skipped.
try:
    from src.mapping.embedder import embed_text as _embed_text
    _HAS_EMBEDDER = True
except Exception:
    _HAS_EMBEDDER = False
    logger.info("sentence-transformers not available — embeddings will be skipped")


@dataclass
class NlpResult:
    document_id: uuid.UUID
    changes_created: int = 0
    skipped: bool = False
    error: str | None = None


async def analyze_document(document_id: uuid.UUID, db: AsyncSession) -> NlpResult:
    """Run the NLP pipeline on a stored document and persist RegulatoryChange records.

    Looks for a previous version of the same source to compute diffs.
    If none is found, analyzes the document in isolation (all content is "new").

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
    analysis: AnalysisResult = analyze(doc.raw_text, old_text)

    if not analysis.has_changes:
        logger.info("No significant changes detected in document %s", document_id)
        return NlpResult(document_id=document_id, changes_created=0)

    count = 0
    for section_change in analysis.changes:
        orm_record = _to_orm(section_change, doc)
        db.add(orm_record)
        count += 1

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


async def _find_previous_text(doc: RegulatoryDocument, db: AsyncSession) -> str:
    """Find the most recent earlier document from the same source to use as old_text.

    Uses the same source and looks for the document published immediately before
    the current one. This heuristic is reasonable for regulations that are
    updated periodically (e.g. CNBV circulars that supersede earlier ones).

    Returns empty string if no prior document exists.
    """
    result = await db.execute(
        select(RegulatoryDocument.raw_text)
        .where(RegulatoryDocument.source == doc.source)
        .where(RegulatoryDocument.publication_date < doc.publication_date)
        .where(RegulatoryDocument.raw_text.isnot(None))
        .order_by(RegulatoryDocument.publication_date.desc())
        .limit(1)
    )
    prior_text = result.scalar_one_or_none()
    if prior_text:
        logger.debug("Found previous version for %s (source=%s)", doc.external_id, doc.source)
    return prior_text or ""


def _to_orm(section_change: SectionChange, doc: RegulatoryDocument) -> RegulatoryChange:
    """Convert a SectionChange into a RegulatoryChange ORM instance."""
    embedding: list[float] | None = None
    if _HAS_EMBEDDER and section_change.new_text:
        try:
            embedding = _embed_text(section_change.new_text[:2000])
        except Exception as exc:
            logger.warning("Embedding failed for section '%s': %s", section_change.section_ref, exc)

    return RegulatoryChange(
        document_id=doc.id,
        article_ref=section_change.section_ref[:100],
        change_type=section_change.change_type,
        summary=section_change.summary[:500],
        old_text=section_change.old_text[:4000] if section_change.old_text else None,
        new_text=section_change.new_text[:4000],
        embedding=embedding,
    )
