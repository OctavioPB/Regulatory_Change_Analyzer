"""CRUD operations for CrossJurisdictionLink."""
import json
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.mapping.cross_mapper import CrossCandidate
from src.models.cross_mapping import CrossJurisdictionLink


async def upsert_link(db: AsyncSession, candidate: CrossCandidate) -> CrossJurisdictionLink:
    """Insert a link or return the existing one if the pair already exists."""
    existing = await db.execute(
        select(CrossJurisdictionLink).where(
            CrossJurisdictionLink.source_change_id == uuid.UUID(candidate.source_change_id),
            CrossJurisdictionLink.target_change_id == uuid.UUID(candidate.target_change_id),
        )
    )
    link = existing.scalar_one_or_none()
    if link is not None:
        return link

    link = CrossJurisdictionLink(
        source_change_id=uuid.UUID(candidate.source_change_id),
        target_change_id=uuid.UUID(candidate.target_change_id),
        source_jurisdiction=candidate.source_jurisdiction,
        target_jurisdiction=candidate.target_jurisdiction,
        similarity_score=candidate.similarity_score,
        shared_rule_ids=json.dumps(candidate.shared_rule_ids),
        analysis=candidate.analysis,
    )
    db.add(link)
    await db.flush()
    return link


async def list_links_for_change(
    db: AsyncSession,
    change_id: uuid.UUID,
    *,
    as_source: bool = True,
    as_target: bool = True,
) -> list[CrossJurisdictionLink]:
    """Return all links where the change appears as source, target, or both."""
    conditions = []
    if as_source:
        conditions.append(CrossJurisdictionLink.source_change_id == change_id)
    if as_target:
        conditions.append(CrossJurisdictionLink.target_change_id == change_id)

    if not conditions:
        return []

    from sqlalchemy import or_
    stmt = (
        select(CrossJurisdictionLink)
        .where(or_(*conditions))
        .order_by(CrossJurisdictionLink.similarity_score.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def list_all_links(
    db: AsyncSession,
    source_jurisdiction: str | None = None,
    target_jurisdiction: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[CrossJurisdictionLink], int]:
    """Return paginated links with optional jurisdiction filters.

    Returns (items, total_count).
    """
    from sqlalchemy import func

    base_stmt = select(CrossJurisdictionLink)
    if source_jurisdiction:
        base_stmt = base_stmt.where(
            CrossJurisdictionLink.source_jurisdiction == source_jurisdiction.upper()
        )
    if target_jurisdiction:
        base_stmt = base_stmt.where(
            CrossJurisdictionLink.target_jurisdiction == target_jurisdiction.upper()
        )

    total: int = (
        await db.execute(select(func.count()).select_from(base_stmt.subquery()))
    ).scalar_one()

    items_stmt = (
        base_stmt.order_by(CrossJurisdictionLink.similarity_score.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(items_stmt)
    return list(result.scalars().all()), total


async def count_links_for_change(db: AsyncSession, change_id: uuid.UUID) -> int:
    """Return the number of cross links associated with a change (as source)."""
    from sqlalchemy import func
    result = await db.execute(
        select(func.count()).where(
            CrossJurisdictionLink.source_change_id == change_id
        )
    )
    return result.scalar_one()
