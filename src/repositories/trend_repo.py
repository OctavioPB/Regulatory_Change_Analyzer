"""CRUD operations for TrendSignal."""
import json
import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.trend import TrendSignal
from src.nlp.trend_extractor import TrendExtractionResult


async def upsert_signal(
    db: AsyncSession,
    document_id: uuid.UUID,
    result: TrendExtractionResult,
) -> TrendSignal:
    """Insert a TrendSignal or return the existing one for this document."""
    existing = await db.execute(
        select(TrendSignal).where(TrendSignal.document_id == document_id)
    )
    signal = existing.scalar_one_or_none()

    if signal is not None:
        signal.doc_type = result.doc_type
        signal.domain = result.domain
        signal.signal_strength = result.signal_strength
        signal.horizon_months = result.horizon_months
        signal.predicted_effective_date = result.predicted_effective_date
        signal.key_themes = json.dumps(result.key_themes)
        signal.confidence_score = result.confidence_score
        signal.extracted_at = datetime.utcnow()
        return signal

    signal = TrendSignal(
        document_id=document_id,
        doc_type=result.doc_type,
        domain=result.domain,
        signal_strength=result.signal_strength,
        horizon_months=result.horizon_months,
        predicted_effective_date=result.predicted_effective_date,
        key_themes=json.dumps(result.key_themes),
        confidence_score=result.confidence_score,
    )
    db.add(signal)
    await db.flush()
    return signal


async def list_signals(
    db: AsyncSession,
    doc_type: str | None = None,
    domain: str | None = None,
    min_confidence: float = 0.0,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[TrendSignal], int]:
    """Return paginated trend signals with optional filters."""
    base = select(TrendSignal)
    if doc_type:
        base = base.where(TrendSignal.doc_type == doc_type)
    if domain:
        base = base.where(TrendSignal.domain == domain)
    if min_confidence > 0:
        base = base.where(TrendSignal.confidence_score >= min_confidence)

    total: int = (
        await db.execute(select(func.count()).select_from(base.subquery()))
    ).scalar_one()

    items_stmt = (
        base.order_by(TrendSignal.confidence_score.desc(), TrendSignal.extracted_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(items_stmt)
    return list(result.scalars().all()), total


async def get_domain_forecast(db: AsyncSession) -> list[dict]:
    """Aggregate signals by domain — avg strength, count, avg horizon."""
    stmt = (
        select(
            TrendSignal.domain,
            func.count(TrendSignal.id).label("signal_count"),
            func.avg(TrendSignal.signal_strength).label("avg_strength"),
            func.avg(TrendSignal.confidence_score).label("avg_confidence"),
            func.avg(TrendSignal.horizon_months).label("avg_horizon"),
        )
        .group_by(TrendSignal.domain)
        .order_by(func.avg(TrendSignal.signal_strength).desc())
    )
    rows = (await db.execute(stmt)).all()
    return [
        {
            "domain": r.domain,
            "signal_count": r.signal_count,
            "avg_strength": round(float(r.avg_strength), 3),
            "avg_confidence": round(float(r.avg_confidence), 3),
            "avg_horizon_months": round(float(r.avg_horizon)),
        }
        for r in rows
    ]


async def count_by_doc_type(db: AsyncSession) -> dict[str, int]:
    """Return count of signals per doc_type."""
    stmt = select(TrendSignal.doc_type, func.count(TrendSignal.id)).group_by(TrendSignal.doc_type)
    rows = (await db.execute(stmt)).all()
    return {str(r[0]): r[1] for r in rows}
